"""SIGNAL worker step: the LangGraph signal graph.

[Signal graph](/architecture/services/worker.md#signal-graph),
[ADR-05](/architecture/adrs/adr-05-langgraph-only-for-the-signal-graph.md).

Each node writes its results before the next runs; the graph keeps no LangGraph
checkpoint — the database is the durable state. ``run_signal_job`` loads the account's
documents to triage, its questions, and the pairs waiting for the LLM, and hands them to
``run_signal_step`` as a ``SignalBatch``. The step does not fetch or chunk: it works on the
passages the ``PROCESS`` step stored.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, cast

import httpx
from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from leadradar.ai.audit import AiCallContext
from leadradar.ai.embedder import embed
from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.ai.shapes import (
    ClassifierAnswer,
    ClassifierQuestion,
    ClassifierRequest,
    EscalationInput,
    EscalationOutput,
    EscalationQuestion,
    EvidenceInput,
    EvidenceOutput,
)
from leadradar.core.enums import (
    ClassificationStatus,
    DocumentTriageClassifier,
    DocumentTriageOutcome,
    FindingDecidedBy,
    FindingStatus,
    FindingStrength,
    PipelineRunStage,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionStatus,
)
from leadradar.core.signal.classification import (
    AnswerMapping,
    choice_option_strength,
    map_answer,
    observed_at,
)
from leadradar.core.signal.escalation import Route, post_escalation_route, route
from leadradar.core.signal.evidence import validate_quote
from leadradar.core.signal.triage import (
    ABOUT_ACCOUNT_QUESTION_ID,
    RELEVANT_QUESTION_PREFIX,
    TriageResult,
    about_account_question,
    is_own_source,
    triage,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document, Job, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.worker.queue import add_run_error, add_run_progress
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepFailed
from leadradar.worker.steps.passage_selection import select_document_passages

# ── State ──────────────────────────────────────────────────────────────────────


class SignalGateway(Protocol):
    @property
    def classifier(self) -> DocumentTriageClassifier: ...

    async def classify(
        self, request: ClassifierRequest, context: AiCallContext
    ) -> list[ClassifierAnswer]: ...

    async def escalate(
        self, role_input: EscalationInput, context: AiCallContext
    ) -> EscalationOutput: ...

    async def extract_evidence(
        self, role_input: EvidenceInput, context: AiCallContext
    ) -> EvidenceOutput: ...


@dataclass
class SignalBatch:
    """Mutable state of one SIGNAL graph execution."""

    # Inputs
    account_id: uuid.UUID
    account_name: str
    account_domain: str
    account_country_code: str | None
    run_id: uuid.UUID
    service_ids: list[str]
    service_descriptions: dict[str, str]  # service_id → description

    # Documents to triage (each dict has document_id, source_type, plugin_code, …)
    documents: list[dict[str, Any]]
    # Passages ready for classification (chunk_id, document_id, text, section, ordinal)
    passages: list[dict[str, Any]]
    # Questions to ask (id, service_id, key, text, answer_type, options, revision, source_types)
    questions: list[dict[str, Any]]

    # Runtime config
    gateway: SignalGateway
    triage_chars: int
    triage_about_min_p: float
    triage_relevance_min_p: float
    escalation_lower: float
    escalation_upper: float
    evidence_max_attempts: int
    evidence_min_quote_chars: int
    evidence_max_quote_chars: int
    evidence_max_rationale_chars: int
    #: Embeds question texts for passage selection (`API-67`).
    embed: Callable[[list[str]], Awaitable[list[list[float]]]]
    passages_per_question: int
    max_passages_per_document: int
    retrieval_candidates: int
    retrieval_rrf_k: int

    # Outputs accumulated by nodes
    triage_results: dict[str, TriageResult] = field(default_factory=dict)  # doc_id → result
    # classification_id for pairs that reached POSITIVE
    finding_inputs: list[dict[str, Any]] = field(default_factory=list)
    # (document_id, service_id) → ordinals of the passages selected for that service's questions
    selected: dict[tuple[str, str], set[int]] = field(default_factory=dict)
    # Pairs left waiting by an earlier job, resumed by the evidence node after `finding_inputs`
    pending_inputs: list[dict[str, Any]] = field(default_factory=list)
    #: What this job created, added to the run's `progress` at the end.
    counts: dict[str, int] = field(
        default_factory=lambda: {
            "documents_kept": 0,
            "pairs_classified": 0,
            "pairs_escalated": 0,
            "findings_created": 0,
            "pending_budget": 0,
        }
    )
    #: The job, for the run's `progress` and `errors`.
    job_id: uuid.UUID | None = None
    llm_unavailable: str | None = None


# ── Node: triage ────────────────────────────────────────────────────────────────


async def _node_triage(state: SignalBatch, session: AsyncSession) -> None:
    """Triage each document to triage: call the classifier, write its ``document_triage`` row."""
    for doc in state.documents:
        doc_id = doc["document_id"]

        own_source = is_own_source(doc["plugin_code"])
        text_slice = (doc.get("text") or "")[: state.triage_chars]
        if doc.get("title"):
            text_slice = f"{doc['title']}\n{text_slice}"

        # Build classifier questions for triage
        triage_questions: list[ClassifierQuestion] = []
        about_text = about_account_question(
            doc["plugin_code"],
            name=state.account_name,
            domain=state.account_domain,
            country=state.account_country_code or "",
        )
        if about_text is not None:
            triage_questions.append(
                ClassifierQuestion(
                    id=ABOUT_ACCOUNT_QUESTION_ID, kind="YES_NO", text=about_text, options=None
                )
            )

        for svc_id in state.service_ids:
            desc = state.service_descriptions.get(svc_id, "")
            triage_questions.append(
                ClassifierQuestion(
                    id=f"{RELEVANT_QUESTION_PREFIX}{svc_id}",
                    kind="YES_NO",
                    text=(
                        f"Could this text matter for whether {state.account_name}"
                        f" might need this service: {desc}?"
                    ),
                    options=None,
                )
            )

        context_line = (
            f"Company: {state.account_name} ({state.account_domain},"
            f" {state.account_country_code or ''})"
        )
        req = ClassifierRequest(
            state=text_slice,
            context=context_line,
            questions=triage_questions,
        )

        answers_list = await _classify_call(
            state,
            req,
            AiCallContext(entity_type="document", entity_id=uuid.UUID(doc_id), run_id=state.run_id),
        )
        answers: dict[str, dict[str, float]] = {
            a.question_id: a.probabilities for a in answers_list
        }

        result = triage(
            is_own_source=own_source,
            service_ids=state.service_ids,
            answers=answers,
            triage_about_min_p=state.triage_about_min_p,
            triage_relevance_min_p=state.triage_relevance_min_p,
        )
        state.triage_results[doc_id] = result
        if result.outcome is DocumentTriageOutcome.KEPT:
            state.counts["documents_kept"] += 1

        # Derive service_relevance dict for storing
        service_relevance: dict[str, float] = {}
        for svc_id in state.service_ids:
            q_id = f"{RELEVANT_QUESTION_PREFIX}{svc_id}"
            probs = answers.get(q_id, {})
            service_relevance[svc_id] = probs.get("YES", 0.0)

        session.add(
            DocumentTriage(
                document_id=uuid.UUID(doc_id),
                classifier=state.gateway.classifier,
                about_account_p=result.about_account_p,
                service_relevance=service_relevance,
                outcome=result.outcome,
            )
        )

    await session.flush()


# ── Node: select passages ───────────────────────────────────────────────────────


async def _node_select(state: SignalBatch, session: AsyncSession) -> None:
    """Select, for each kept document and each service it kept, the passages its applicable
    questions are asked on ([Passage selection]
    (/architecture/rules.md#chunking-and-passage-selection)): the only passage of a one-passage
    document, else the union of each question's best passages."""
    ordinals_by_document: dict[str, list[int]] = {}
    for passage in state.passages:
        ordinals_by_document.setdefault(passage["document_id"], []).append(passage["ordinal"])
    vectors: dict[str, list[float]] = {}

    for document in state.documents:
        document_id = document["document_id"]
        result = state.triage_results.get(document_id)
        ordinals = ordinals_by_document.get(document_id, [])
        if result is None or not ordinals:
            continue
        for service_id in result.kept_service_ids:
            if len(ordinals) == 1:
                state.selected[(document_id, service_id)] = set(ordinals)
                continue
            applicable = _applicable_questions(state, document["source_type"], {service_id})
            if not applicable:
                continue
            missing = [q for q in applicable if q["id"] not in vectors]
            if missing:
                try:
                    embedded = await state.embed(
                        [" ".join([q["text"], *q["hint_terms"]]) for q in missing]
                    )
                except UpstreamUnavailable as error:
                    raise StepFailed("UPSTREAM_UNAVAILABLE", str(error)) from error
                vectors.update(
                    {q["id"]: vector for q, vector in zip(missing, embedded, strict=True)}
                )
            state.selected[(document_id, service_id)] = set(
                await select_document_passages(
                    session,
                    document_id=uuid.UUID(document_id),
                    questions=[(q["id"], q["hint_terms"], vectors[q["id"]]) for q in applicable],
                    passages_per_question=state.passages_per_question,
                    candidates=state.retrieval_candidates,
                    rrf_k=state.retrieval_rrf_k,
                    max_passages_per_document=state.max_passages_per_document,
                )
            )


def _applicable_questions(
    state: SignalBatch, source_type: str, service_ids: Collection[str]
) -> list[dict[str, Any]]:
    """The questions of the given services whose `source_types` include the source type."""
    return [
        q
        for q in state.questions
        if q["service_id"] in service_ids and source_type in q["source_types"]
    ]


# ── Node: classify passages ─────────────────────────────────────────────────────


async def _node_classify(state: SignalBatch, session: AsyncSession) -> None:
    """Classify each passage against its applicable questions.

    One classifier call per passage.  Writes ``classification`` rows idempotently
    via the unique key ``(chunk_id, question_id, question_revision)``.
    """
    # Build lookup: document_id → source_type and triage kept-service set
    doc_source_type: dict[str, str] = {d["document_id"]: d["source_type"] for d in state.documents}
    doc_kept_services: dict[str, frozenset[str]] = {}
    for doc_id, tr in state.triage_results.items():
        doc_kept_services[doc_id] = tr.kept_service_ids

    for passage in state.passages:
        chunk_id_str = passage["chunk_id"]
        doc_id = passage["document_id"]
        passage_text = passage.get("text", "")
        section = passage.get("section")

        # Determine which questions to ask on this passage
        kept_services = doc_kept_services.get(doc_id, frozenset())
        if not kept_services:
            continue  # Document not kept or not triaged

        applicable_questions = [
            q
            for q in _applicable_questions(state, doc_source_type[doc_id], kept_services)
            if passage["ordinal"] in state.selected.get((doc_id, q["service_id"]), ())
        ]
        if not applicable_questions:
            continue

        # Skip questions already classified for this passage at current revision
        chunk_id = uuid.UUID(chunk_id_str)
        already_classified: set[tuple[str, int]] = set()
        for q in applicable_questions:
            stmt = select(Classification.id).where(
                Classification.chunk_id == chunk_id,
                Classification.question_id == uuid.UUID(q["id"]),
                Classification.question_revision == int(q["revision"]),
            )
            row = await session.execute(stmt)
            if row.scalar_one_or_none() is not None:
                already_classified.add((q["id"], int(q["revision"])))

        questions_to_ask = [
            q
            for q in applicable_questions
            if (q["id"], int(q["revision"])) not in already_classified
        ]
        if not questions_to_ask:
            continue

        # Build passage header
        doc = next((d for d in state.documents if d["document_id"] == doc_id), {})
        header = _build_passage_header(
            account_name=state.account_name,
            title=doc.get("title") or "",
            section=section,
            published_at=doc.get("published_at"),
            fetched_at=doc.get("fetched_at"),
        )

        # Build classifier questions
        clf_questions: list[ClassifierQuestion] = []
        for q in questions_to_ask:
            question_text = f"About {state.account_name}: {q['text']}"
            kind = q["answer_type"]
            opts: list[dict[str, str]] | None = None
            if kind == SignalQuestionAnswerType.SCALE.value:
                opts = [
                    {"key": "NONE", "label": "No signal"},
                    {"key": "WEAK", "label": "Weak"},
                    {"key": "MEDIUM", "label": "Medium"},
                    {"key": "STRONG", "label": "Strong"},
                ]
            elif kind == SignalQuestionAnswerType.YES_NO.value:
                # Also send the scale sub-question
                clf_questions.append(
                    ClassifierQuestion(
                        id=q["id"],
                        kind="YES_NO",
                        text=question_text,
                        options=None,
                    )
                )
                clf_questions.append(
                    ClassifierQuestion(
                        id=f"{q['id']}__SCALE",
                        kind="SCALE",
                        text="How strong is the evidence?",
                        options=[
                            {"key": "WEAK", "label": "Weak"},
                            {"key": "MEDIUM", "label": "Medium"},
                            {"key": "STRONG", "label": "Strong"},
                        ],
                    )
                )
                continue  # already appended both; skip the generic append below
            elif kind == SignalQuestionAnswerType.CHOICE.value:
                raw_opts = q.get("options") or []
                opts = [{"key": str(o["key"]), "label": str(o["label"])} for o in raw_opts]

            clf_questions.append(
                ClassifierQuestion(
                    id=q["id"],
                    kind=kind,
                    text=question_text,
                    options=opts,
                )
            )

        req = ClassifierRequest(
            state=passage_text,
            context=header,
            questions=clf_questions,
        )

        answers_list = await _classify_call(
            state,
            req,
            AiCallContext(
                entity_type="chunk", entity_id=uuid.UUID(chunk_id_str), run_id=state.run_id
            ),
        )
        answers_by_qid: dict[str, dict[str, float]] = {
            a.question_id: a.probabilities for a in answers_list
        }

        # Write classification rows and route
        for q in questions_to_ask:
            at = q["answer_type"]
            main_probs = answers_by_qid.get(q["id"], {})

            # For YES_NO, merge scale sub-question probabilities
            if at == SignalQuestionAnswerType.YES_NO.value:
                scale_probs = answers_by_qid.get(f"{q['id']}__SCALE", {})
                merged = {**main_probs, **scale_probs}
            else:
                merged = main_probs

            mapping: AnswerMapping = map_answer(
                answer_type=SignalQuestionAnswerType(at),
                probabilities=merged,
                options=q.get("options"),
            )

            # Determine initial status via routing
            initial_route = route(
                mapping.p_positive,
                escalation_lower=state.escalation_lower,
                escalation_upper=state.escalation_upper,
            )

            strength: FindingStrength | None = None  # null while PENDING_LLM
            if initial_route is Route.NEGATIVE:
                status = ClassificationStatus.NEGATIVE
                strength = FindingStrength.NONE
            else:  # the evidence node settles it
                status = ClassificationStatus.PENDING_LLM
            escalated = initial_route is Route.ESCALATE

            clf = Classification(
                chunk_id=chunk_id,
                question_id=uuid.UUID(q["id"]),
                question_revision=int(q["revision"]),
                run_id=state.run_id,
                classifier=state.gateway.classifier,
                answer=merged,
                p_positive=mapping.p_positive,
                escalated=escalated,
                strength=strength,
                status=status,
                evidence_retried=False,
            )
            session.add(clf)
            await session.flush()
            state.counts["pairs_classified"] += 1
            if escalated:
                state.counts["pairs_escalated"] += 1

            if initial_route in (Route.POSITIVE, Route.ESCALATE):
                # Queue for escalation/evidence in the next nodes
                doc_data = next((d for d in state.documents if d["document_id"] == doc_id), {})
                state.finding_inputs.append(
                    {
                        "classification_id": str(clf.id),
                        "chunk_id": chunk_id_str,
                        "doc_id": doc_id,
                        "question": q,
                        "mapping": mapping,
                        "passage_text": passage_text,
                        "header": header,
                        "language": doc_data.get("language", "en"),
                        "route": initial_route,
                        "was_failed": False,
                        "published_at": doc_data.get("published_at"),
                        "fetched_at": doc_data.get("fetched_at"),
                    }
                )

    await session.flush()


# ── Node: escalate/evidence ─────────────────────────────────────────────────────


async def _node_evidence(state: SignalBatch, session: AsyncSession) -> None:
    """Escalate and extract evidence for this job's new pairs, then for the pairs an earlier job
    left waiting; writes the final ``classification`` status and the ``finding`` rows."""
    for item in [*state.finding_inputs, *state.pending_inputs]:
        clf_id = uuid.UUID(item["classification_id"])
        if item["was_failed"]:
            await session.execute(
                update(Classification)
                .where(Classification.id == clf_id)
                .values(evidence_retried=True)
            )
        try:
            if item["route"] is Route.POSITIVE:
                await _resolve_positive(state, session, item)
            else:
                await _resolve_escalated(state, session, item)
        except BudgetExhausted:
            await _update_classification(session, clf_id, ClassificationStatus.PENDING_LLM, None)
            state.counts["pending_budget"] += 1
        except UpstreamUnavailable as error:
            await _update_classification(session, clf_id, ClassificationStatus.PENDING_LLM, None)
            state.llm_unavailable = state.llm_unavailable or str(error)
        except FixtureMissing as error:
            raise StepFailed("FIXTURE_MISSING", str(error)) from error

    await session.flush()


def _validate(
    state: SignalBatch,
    item: dict[str, Any],
    *,
    quote: str,
    quote_en: str | None,
    rationale: str,
) -> str | None:
    """The passage's own text at the quote's place when the quote is valid, else None."""
    return validate_quote(
        quote=quote,
        passage=item["passage_text"],
        lang=item["language"],
        quote_en=quote_en,
        rationale=rationale,
        evidence_min_quote_chars=state.evidence_min_quote_chars,
        evidence_max_quote_chars=state.evidence_max_quote_chars,
        evidence_max_rationale_chars=state.evidence_max_rationale_chars,
    ).span


async def _resolve_positive(
    state: SignalBatch, session: AsyncSession, item: dict[str, Any]
) -> None:
    q = item["question"]
    mapping: AnswerMapping = item["mapping"]
    clf_id = uuid.UUID(item["classification_id"])
    for _ in range(state.evidence_max_attempts):
        out = await state.gateway.extract_evidence(
            EvidenceInput(
                account_name=state.account_name,
                question=_escalation_question(q),
                passage=item["passage_text"],
                language=item["language"],
                header=item["header"],
                strength=mapping.candidate_strength,
            ),
            AiCallContext(run_id=state.run_id),
        )
        span = _validate(
            state, item, quote=out.quote, quote_en=out.quote_en, rationale=out.rationale
        )
        if span is not None:
            _write_finding(
                state,
                session,
                item,
                strength=mapping.candidate_strength,
                confidence=mapping.p_positive,
                decided_by=FindingDecidedBy.CLASSIFIER,
                option_key=mapping.option_key,
                quote=span,
                quote_en=out.quote_en,
                rationale=out.rationale,
            )
            await _update_classification(
                session, clf_id, ClassificationStatus.POSITIVE, mapping.candidate_strength
            )
            return
    await _update_classification(
        session, clf_id, ClassificationStatus.EVIDENCE_FAILED, mapping.candidate_strength
    )


async def _resolve_escalated(
    state: SignalBatch, session: AsyncSession, item: dict[str, Any]
) -> None:
    q = item["question"]
    clf_id = uuid.UUID(item["classification_id"])
    is_choice = q["answer_type"] == SignalQuestionAnswerType.CHOICE.value
    last_strength: FindingStrength | None = None
    for _ in range(state.evidence_max_attempts):
        out = await state.gateway.escalate(
            EscalationInput(
                account_name=state.account_name,
                question=_escalation_question(q),
                passage=item["passage_text"],
                language=item["language"],
                header=item["header"],
            ),
            AiCallContext(run_id=state.run_id),
        )
        if post_escalation_route(out.strength) is Route.NEGATIVE:
            await _update_classification(
                session, clf_id, ClassificationStatus.NEGATIVE, FindingStrength.NONE
            )
            return
        last_strength = out.strength
        strength = out.strength
        if is_choice:
            option_strength = choice_option_strength(q.get("options") or [], out.option_key)
            if option_strength is None:
                continue
            strength = option_strength
        if out.quote is None:
            continue
        rationale = out.rationale or ""
        span = _validate(state, item, quote=out.quote, quote_en=out.quote_en, rationale=rationale)
        if span is None:
            continue
        _write_finding(
            state,
            session,
            item,
            strength=strength,
            confidence=out.confidence,
            decided_by=FindingDecidedBy.LLM,
            option_key=out.option_key if is_choice else None,
            quote=span,
            quote_en=out.quote_en,
            rationale=rationale,
        )
        await _update_classification(session, clf_id, ClassificationStatus.POSITIVE, strength)
        return
    await _update_classification(
        session, clf_id, ClassificationStatus.EVIDENCE_FAILED, last_strength
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _classify_call(
    state: SignalBatch, request: ClassifierRequest, context: AiCallContext
) -> list[ClassifierAnswer]:
    """One classifier call; an unavailable classifier or a missing recording fails the job."""
    try:
        return await state.gateway.classify(request, context)
    except UpstreamUnavailable as error:
        raise StepFailed("UPSTREAM_UNAVAILABLE", str(error)) from error
    except FixtureMissing as error:
        raise StepFailed("FIXTURE_MISSING", str(error)) from error


def _escalation_question(q: dict[str, Any]) -> EscalationQuestion:
    return EscalationQuestion.model_validate(
        {"text": q["text"], "answer_type": q["answer_type"], "options": q.get("options")}
    )


def _build_passage_header(
    *,
    account_name: str,
    title: str,
    section: str | None,
    published_at: Any,
    fetched_at: Any,
) -> str:
    """Build the one-line passage header per [Chunking and passage selection]
    (/architecture/rules.md#chunking-and-passage-selection).

    Format: ``{account} · {title} · {section} · {date}``
    """
    parts = [account_name]
    if title:
        parts.append(title)
    if section:
        parts.append(section)
    date_val = published_at or fetched_at
    if date_val:
        if isinstance(date_val, datetime):
            parts.append(date_val.strftime("%Y-%m-%d"))
        else:
            parts.append(str(date_val)[:10])
    return " · ".join(parts)


async def _update_classification(
    session: AsyncSession,
    clf_id: uuid.UUID,
    status: ClassificationStatus,
    strength: FindingStrength | None,
) -> None:
    await session.execute(
        update(Classification)
        .where(Classification.id == clf_id)
        .values(status=status, strength=strength)
    )


def _write_finding(
    state: SignalBatch,
    session: AsyncSession,
    item: dict[str, Any],
    *,
    strength: FindingStrength,
    confidence: float,
    decided_by: FindingDecidedBy,
    option_key: str | None,
    quote: str,
    quote_en: str | None,
    rationale: str,
) -> None:
    question = item["question"]
    session.add(
        Finding(
            account_id=state.account_id,
            question_id=uuid.UUID(question["id"]),
            question_revision=int(question["revision"]),
            classification_id=uuid.UUID(item["classification_id"]),
            chunk_id=uuid.UUID(item["chunk_id"]),
            strength=strength,
            confidence=confidence,
            decided_by=decided_by,
            option_key=option_key,
            quote=quote,
            quote_en=quote_en,
            rationale=rationale,
            observed_at=observed_at(item["published_at"], item["fetched_at"]),
            status=FindingStatus.ACTIVE,
        )
    )
    state.counts["findings_created"] += 1


# ── Supersede findings of a previous revision (Reclassification) ───────────────


async def supersede_old_revision_findings(
    session: AsyncSession,
    *,
    question_id: uuid.UUID,
    current_revision: int,
) -> None:
    """Mark findings of older revisions ``SUPERSEDED``.

    Implements [Reclassification](/architecture/rules.md#reclassification) step 1:
    *"Mark the question's findings of an older revision ``SUPERSEDED``."*
    """
    await session.execute(
        update(Finding)
        .where(
            Finding.question_id == question_id,
            Finding.question_revision < current_revision,
            Finding.status == FindingStatus.ACTIVE,
        )
        .values(status=FindingStatus.SUPERSEDED)
    )


# ── Public entry point ──────────────────────────────────────────────────────────


async def run_signal_step(
    session: AsyncSession,
    *,
    batch: SignalBatch,
) -> None:
    """Execute the SIGNAL graph for one batch.

    Nodes run in order; each writes to the database before the next starts.
    An interrupted job resumes from what is already recorded.
    """
    await _set_stage(session, batch.run_id, PipelineRunStage.TRIAGE)
    await _node_triage(batch, session)
    await _set_stage(session, batch.run_id, PipelineRunStage.CLASSIFY)
    await _node_select(batch, session)
    await _node_classify(batch, session)
    await _set_stage(session, batch.run_id, PipelineRunStage.EVIDENCE)
    await _node_evidence(batch, session)
    if batch.job_id is not None:
        await add_run_progress(
            session, job_id=batch.job_id, run_id=batch.run_id, counts=batch.counts
        )
        if batch.llm_unavailable is not None:
            await add_run_error(
                session,
                job_id=batch.job_id,
                run_id=batch.run_id,
                error={
                    "stage": PipelineRunStage.EVIDENCE.value,
                    "code": "UPSTREAM_UNAVAILABLE",
                    "message": batch.llm_unavailable,
                },
            )


async def _set_stage(session: AsyncSession, run_id: uuid.UUID, stage: PipelineRunStage) -> None:
    await session.execute(update(PipelineRun).where(PipelineRun.id == run_id).values(stage=stage))


# ── Work waiting for a SIGNAL job ───────────────────────────────────────────────


def _documents_to_triage(account_id: uuid.UUID) -> Select[Document]:
    """The account's processed documents not yet triaged: non-duplicate, not purged, every
    passage embedded ([Run lifecycle](/architecture/services/worker.md#run-lifecycle))."""
    return select(Document).where(
        Document.account_id == account_id,
        Document.duplicate_of_id.is_(None),
        Document.purged_at.is_(None),
        ~exists().where(DocumentTriage.document_id == Document.id),
        ~exists().where(
            Chunk.document_id == Document.id, Chunk.text.is_not(None), Chunk.embedding.is_(None)
        ),
    )


def _pending_pairs(account_id: uuid.UUID) -> Select[Classification, Chunk, Document]:
    """The account's pairs waiting for the LLM at their question's current revision: `PENDING_LLM`,
    and `EVIDENCE_FAILED` until its one retry ([Escalation](/architecture/rules.md#escalation),
    [Evidence extraction](/architecture/rules.md#evidence-extraction))."""
    return (
        select(Classification, Chunk, Document)
        .join(Chunk, Chunk.id == Classification.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .join(SignalQuestion, SignalQuestion.id == Classification.question_id)
        .join(Service, Service.id == SignalQuestion.service_id)
        .where(
            Document.account_id == account_id,
            Chunk.text.is_not(None),
            Classification.question_revision == SignalQuestion.revision,
            SignalQuestion.status == SignalQuestionStatus.ACTIVE,
            Service.status == ServiceStatus.ACTIVE,
            or_(
                Classification.status == ClassificationStatus.PENDING_LLM,
                and_(
                    Classification.status == ClassificationStatus.EVIDENCE_FAILED,
                    Classification.evidence_retried.is_(False),
                ),
            ),
        )
    )


async def has_pending_signal_work(session: AsyncSession, account_id: uuid.UUID) -> bool:
    """True when the account has a document to triage or a pair waiting for the LLM."""
    return bool(
        await session.scalar(
            select(
                or_(
                    _documents_to_triage(account_id).exists(),
                    _pending_pairs(account_id).exists(),
                )
            )
        )
    )


def _pending_inputs(
    rows: list[tuple[Classification, Chunk, Document]],
    *,
    account_name: str,
    questions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """The evidence node's items for pairs left waiting: the candidate mapping is recomputed from
    the stored answer."""
    items: list[dict[str, Any]] = []
    for clf, chunk, doc in rows:
        q = questions[str(clf.question_id)]
        items.append(
            {
                "classification_id": str(clf.id),
                "chunk_id": str(chunk.id),
                "question": q,
                "mapping": map_answer(
                    answer_type=SignalQuestionAnswerType(q["answer_type"]),
                    probabilities=cast(dict[str, float], clf.answer),
                    options=q.get("options"),
                ),
                "passage_text": chunk.text or "",
                "header": _build_passage_header(
                    account_name=account_name,
                    title=doc.title or "",
                    section=chunk.section,
                    published_at=doc.published_at,
                    fetched_at=doc.fetched_at,
                ),
                "language": doc.language,
                "route": Route.ESCALATE if clf.escalated else Route.POSITIVE,
                "was_failed": clf.status is ClassificationStatus.EVIDENCE_FAILED,
                "published_at": doc.published_at,
                "fetched_at": doc.fetched_at,
            }
        )
    return items


# ── Job-loop adapter ────────────────────────────────────────────────────────────


async def run_signal_job(
    session: AsyncSession,
    *,
    job: Job,
    run: PipelineRun,
    settings: WorkerSettings,
    gateway: SignalGateway,
    embedder: httpx.AsyncClient,
) -> None:
    """Adapter that wires a SIGNAL ``Job`` into the generic job-loop handler protocol.

    Loads the account, the active services and questions, the account's documents to triage and
    the pairs waiting for the LLM, builds a ``SignalBatch`` from ``WorkerSettings`` and calls
    ``run_signal_step``. The job payload's optional ``question_id`` restricts the questions
    (RECLASSIFY runs).
    """
    cfg = settings

    account_id = run.account_id
    if account_id is None:
        raise ValueError(f"SIGNAL step: run {run.id} has no account_id")

    # Load account
    account = await session.get(Account, account_id)
    if account is None:
        raise ValueError(f"SIGNAL step: account {account_id} not found")

    svc_stmt = select(Service).where(Service.status == ServiceStatus.ACTIVE)
    services = list((await session.execute(svc_stmt)).scalars())
    service_ids = [str(svc.id) for svc in services]
    service_descriptions = {str(svc.id): svc.description for svc in services}

    # Load active signal questions for these services
    q_stmt = select(SignalQuestion).where(
        SignalQuestion.service_id.in_([svc.id for svc in services]),
        SignalQuestion.status == SignalQuestionStatus.ACTIVE,
    )
    # For RECLASSIFY: filter to one question
    reclassify_question_id_raw = job.payload.get("question_id")
    if reclassify_question_id_raw is not None:
        reclassify_qid = uuid.UUID(str(reclassify_question_id_raw))
        q_stmt = q_stmt.where(SignalQuestion.id == reclassify_qid)
        questions_rows = list((await session.execute(q_stmt)).scalars())
        if questions_rows:
            # Supersede findings of older revisions before classifying
            await supersede_old_revision_findings(
                session, question_id=reclassify_qid, current_revision=questions_rows[0].revision
            )
    else:
        questions_rows = list((await session.execute(q_stmt)).scalars())

    questions: list[dict[str, Any]] = [
        {
            "id": str(q.id),
            "service_id": str(q.service_id),
            "key": q.key,
            "text": q.text,
            "answer_type": q.answer_type.value,
            "options": q.options if isinstance(q.options, list) else None,
            "revision": q.revision,
            "source_types": list(q.source_types),
            "hint_terms": list(q.hint_terms),
        }
        for q in questions_rows
    ]

    docs = list((await session.execute(_documents_to_triage(account_id))).scalars())

    documents: list[dict[str, Any]] = [
        {
            "document_id": str(doc.id),
            "account_id": str(doc.account_id),
            "run_id": str(doc.run_id),
            "source_type": doc.source_type.value,
            "language": doc.language,
            "plugin_code": doc.plugin_code.value,
            "published_at": doc.published_at,
            "fetched_at": doc.fetched_at,
            "title": doc.title,
            "text": doc.text,
        }
        for doc in docs
    ]

    # Load passages (all chunks) for those documents (decision G1)
    doc_ids_for_chunks = [doc.id for doc in docs]
    passages: list[dict[str, Any]] = []
    if doc_ids_for_chunks:
        chunk_stmt = select(Chunk).where(Chunk.document_id.in_(doc_ids_for_chunks))
        chunks = list((await session.execute(chunk_stmt)).scalars())
        passages = [
            {
                "chunk_id": str(c.id),
                "document_id": str(c.document_id),
                "text": c.text or "",
                "section": c.section,
                "ordinal": c.ordinal,
            }
            for c in chunks
        ]

    pending_rows = [
        (clf, chunk, doc)
        for clf, chunk, doc in (
            await session.execute(
                _pending_pairs(account_id).where(
                    Classification.question_id.in_([q.id for q in questions_rows])
                )
            )
        )
    ]

    async def embed_texts(texts: list[str]) -> list[list[float]]:
        return await embed(
            embedder,
            embedder_url=cfg.embedder_url,
            dim=cfg.embedding_dim,
            batch_size=cfg.embed_batch_size,
            texts=texts,
        )

    batch = SignalBatch(
        account_id=account_id,
        account_name=account.name,
        account_domain=account.domain,
        account_country_code=account.country_code,
        run_id=run.id,
        service_ids=service_ids,
        service_descriptions=service_descriptions,
        documents=documents,
        passages=passages,
        questions=questions,
        gateway=gateway,
        triage_chars=cfg.triage_chars,
        triage_about_min_p=cfg.triage_about_min_p,
        triage_relevance_min_p=cfg.triage_relevance_min_p,
        escalation_lower=cfg.escalation_lower,
        escalation_upper=cfg.escalation_upper,
        evidence_max_attempts=cfg.evidence_max_attempts,
        evidence_min_quote_chars=cfg.evidence_min_quote_chars,
        evidence_max_quote_chars=cfg.evidence_max_quote_chars,
        evidence_max_rationale_chars=cfg.evidence_max_rationale_chars,
        embed=embed_texts,
        passages_per_question=cfg.passages_per_question,
        max_passages_per_document=cfg.max_passages_per_document,
        retrieval_candidates=cfg.retrieval_candidates,
        retrieval_rrf_k=cfg.retrieval_rrf_k,
        pending_inputs=_pending_inputs(
            pending_rows, account_name=account.name, questions={q["id"]: q for q in questions}
        ),
        job_id=job.id,
    )

    await run_signal_step(session, batch=batch)
