"""Capability function for `API-14` (`S-CFG-05`): ask a saved or unsaved question against pasted
text or an account's stored passages through the same [Signal classification]
(/architecture/rules.md#signal-classification), [Escalation](/architecture/rules.md#escalation)
and [Evidence extraction](/architecture/rules.md#evidence-extraction) rules as the pipeline.
Nothing is written here; the only rows the call leaves are the `AI_CALL` audit rows the AI
gateway writes in its own transactions."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import ColumnElement, Select, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.errors import AccountNotFound
from leadradar.ai.audit import AiCallContext
from leadradar.ai.embedder import embed
from leadradar.ai.gateway import AiGateway
from leadradar.ai.settings import AiGatewaySettings
from leadradar.ai.shapes import (
    ClassifierOption,
    ClassifierQuestion,
    ClassifierRequest,
    EscalationInput,
    EscalationQuestion,
    EvidenceInput,
    QuestionOption,
)
from leadradar.configuration.errors import QuestionInvalid, QuestionNotFound
from leadradar.configuration.queries import question_options, require_service
from leadradar.core.chunking import fuse_rankings, passage_header, split_into_passages
from leadradar.core.document_normalisation import detect_language
from leadradar.core.enums import DocumentSourceType, FindingStrength, SignalQuestionAnswerType
from leadradar.core.questions import validate_question_shape
from leadradar.core.scoring.settings import FieldError
from leadradar.core.signal.classification import (
    SCALE_SUFFIX,
    classifier_questions_for,
    map_answer,
    merge_yes_no_probabilities,
)
from leadradar.core.signal.escalation import Route, post_escalation_route, route
from leadradar.core.signal.evidence import validate_quote
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document

# Pasted text belongs to no account; the classifier frames its question about "the company".
PASTED_TEXT_ACCOUNT_NAME = "the company"
_PREVIEW_QUESTION_ID = "PREVIEW"


@dataclass(frozen=True)
class PreviewRequest:
    """The fields of [`QuestionPreviewRequest`]
    (/architecture/interfaces.md#questionpreviewrequest)."""

    service_id: uuid.UUID
    question_id: uuid.UUID | None
    text: str | None
    answer_type: SignalQuestionAnswerType | None
    options: list[dict[str, object]] | None
    source_types: list[str] | None
    hint_terms: list[str] | None
    sample_text: str | None
    account_id: uuid.UUID | None


@dataclass(frozen=True)
class _Question:
    id: str
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[dict[str, object]] | None
    source_types: list[str]
    hint_terms: list[str]


@dataclass(frozen=True)
class _Passage:
    text: str
    header: str
    language: str
    chunk_id: uuid.UUID | None
    title: str | None
    url: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class PreviewResult:
    """One entry of [`QuestionPreview`](/architecture/interfaces.md#questionpreview) `results`."""

    passage: str
    title: str | None
    url: str | None
    published_at: datetime | None
    p_positive: float
    escalated: bool
    strength: FindingStrength
    quote: str | None
    quote_en: str | None
    rationale: str | None


async def _question(session: AsyncSession, request: PreviewRequest) -> _Question:
    """The saved question, overlaid with any field the form changed, or the unsaved one."""
    saved: SignalQuestion | None = None
    if request.question_id is not None:
        saved = await session.get(SignalQuestion, request.question_id)
        if saved is None or saved.service_id != request.service_id:
            raise QuestionNotFound(f"No question {request.question_id}.")
    text = request.text if request.text is not None else (saved.text if saved else None)
    answer_type = request.answer_type or (saved.answer_type if saved else None)
    errors: list[FieldError] = []
    if not text:
        errors.append(FieldError("text", "A question text or question_id is required."))
    if answer_type is None:
        errors.append(FieldError("answer_type", "An answer type or question_id is required."))
    if (request.sample_text is None) == (request.account_id is None):
        errors.append(FieldError("sample_text", "Give exactly one of sample_text and account_id."))
    if errors or text is None or answer_type is None:
        raise QuestionInvalid(errors)
    options = (
        request.options
        if request.options is not None
        else (question_options(saved.options) if saved else None)
    )
    shape_errors = validate_question_shape(answer_type, options)
    if shape_errors:
        raise QuestionInvalid(shape_errors)
    source_types = (
        request.source_types
        if request.source_types is not None
        else (list(saved.source_types) if saved else [])
    )
    hint_terms = (
        request.hint_terms
        if request.hint_terms is not None
        else (list(saved.hint_terms) if saved else [])
    )
    return _Question(
        id=str(saved.id) if saved else _PREVIEW_QUESTION_ID,
        text=text,
        answer_type=answer_type,
        options=options,
        source_types=source_types,
        hint_terms=hint_terms,
    )


def _embedding_text(question: _Question) -> str:
    """Question text followed by its hint terms ([Chunking and passage selection]
    (/architecture/rules.md#chunking-and-passage-selection))."""
    return " ".join([question.text, *question.hint_terms])


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


async def _pasted_passages(
    sample_text: str,
    question: _Question,
    *,
    settings: AiGatewaySettings,
    embedder: httpx.AsyncClient,
    limit: int,
    now: datetime,
) -> list[_Passage]:
    """Pasted text chunked like a document, then question-scoped retrieval over its passages."""
    drafts = split_into_passages(
        sample_text,
        [],
        whole_document_max_chars=settings.whole_document_max_chars,
        chunk_target_chars=settings.chunk_target_chars,
        chunk_overlap_chars=settings.chunk_overlap_chars,
    )
    language = detect_language(sample_text)
    header = passage_header(
        account_name=PASTED_TEXT_ACCOUNT_NAME,
        document_title=None,
        section=None,
        date=now.strftime("%Y-%m-%d"),
    )
    order = [draft.ordinal for draft in drafts]
    if len(drafts) > 1:
        terms = [_normalised(term) for term in question.hint_terms if term.strip()]
        counts = {d.ordinal: sum(_normalised(d.text).count(term) for term in terms) for d in drafts}
        by_keyword = sorted((o for o, c in counts.items() if c > 0), key=lambda o: -counts[o])
        vectors = await embed(
            embedder,
            embedder_url=settings.embedder_url,
            dim=settings.embedding_dim,
            batch_size=settings.embed_batch_size,
            texts=[_embedding_text(question), *(d.text for d in drafts)],
        )
        similarity = {
            d.ordinal: _cosine(vectors[0], v) for d, v in zip(drafts, vectors[1:], strict=True)
        }
        by_meaning = sorted(similarity, key=lambda o: -similarity[o])
        fused = fuse_rankings(
            [by_keyword, by_meaning],
            candidates=settings.retrieval_candidates,
            rrf_k=settings.retrieval_rrf_k,
        )
        order = [ordinal for ordinal, _ in fused]
    return [
        _Passage(drafts[o].text, header, language, None, None, None, None) for o in order[:limit]
    ]


async def _account_passages(
    session: AsyncSession,
    account: Account,
    question: _Question,
    *,
    settings: AiGatewaySettings,
    embedder: httpx.AsyncClient,
    limit: int,
) -> list[_Passage]:
    """Question-scoped retrieval over the stored passages of the account's documents of the
    question's source types: a keyword and a meaning ranking fused by reciprocal rank."""

    def base() -> Select[uuid.UUID]:
        return (
            select(Chunk.id)
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Document.account_id == account.id,
                Document.source_type.in_(
                    [DocumentSourceType(value) for value in question.source_types]
                ),
                Chunk.text.isnot(None),
            )
        )

    rankings: list[list[uuid.UUID]] = []
    terms = [term for term in question.hint_terms if term.strip()]
    if terms:
        simple: ColumnElement[Any] = literal_column("'simple'::regconfig")
        query: ColumnElement[Any] = func.phraseto_tsquery(simple, terms[0])
        for term in terms[1:]:
            query = query.op("||")(func.phraseto_tsquery(simple, term))
        keyword = (
            base()
            .where(Chunk.lexemes.op("@@")(query))
            .order_by(func.ts_rank(Chunk.lexemes, query).desc(), Chunk.ordinal)
            .limit(settings.retrieval_candidates)
        )
        rankings.append(list((await session.execute(keyword)).scalars()))
    [vector] = await embed(
        embedder,
        embedder_url=settings.embedder_url,
        dim=settings.embedding_dim,
        batch_size=settings.embed_batch_size,
        texts=[_embedding_text(question)],
    )
    meaning = (
        base()
        .where(Chunk.embedding.isnot(None))
        .order_by(Chunk.embedding.cosine_distance(vector), Chunk.ordinal)
        .limit(settings.retrieval_candidates)
    )
    rankings.append(list((await session.execute(meaning)).scalars()))

    ids = list(dict.fromkeys(chunk_id for ranking in rankings for chunk_id in ranking))
    index = {chunk_id: position for position, chunk_id in enumerate(ids)}
    fused = fuse_rankings(
        [[index[c] for c in ranking] for ranking in rankings],
        candidates=settings.retrieval_candidates,
        rrf_k=settings.retrieval_rrf_k,
    )
    chosen = [ids[position] for position, _ in fused[:limit]]
    if not chosen:
        return []
    rows = {
        chunk.id: (chunk, document)
        for chunk, document in (
            await session.execute(
                select(Chunk, Document)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.id.in_(chosen))
            )
        ).all()
    }
    passages: list[_Passage] = []
    for chunk_id in chosen:
        chunk, document = rows[chunk_id]
        assert chunk.text is not None
        passages.append(
            _Passage(
                text=chunk.text,
                header=passage_header(
                    account_name=account.name,
                    document_title=document.title,
                    section=chunk.section,
                    date=(document.published_at or document.fetched_at).strftime("%Y-%m-%d"),
                ),
                language=document.language,
                chunk_id=chunk.id,
                title=document.title,
                url=document.url,
                published_at=document.published_at,
            )
        )
    return passages


def _escalation_question(question: _Question) -> EscalationQuestion:
    return EscalationQuestion(
        text=question.text,
        answer_type=question.answer_type,
        options=(
            None
            if question.options is None
            else [
                QuestionOption(
                    key=str(option["key"]),
                    label=str(option["label"]),
                    strength=FindingStrength(str(option["strength"])),
                )
                for option in question.options
            ]
        ),
    )


async def _ask(
    gateway: AiGateway,
    settings: AiGatewaySettings,
    question: _Question,
    passage: _Passage,
    account_name: str,
    context: AiCallContext,
) -> PreviewResult:
    """One passage through classification, escalation and evidence, as the SIGNAL step does."""
    specs = classifier_questions_for(
        question_id=question.id,
        account_name=account_name,
        question_text=question.text,
        answer_type=question.answer_type,
        options=question.options,
    )
    answers = await gateway.classify(
        ClassifierRequest(
            state=passage.text,
            context=passage.header,
            questions=[
                ClassifierQuestion(
                    id=spec.id,
                    kind=spec.answer_type,
                    text=spec.text,
                    options=(
                        None
                        if spec.options is None
                        else [ClassifierOption(key=o.key, label=o.label) for o in spec.options]
                    ),
                )
                for spec in specs
            ],
        ),
        context,
    )
    by_id = {answer.question_id: answer.probabilities for answer in answers}
    probabilities = by_id.get(question.id, {})
    if question.answer_type is SignalQuestionAnswerType.YES_NO:
        probabilities = merge_yes_no_probabilities(
            probabilities, by_id.get(f"{question.id}{SCALE_SUFFIX}", {})
        )
    mapping = map_answer(
        answer_type=question.answer_type, probabilities=probabilities, options=question.options
    )
    decision = route(
        mapping.p_positive,
        escalation_lower=settings.escalation_lower,
        escalation_upper=settings.escalation_upper,
    )

    def result(
        escalated: bool,
        strength: FindingStrength,
        quote: str | None = None,
        quote_en: str | None = None,
        rationale: str | None = None,
    ) -> PreviewResult:
        return PreviewResult(
            passage=passage.text,
            title=passage.title,
            url=passage.url,
            published_at=passage.published_at,
            p_positive=mapping.p_positive,
            escalated=escalated,
            strength=strength,
            quote=quote,
            quote_en=quote_en,
            rationale=rationale,
        )

    def valid(quote: str, quote_en: str | None, rationale: str) -> bool:
        return validate_quote(
            quote=quote,
            passage=passage.text,
            lang=passage.language,
            quote_en=quote_en,
            rationale=rationale,
            evidence_min_quote_chars=settings.evidence_min_quote_chars,
            evidence_max_quote_chars=settings.evidence_max_quote_chars,
            evidence_max_rationale_chars=settings.evidence_max_rationale_chars,
        ).valid

    if decision is Route.NEGATIVE:
        return result(False, FindingStrength.NONE)
    if decision is Route.ESCALATE:
        escalation = await gateway.escalate(
            EscalationInput(
                account_name=account_name,
                question=_escalation_question(question),
                passage=passage.text,
                language=passage.language,
                header=passage.header,
            ),
            context,
        )
        if post_escalation_route(escalation.strength) is Route.NEGATIVE:
            return result(True, FindingStrength.NONE)
        if escalation.quote is None or not valid(
            escalation.quote, escalation.quote_en, escalation.rationale or ""
        ):
            # EVIDENCE_FAILED: no evidence, no finding.
            return result(True, FindingStrength.NONE)
        return result(
            True,
            escalation.strength,
            escalation.quote,
            escalation.quote_en,
            escalation.rationale,
        )
    for _ in range(settings.evidence_max_attempts):
        evidence = await gateway.extract_evidence(
            EvidenceInput(
                account_name=account_name,
                question=_escalation_question(question),
                passage=passage.text,
                language=passage.language,
                header=passage.header,
                strength=mapping.candidate_strength,
            ),
            context,
        )
        if valid(evidence.quote, evidence.quote_en, evidence.rationale):
            return result(
                False,
                mapping.candidate_strength,
                evidence.quote,
                evidence.quote_en,
                evidence.rationale,
            )
    return result(False, FindingStrength.NONE)


async def preview_question(
    session: AsyncSession,
    request: PreviewRequest,
    *,
    gateway: AiGateway,
    embedder: httpx.AsyncClient,
    settings: AiGatewaySettings,
    max_passages: int,
    actor_id: uuid.UUID,
    now: datetime,
) -> list[PreviewResult]:
    """`API-14`: the results of the first `max_passages` passages (`PREVIEW_MAX_PASSAGES`).
    Raises `ServiceNotFound`, `QuestionNotFound`, `AccountNotFound`, `QuestionInvalid`, and the
    AI gateway's and embedder's errors."""
    await require_service(session, request.service_id)
    question = await _question(session, request)
    if request.account_id is not None:
        account = await session.get(Account, request.account_id)
        if account is None:
            raise AccountNotFound(f"No account {request.account_id}.")
        account_name = account.name
        passages = await _account_passages(
            session,
            account,
            question,
            settings=settings,
            embedder=embedder,
            limit=max_passages,
        )
    else:
        assert request.sample_text is not None
        account_name = PASTED_TEXT_ACCOUNT_NAME
        passages = await _pasted_passages(
            request.sample_text,
            question,
            settings=settings,
            embedder=embedder,
            limit=max_passages,
            now=now,
        )
    results: list[PreviewResult] = []
    for passage in passages:
        context = AiCallContext(
            entity_type="chunk" if passage.chunk_id else None,
            entity_id=passage.chunk_id,
            actor_id=actor_id,
        )
        results.append(await _ask(gateway, settings, question, passage, account_name, context))
    return results
