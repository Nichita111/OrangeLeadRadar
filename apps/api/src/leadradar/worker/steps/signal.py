"""SIGNAL worker step: the LangGraph signal graph.

[Signal graph](/architecture/services/worker.md#signal-graph),
[ADR-05](/architecture/adrs/adr-05-langgraph-only-for-the-signal-graph.md).

Each node writes its results before the next runs; the graph keeps no LangGraph
checkpoint — the database is the durable state.

Inputs to ``run_signal_step``:
- ``documents``: list of dicts with keys ``document_id``, ``account_id``, ``run_id``,
  ``source_type``, ``language``, ``plugin_code``, ``published_at``, ``fetched_at``,
  ``title``, ``text`` (first ``TRIAGE_CHARS`` characters already sliced by caller or
  in full when passage-level).
- ``service_descriptions``: mapping service_id → description text (for triage relevance
  questions).
- ``account``: ``{id, name, domain, country_code}``.
- ``passages``: list of dicts ``{chunk_id, document_id, text, section, ordinal}``.
- ``questions``: list of dicts ``{id, service_id, key, text, answer_type, options,
  revision, source_types}``.

The SIGNAL step does not fetch or chunk — it receives already-selected passages.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import (
    ClassificationStatus,
    DocumentTriageClassifier,
    FindingDecidedBy,
    FindingStatus,
    FindingStrength,
    ServiceStatus,
    SignalQuestionAnswerType,
    SignalQuestionStatus,
)
from leadradar.core.signal.classification import AnswerMapping, map_answer, observed_at
from leadradar.core.signal.escalation import Route, post_escalation_route, route
from leadradar.core.signal.evidence import validate_quote
from leadradar.core.signal.triage import (
    ABOUT_ACCOUNT_QUESTION_ID,
    RELEVANT_QUESTION_PREFIX,
    TriageResult,
    triage,
)
from leadradar.db.models.accounts import Account
from leadradar.db.models.configuration import Service, SignalQuestion
from leadradar.db.models.ingestion import Chunk, Document, Job, PipelineRun
from leadradar.db.models.signals import Classification, DocumentTriage, Finding
from leadradar.worker.ai.classifier import ClassifierQuestion, ClassifierRequest
from leadradar.worker.ai.gateway import (
    BudgetExhaustedError,
    FixtureMissingError,
    classify,
    escalate,
    extract_evidence,
)
from leadradar.worker.ai.llm import (
    EscalationInput,
    EscalationOutput,
    EvidenceInput,
    EvidenceOutput,
)

# ── State ──────────────────────────────────────────────────────────────────────


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
    fixture_mode: str
    fixture_dir: str
    triage_chars: int
    triage_about_min_p: float
    triage_relevance_min_p: float
    escalation_lower: float
    escalation_upper: float
    evidence_max_attempts: int
    evidence_min_quote_chars: int
    evidence_max_quote_chars: int
    evidence_max_rationale_chars: int
    daily_budget_eur: float
    usd_eur_rate: float

    # Outputs accumulated by nodes
    triage_results: dict[str, TriageResult] = field(default_factory=dict)  # doc_id → result
    # classification_id for pairs that reached POSITIVE
    finding_inputs: list[dict[str, Any]] = field(default_factory=list)


# ── Node: triage ────────────────────────────────────────────────────────────────


async def _node_triage(state: SignalBatch, session: AsyncSession) -> None:
    """Triage each document: call classifier, write ``document_triage`` row.

    Idempotent: skips documents that already have a ``document_triage`` row.
    """
    # Load already-triaged document ids
    existing_ids: set[str] = set()
    if state.documents:
        doc_ids = [uuid.UUID(d["document_id"]) for d in state.documents]
        stmt = select(DocumentTriage.document_id).where(DocumentTriage.document_id.in_(doc_ids))
        rows = await session.execute(stmt)
        existing_ids = {str(r) for r in rows.scalars()}

    for doc in state.documents:
        doc_id = doc["document_id"]
        if doc_id in existing_ids:
            continue

        is_own_source = _is_own_source(doc.get("plugin_code", ""))
        text_slice = (doc.get("text") or "")[: state.triage_chars]

        # Build classifier questions for triage
        triage_questions: list[ClassifierQuestion] = []
        if not is_own_source:
            ctx_name = state.account_name
            ctx_domain = state.account_domain
            ctx_country = state.account_country_code or ""
            triage_questions.append(
                ClassifierQuestion(
                    id=ABOUT_ACCOUNT_QUESTION_ID,
                    kind="YES_NO",
                    text=(
                        f"Is this text mainly about {ctx_name} ({ctx_domain}, {ctx_country}),"
                        f" not a different company with a similar name and not a passing mention?"
                    ),
                    options=None,
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

        answers_list = await classify(
            req,
            session=session,
            fixture_mode=state.fixture_mode,
            fixture_dir=state.fixture_dir,
            run_id=state.run_id,
        )
        answers: dict[str, dict[str, float]] = {
            a.question_id: a.probabilities for a in answers_list
        }

        result = triage(
            is_own_source=is_own_source,
            service_ids=state.service_ids,
            answers=answers,
            triage_about_min_p=state.triage_about_min_p,
            triage_relevance_min_p=state.triage_relevance_min_p,
        )
        state.triage_results[doc_id] = result

        # Derive service_relevance dict for storing
        service_relevance: dict[str, float] = {}
        for svc_id in state.service_ids:
            q_id = f"{RELEVANT_QUESTION_PREFIX}{svc_id}"
            probs = answers.get(q_id, {})
            service_relevance[svc_id] = probs.get("YES", 0.0)

        session.add(
            DocumentTriage(
                document_id=uuid.UUID(doc_id),
                classifier=DocumentTriageClassifier.LLM,
                about_account_p=result.about_account_p,
                service_relevance=service_relevance,
                outcome=result.outcome,
            )
        )

    await session.flush()


# ── Node: classify passages ─────────────────────────────────────────────────────


async def _node_classify(state: SignalBatch, session: AsyncSession) -> None:
    """Classify each passage against its applicable questions.

    One classifier call per passage.  Writes ``classification`` rows idempotently
    via the unique key ``(chunk_id, question_id, question_revision)``.
    """
    # Build lookup: document_id → source_type and triage kept-service set
    doc_source_type: dict[str, str] = {
        d["document_id"]: d.get("source_type", "NEWS") for d in state.documents
    }
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

        source_type = doc_source_type.get(doc_id, "NEWS")
        applicable_questions = [
            q
            for q in state.questions
            if (q["service_id"] in kept_services and source_type in q.get("source_types", []))
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

        answers_list = await classify(
            req,
            session=session,
            fixture_mode=state.fixture_mode,
            fixture_dir=state.fixture_dir,
            run_id=state.run_id,
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

            if initial_route is Route.NEGATIVE:
                status = ClassificationStatus.NEGATIVE
                strength = FindingStrength.NONE
                escalated = False
            elif initial_route is Route.POSITIVE:
                # Will proceed to evidence extraction
                status = ClassificationStatus.PENDING_LLM  # temporarily; evidence node updates
                strength = mapping.candidate_strength
                escalated = False
            else:  # ESCALATE
                status = ClassificationStatus.PENDING_LLM  # temporarily; escalation node updates
                strength = mapping.candidate_strength
                escalated = True

            clf = Classification(
                chunk_id=chunk_id,
                question_id=uuid.UUID(q["id"]),
                question_revision=int(q["revision"]),
                run_id=state.run_id,
                classifier=DocumentTriageClassifier.LLM,
                answer=merged,
                p_positive=mapping.p_positive,
                escalated=escalated,
                strength=strength if strength is not FindingStrength.NONE else None,
                status=status,
                evidence_retried=False,
            )
            session.add(clf)
            await session.flush()

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
                        "published_at": doc_data.get("published_at"),
                        "fetched_at": doc_data.get("fetched_at"),
                    }
                )

    await session.flush()


# ── Node: escalate/evidence ─────────────────────────────────────────────────────


async def _node_evidence(state: SignalBatch, session: AsyncSession) -> None:
    """Route, escalate and extract evidence for pending classifications.

    Writes final ``classification`` status and ``finding`` rows.
    """
    for item in state.finding_inputs:
        clf_id = uuid.UUID(item["classification_id"])
        q = item["question"]
        mapping: AnswerMapping = item["mapping"]
        passage_text: str = item["passage_text"]
        header: str = item["header"]
        language: str = item["language"]
        initial_route: Route = item["route"]
        published_at: datetime | None = item.get("published_at")
        fetched_at_raw = item.get("fetched_at") or datetime.now(tz=UTC)
        fetched_at: datetime = (
            fetched_at_raw
            if isinstance(fetched_at_raw, datetime)
            else datetime.fromisoformat(str(fetched_at_raw))
        )

        try:
            if initial_route is Route.POSITIVE:
                # Evidence extraction directly
                evidence_out = await _do_extract_evidence(
                    state=state,
                    session=session,
                    q=q,
                    passage_text=passage_text,
                    header=header,
                    language=language,
                    candidate_strength=mapping.candidate_strength,
                )
                if evidence_out is None:
                    # All attempts exhausted
                    await _update_classification(
                        session, clf_id, ClassificationStatus.EVIDENCE_FAILED, None
                    )
                    continue

                await _write_finding(
                    session=session,
                    clf_id=clf_id,
                    chunk_id=uuid.UUID(item["chunk_id"]),
                    account_id=state.account_id,
                    question=q,
                    strength=mapping.candidate_strength,
                    confidence=mapping.p_positive,
                    decided_by=FindingDecidedBy.CLASSIFIER,
                    option_key=mapping.option_key,
                    quote=evidence_out.quote,
                    quote_en=evidence_out.quote_en,
                    rationale=evidence_out.rationale,
                    observed_at_dt=observed_at(published_at, fetched_at),
                )
                await _update_classification(
                    session, clf_id, ClassificationStatus.POSITIVE, mapping.candidate_strength
                )

            else:  # ESCALATE
                esc_out = await _do_escalate(
                    state=state,
                    session=session,
                    q=q,
                    passage_text=passage_text,
                    header=header,
                    language=language,
                )
                if esc_out is None:
                    # Budget or unavailability — stays PENDING_LLM
                    continue

                post_route = post_escalation_route(esc_out.strength)
                if post_route is Route.NEGATIVE:
                    await _update_classification(
                        session, clf_id, ClassificationStatus.NEGATIVE, FindingStrength.NONE
                    )
                    continue

                # Positive from escalation — validate embedded quote
                if esc_out.quote is None:
                    await _update_classification(
                        session, clf_id, ClassificationStatus.EVIDENCE_FAILED, None
                    )
                    continue

                evidence_valid = validate_quote(
                    quote=esc_out.quote,
                    passage=passage_text,
                    lang=language,
                    quote_en=esc_out.quote_en,
                    rationale=esc_out.rationale or "",
                    evidence_min_quote_chars=state.evidence_min_quote_chars,
                    evidence_max_quote_chars=state.evidence_max_quote_chars,
                    evidence_max_rationale_chars=state.evidence_max_rationale_chars,
                )
                if not evidence_valid.valid:
                    # Escalation returned invalid quote — treat as EVIDENCE_FAILED
                    await _update_classification(
                        session, clf_id, ClassificationStatus.EVIDENCE_FAILED, None
                    )
                    continue

                await _write_finding(
                    session=session,
                    clf_id=clf_id,
                    chunk_id=uuid.UUID(item["chunk_id"]),
                    account_id=state.account_id,
                    question=q,
                    strength=esc_out.strength,
                    confidence=esc_out.confidence,
                    decided_by=FindingDecidedBy.LLM,
                    option_key=esc_out.option_key,
                    quote=esc_out.quote,
                    quote_en=esc_out.quote_en,
                    rationale=esc_out.rationale or "",
                    observed_at_dt=observed_at(published_at, fetched_at),
                )
                await _update_classification(
                    session, clf_id, ClassificationStatus.POSITIVE, esc_out.strength
                )

        except (BudgetExhaustedError, FixtureMissingError):
            # Stays PENDING_LLM; caller decides whether to mark run PARTIAL
            pass

    await session.flush()


# ── Helpers ────────────────────────────────────────────────────────────────────


def _is_own_source(plugin_code: str) -> bool:
    """True for sources that are about the account by construction."""
    return plugin_code in {
        "CAREERS",
        "CRUNCHBASE",
        "WEBSITE",
        "NEWSROOM",
        "INVESTOR_RELATIONS",
        "RSS_FEED",
        "RSS",
    }


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


async def _do_extract_evidence(
    *,
    state: SignalBatch,
    session: AsyncSession,
    q: dict[str, Any],
    passage_text: str,
    header: str,
    language: str,
    candidate_strength: FindingStrength,
) -> EvidenceOutput | None:
    """Try up to ``EVIDENCE_MAX_ATTEMPTS`` times to get a valid quote.

    Returns ``EvidenceOutput`` on success, ``None`` after all attempts fail.
    """
    for _ in range(state.evidence_max_attempts):
        inp = EvidenceInput(
            account_name=state.account_name,
            question={
                "text": q["text"],
                "answer_type": q["answer_type"],
                "options": q.get("options"),
            },
            passage=passage_text,
            language=language,
            header=header,
            strength=candidate_strength,
        )
        try:
            out = await extract_evidence(
                inp,
                session=session,
                fixture_mode=state.fixture_mode,
                fixture_dir=state.fixture_dir,
                run_id=state.run_id,
                daily_budget_eur=state.daily_budget_eur,
                usd_eur_rate=state.usd_eur_rate,
            )
        except (BudgetExhaustedError, FixtureMissingError):
            raise  # caller handles these
        valid = validate_quote(
            quote=out.quote,
            passage=passage_text,
            lang=language,
            quote_en=out.quote_en,
            rationale=out.rationale,
            evidence_min_quote_chars=state.evidence_min_quote_chars,
            evidence_max_quote_chars=state.evidence_max_quote_chars,
            evidence_max_rationale_chars=state.evidence_max_rationale_chars,
        )
        if valid.valid:
            return out
    return None  # all attempts exhausted


async def _do_escalate(
    *,
    state: SignalBatch,
    session: AsyncSession,
    q: dict[str, Any],
    passage_text: str,
    header: str,
    language: str,
) -> EscalationOutput | None:
    """Call escalation.  Returns ``None`` on budget exhaustion or missing fixture."""
    inp = EscalationInput(
        account_name=state.account_name,
        question={
            "text": q["text"],
            "answer_type": q["answer_type"],
            "options": q.get("options"),
        },
        passage=passage_text,
        language=language,
        header=header,
    )
    try:
        return await escalate(
            inp,
            session=session,
            fixture_mode=state.fixture_mode,
            fixture_dir=state.fixture_dir,
            run_id=state.run_id,
            daily_budget_eur=state.daily_budget_eur,
            usd_eur_rate=state.usd_eur_rate,
        )
    except (BudgetExhaustedError, FixtureMissingError):
        return None


async def _update_classification(
    session: AsyncSession,
    clf_id: uuid.UUID,
    status: ClassificationStatus,
    strength: FindingStrength | None,
) -> None:
    values: dict[str, Any] = {"status": status}
    if strength is not None:
        values["strength"] = strength if strength is not FindingStrength.NONE else None
    await session.execute(
        update(Classification).where(Classification.id == clf_id).values(**values)
    )


async def _write_finding(
    *,
    session: AsyncSession,
    clf_id: uuid.UUID,
    chunk_id: uuid.UUID,
    account_id: uuid.UUID,
    question: dict[str, Any],
    strength: FindingStrength,
    confidence: float,
    decided_by: FindingDecidedBy,
    option_key: str | None,
    quote: str,
    quote_en: str | None,
    rationale: str,
    observed_at_dt: datetime,
) -> None:
    session.add(
        Finding(
            account_id=account_id,
            question_id=uuid.UUID(question["id"]),
            question_revision=int(question["revision"]),
            classification_id=clf_id,
            chunk_id=chunk_id,
            strength=strength,
            confidence=confidence,
            decided_by=decided_by,
            option_key=option_key,
            quote=quote,
            quote_en=quote_en,
            rationale=rationale,
            observed_at=observed_at_dt,
            status=FindingStatus.ACTIVE,
        )
    )


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
    await _node_triage(batch, session)
    await _node_classify(batch, session)
    await _node_evidence(batch, session)


# ── Job-loop adapter ────────────────────────────────────────────────────────────


async def run_signal_job(
    session: AsyncSession,
    *,
    job: Job,
    run: PipelineRun,
    worker_instance_id: str,
    alert_max_age_days: int,
    settings: Any = None,
) -> None:
    """Adapter that wires a SIGNAL ``Job`` into the generic job-loop handler protocol.

    Loads account, services, questions, documents and passages from the database,
    builds a ``SignalBatch`` using config from ``settings`` (a ``WorkerSettings``),
    and calls ``run_signal_step``.

    Job payload keys (all optional, fallback to run context):
    - ``document_ids``: list of document id strings to process; if absent all
      non-duplicate documents of the run are used.
    - ``service_ids``: list of service id strings to include; if absent all
      ACTIVE services are used.
    - ``question_id``: single question id string for RECLASSIFY runs.
    """
    # Import here to avoid a cycle: settings lives in worker.settings which is fine.
    from leadradar.worker.settings import WorkerSettings

    cfg: WorkerSettings = settings if isinstance(settings, WorkerSettings) else WorkerSettings()

    account_id = run.account_id
    if account_id is None:
        raise ValueError(f"SIGNAL step: run {run.id} has no account_id")

    # Load account
    account = await session.get(Account, account_id)
    if account is None:
        raise ValueError(f"SIGNAL step: account {account_id} not found")

    # Load active services (or subset from payload)
    _svc_raw = job.payload.get("service_ids")
    raw_service_ids: list[str] = [str(s) for s in (_svc_raw if isinstance(_svc_raw, list) else [])]
    if raw_service_ids:
        svc_uuids = [uuid.UUID(s) for s in raw_service_ids]
        svc_stmt = select(Service).where(
            Service.id.in_(svc_uuids),
            Service.status == ServiceStatus.ACTIVE,
        )
    else:
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
        # Supersede old revision findings before classifying
        await supersede_old_revision_findings(
            session, question_id=reclassify_qid, current_revision=0
        )
        questions_rows = list((await session.execute(q_stmt)).scalars())
        if questions_rows:
            # Use the current revision of the question
            current_rev = max(q.revision for q in questions_rows)
            await supersede_old_revision_findings(
                session, question_id=reclassify_qid, current_revision=current_rev
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
        }
        for q in questions_rows
    ]

    # Load documents
    _doc_raw = job.payload.get("document_ids")
    raw_doc_ids: list[str] = [str(d) for d in (_doc_raw if isinstance(_doc_raw, list) else [])]
    if raw_doc_ids:
        doc_uuids = [uuid.UUID(d) for d in raw_doc_ids]
        doc_stmt = select(Document).where(
            Document.id.in_(doc_uuids),
            Document.duplicate_of_id.is_(None),
        )
    else:
        doc_stmt = select(Document).where(
            Document.run_id == run.id,
            Document.account_id == account_id,
            Document.duplicate_of_id.is_(None),
        )
    docs = list((await session.execute(doc_stmt)).scalars())

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
        fixture_mode=cfg.fixture_mode,
        fixture_dir=cfg.fixture_dir,
        triage_chars=cfg.triage_chars,
        triage_about_min_p=cfg.triage_about_min_p,
        triage_relevance_min_p=cfg.triage_relevance_min_p,
        escalation_lower=cfg.escalation_lower,
        escalation_upper=cfg.escalation_upper,
        evidence_max_attempts=cfg.evidence_max_attempts,
        evidence_min_quote_chars=cfg.evidence_min_quote_chars,
        evidence_max_quote_chars=cfg.evidence_max_quote_chars,
        evidence_max_rationale_chars=cfg.evidence_max_rationale_chars,
        daily_budget_eur=cfg.llm_daily_budget_eur,
        usd_eur_rate=cfg.usd_eur_rate,
    )

    await run_signal_step(session, batch=batch)
