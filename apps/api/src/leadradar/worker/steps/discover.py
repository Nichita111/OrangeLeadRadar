"""The `DISCOVER` step ([Run lifecycle](/architecture/services/worker.md#run-lifecycle),
[Discovery](/architecture/rules.md#discovery)): one job per run (G1) that searches every available
news plug-in for its run's service, triages and extracts the organisations its kept documents
name, and writes the run's `PENDING` discovery candidates. As in [`fetch.py`](fetch.py), the
network is used outside a long-held transaction for the plug-in usage it records; the documents,
triage rows and candidates themselves are written in the step's own transaction, which commits
with the job ([Discovery](/architecture/rules.md#discovery) Invariants: never fetched, triaged or
scored as an account before acceptance)."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import any_, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.audit import AiCallContext
from leadradar.ai.errors import BudgetExhausted, UpstreamUnavailable
from leadradar.ai.fixtures import FixtureMissing
from leadradar.ai.shapes import ClassifierQuestion, ClassifierRequest, DiscoveryInput
from leadradar.core.discovery import (
    Company,
    KnownIdentities,
    OrganisationMention,
    news_query,
    propose,
    validate_organisation,
)
from leadradar.core.document_normalisation import normalise_item
from leadradar.core.enums import (
    DiscoveryCandidateOrigin,
    DiscoveryCandidateStatus,
    DocumentSourceType,
    DocumentTriageOutcome,
    PipelineRunStage,
    ScoringConfigStatus,
    SignalQuestionPolarity,
    SignalQuestionStatus,
    SourcePluginCode,
)
from leadradar.core.fetch_window import plugin_share
from leadradar.core.scoring.settings import ScoringSettings
from leadradar.core.signal.triage import RELEVANT_QUESTION_PREFIX, triage
from leadradar.db.models.accounts import Account, AccountAlias, DiscoveryCandidate
from leadradar.db.models.configuration import ScoringConfig, Service, SignalQuestion
from leadradar.db.models.ingestion import Document
from leadradar.db.models.signals import DocumentTriage
from leadradar.plugins.errors import PluginFetchFailed
from leadradar.plugins.gdelt import GdeltPlugin
from leadradar.plugins.http import CrawlHttpClient, build_crawl_client
from leadradar.plugins.shapes import RawItem
from leadradar.runs.queries import SourcePluginView, get_source_plugin
from leadradar.worker.queue import add_run_error, publish_run_state
from leadradar.worker.settings import WorkerSettings
from leadradar.worker.steps import StepContext, StepFailed

_MS_PER_MINUTE = 60_000
_NEWS_PLUGIN_CODES = (SourcePluginCode.GDELT, SourcePluginCode.NEWSAPI, SourcePluginCode.SERPAPI)


def _search_adapter(code: SourcePluginCode, settings: WorkerSettings) -> GdeltPlugin | None:
    """The `API-69` search adapter of `code`, or `None` when the plug-in has none yet."""
    if code is SourcePluginCode.GDELT:
        return GdeltPlugin(
            max_records=settings.gdelt_max_records,
            min_interval_s=settings.gdelt_min_interval_s,
            backoff_s=settings.gdelt_backoff_s,
        )
    return None


@dataclass(frozen=True)
class _Inputs:
    service_id: uuid.UUID
    service_description: str
    settings: ScoringSettings
    query: str
    news_plugins: list[SourcePluginView]
    crunchbase_available: bool
    accounts: KnownIdentities
    earlier_candidates: KnownIdentities


async def _read_inputs(session: AsyncSession, context: StepContext) -> _Inputs:
    """Discovery step (a): the service, its active settings and questions, the available
    plug-ins, and the service's earlier candidates, in one short transaction."""
    service_id = context.job.service_id
    if service_id is None:
        raise StepFailed("INTERNAL", f"The run of job {context.job.id} has no service to discover.")
    service = await session.get(Service, service_id)
    if service is None:
        raise StepFailed("INTERNAL", f"Run {context.job.run_id} has no service {service_id}.")

    scoring_config = (
        await session.execute(
            select(ScoringConfig).where(
                ScoringConfig.service_id == service_id,
                ScoringConfig.status == ScoringConfigStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if scoring_config is None:
        raise StepFailed("INTERNAL", f"Service {service_id} has no active scoring version.")
    settings = ScoringSettings.model_validate(scoring_config.settings)

    hint_terms: list[str] = []
    rows = await session.execute(
        select(SignalQuestion.hint_terms).where(
            SignalQuestion.service_id == service_id,
            SignalQuestion.status == SignalQuestionStatus.ACTIVE,
            SignalQuestion.polarity == SignalQuestionPolarity.POSITIVE,
            literal(DocumentSourceType.NEWS.value) == any_(SignalQuestion.source_types),
        )
    )
    for (terms,) in rows:
        hint_terms.extend(term for term in terms if term not in hint_terms)

    keys_configured = context.settings.plugin_keys_configured()
    news_plugins: list[SourcePluginView] = []
    for code in _NEWS_PLUGIN_CODES:
        plugin = await get_source_plugin(
            session, code, keys_configured=keys_configured, now=context.now
        )
        if plugin.available:
            news_plugins.append(plugin)
    crunchbase = await get_source_plugin(
        session, SourcePluginCode.CRUNCHBASE, keys_configured=keys_configured, now=context.now
    )

    account_domains = frozenset((await session.execute(select(Account.domain))).scalars())
    alias_names = frozenset((await session.execute(select(AccountAlias.normalised))).scalars())

    candidate_rows = (
        await session.execute(
            select(DiscoveryCandidate.domain, DiscoveryCandidate.normalised_name).where(
                DiscoveryCandidate.service_id == service_id
            )
        )
    ).all()
    candidate_domains = frozenset(domain for domain, _name in candidate_rows if domain is not None)
    candidate_names = frozenset(name for _domain, name in candidate_rows)

    return _Inputs(
        service_id=service_id,
        service_description=service.description,
        settings=settings,
        query=news_query(hint_terms),
        news_plugins=news_plugins,
        crunchbase_available=crunchbase.available,
        accounts=KnownIdentities(domains=account_domains, normalised_names=alias_names),
        earlier_candidates=KnownIdentities(
            domains=candidate_domains, normalised_names=candidate_names
        ),
    )


async def _record_plugin_outcome(
    context: StepContext, *, code: SourcePluginCode, client: CrawlHttpClient, error: str | None
) -> None:
    """Counts the requests this search made in today's `plugin_usage`, and sets the plug-in's
    `last_success_at` or `last_error`, in a transaction of its own that commits whatever the
    search's outcome, as `fetch._record_outcome` does."""
    from leadradar.worker.steps.fetch import _record_outcome  # the one implementation, not a copy

    if context.sessions is None:
        raise RuntimeError("The DISCOVER step requires a session factory")
    async with context.sessions() as session, session.begin():
        await _record_outcome(session, code=code, context=context, client=client, error=error)


async def _search_plugin(
    context: StepContext,
    plugin: SourcePluginView,
    query: str,
    *,
    since: datetime,
    until: datetime,
    max_items: int,
) -> tuple[list[RawItem], dict[str, object] | None]:
    """One news plug-in's search, network outside the step's transaction: builds its own crawl
    client, searches, then records its usage and outcome in a transaction of their own. Returns
    the items found and, on failure, the run error entry to add."""
    adapter = _search_adapter(plugin.code, context.settings)
    assert adapter is not None  # the caller only calls a plug-in `_search_adapter` covers
    settings = context.settings
    client = build_crawl_client(
        adapter=plugin.code.value,
        user_agent=settings.crawler_user_agent_or_default(),
        host_delay_ms=settings.crawl_host_delay_ms,
        min_interval_ms=_MS_PER_MINUTE // plugin.rate_limit_per_minute,
        requests_allowed=(
            None
            if plugin.daily_quota is None
            else max(0, plugin.daily_quota - plugin.requests_today)
        ),
        timeout_s=settings.http_timeout_s,
        clock=lambda: datetime.now(tz=UTC),
        fixture_mode=settings.fixture_mode,
        fixture_dir=settings.fixture_dir,
    )
    error: str | None = None
    code = "UPSTREAM_UNAVAILABLE"
    items: list[RawItem] = []
    try:
        items = await adapter.search(
            query, since=since, until=until, max_items=max_items, client=client
        )
    except PluginFetchFailed as failure:
        error = str(failure)
    except FixtureMissing as failure:
        error = str(failure)
        code = "FIXTURE_MISSING"
    finally:
        try:
            await _record_plugin_outcome(context, code=plugin.code, client=client, error=error)
        finally:
            await client.aclose()
    if error is None:
        return items, None
    return items, {
        "stage": PipelineRunStage.FETCH.value,
        "plugin_code": plugin.code.value,
        "code": code,
        "message": error,
    }


def _no_adapter_error(code: SourcePluginCode) -> dict[str, object]:
    return {
        "stage": PipelineRunStage.FETCH.value,
        "plugin_code": code.value,
        "code": "INTERNAL",
        "message": f"No search adapter for plug-in {code.value}.",
    }


@dataclass(frozen=True)
class _FetchedDocument:
    id: uuid.UUID
    text: str
    title: str | None
    published_at: datetime | None
    language: str


async def _fetch_news(
    context: StepContext, inputs: _Inputs
) -> tuple[list[RawItem], int, list[dict[str, object]]]:
    """Discovery step 2's search over every available news plug-in, split evenly
    (`DISCOVERY_MAX_DOCUMENTS`), each plug-in's error added to `errors` rather than failing the
    job (Plug-in availability). Returns the raw items in search order, the number of news sources
    searched, and the run errors to record."""
    errors: list[dict[str, object]] = []
    if inputs.crunchbase_available:
        errors.append(_no_adapter_error(SourcePluginCode.CRUNCHBASE))

    if not inputs.query or not inputs.news_plugins:
        return [], 0, errors

    settings = context.settings
    since = context.now - timedelta(days=settings.discovery_lookback_days)
    until = context.now
    share = plugin_share(settings.discovery_max_documents, len(inputs.news_plugins))

    items: list[RawItem] = []
    for plugin in inputs.news_plugins:
        if _search_adapter(plugin.code, settings) is None:
            errors.append(_no_adapter_error(plugin.code))
            continue
        found, error = await _search_plugin(
            context, plugin, inputs.query, since=since, until=until, max_items=share
        )
        items.extend(found)
        if error is not None:
            errors.append(error)
    return items, len(inputs.news_plugins), errors


async def _store_documents(
    context: StepContext, items: list[RawItem]
) -> tuple[list[_FetchedDocument], int]:
    """Normalises and stores each item as a `document` with no account, deduplicated by
    `content_hash` ([Document normalisation](/architecture/rules.md#document-normalisation),
    N-05): an identical document already stored is read back rather than duplicated. Returns the
    stored documents in the given (search) order and how many were newly stored."""
    session = context.session
    settings = context.settings
    purge_after: date = (context.now + timedelta(days=settings.document_retention_days)).date()
    documents: list[_FetchedDocument] = []
    new_count = 0
    for item in items:
        normalised = await asyncio.to_thread(
            normalise_item,
            url=item.url,
            content_type=item.content_type,
            body=item.body,
            title=item.title,
            min_document_chars=settings.min_document_chars,
        )
        if normalised is None:
            continue
        document_id = (
            await session.execute(
                insert(Document)
                .values(
                    account_id=None,
                    run_id=context.job.run_id,
                    plugin_code=item.plugin_code,
                    source_type=item.source_type,
                    url=item.url,
                    canonical_url=normalised.canonical_url,
                    title=item.title,
                    language=normalised.language,
                    published_at=item.published_at,
                    fetched_at=context.now,
                    content_hash=normalised.content_hash,
                    text=normalised.text,
                    purge_after=purge_after,
                )
                .on_conflict_do_nothing()
                .returning(Document.id)
            )
        ).scalar_one_or_none()
        if document_id is not None:
            new_count += 1
        else:
            document_id = (
                await session.execute(
                    select(Document.id).where(
                        Document.account_id.is_(None),
                        Document.content_hash == normalised.content_hash,
                    )
                )
            ).scalar_one()
        documents.append(
            _FetchedDocument(
                id=document_id,
                text=normalised.text,
                title=item.title,
                published_at=item.published_at,
                language=normalised.language,
            )
        )
    await session.flush()
    return documents, new_count


def _relevance_question(service_id: uuid.UUID, service_description: str) -> ClassifierQuestion:
    """[Discovery](/architecture/rules.md#discovery) step 2, G12: the account-free relevance
    question, with no `ABOUT_ACCOUNT` question and no context line."""
    return ClassifierQuestion(
        id=f"{RELEVANT_QUESTION_PREFIX}{service_id}",
        kind="YES_NO",
        text=(
            "Could this text matter for whether a company it reports on might need this "
            f"service: {service_description}?"
        ),
        options=None,
    )


def _triage_text(document: _FetchedDocument, triage_chars: int) -> str:
    text_slice = document.text[:triage_chars]
    return f"{document.title}\n{text_slice}" if document.title else text_slice


def _error_code(error: Exception) -> str:
    if isinstance(error, BudgetExhausted):
        return "BUDGET_EXHAUSTED"
    if isinstance(error, FixtureMissing):
        return "FIXTURE_MISSING"
    return "UPSTREAM_UNAVAILABLE"


async def _triage_and_extract(
    context: StepContext, inputs: _Inputs, documents: list[_FetchedDocument]
) -> tuple[int, list[Company], list[dict[str, object]]]:
    """Discovery step 2, stage `TRIAGE`: one classifier call per undecided document, then, for a
    `KEPT` one, one `extract_organisations` call. A failure of either skips only that document —
    no `document_triage` row is written for it, so a later run reconsiders it (Document change
    4) — and records `{stage TRIAGE, code}` in the run's `errors` (G12)."""
    assert context.gateway is not None
    gateway = context.gateway
    settings = context.settings
    question = _relevance_question(inputs.service_id, inputs.service_description)
    relevant_id = question.id

    documents_kept = 0
    companies: list[Company] = []
    errors: list[dict[str, object]] = []

    for document in documents:
        ai_context = AiCallContext(
            entity_type="document", entity_id=document.id, run_id=context.job.run_id
        )
        try:
            answers = await gateway.classify(
                ClassifierRequest(
                    state=_triage_text(document, settings.triage_chars), questions=[question]
                ),
                ai_context,
            )
        except (UpstreamUnavailable, BudgetExhausted, FixtureMissing) as error:
            errors.append(
                {
                    "stage": PipelineRunStage.TRIAGE.value,
                    "code": _error_code(error),
                    "message": str(error),
                }
            )
            continue

        relevance_p = next(
            (a.probabilities.get("YES", 0.0) for a in answers if a.question_id == relevant_id), 0.0
        )
        result = triage(
            is_own_source=True,  # no ABOUT_ACCOUNT question exists for discovery (G12)
            service_ids=[str(inputs.service_id)],
            answers={relevant_id: {"YES": relevance_p}},
            triage_about_min_p=settings.triage_about_min_p,
            triage_relevance_min_p=settings.triage_relevance_min_p,
        )
        service_relevance = {str(inputs.service_id): relevance_p}
        if result.outcome is not DocumentTriageOutcome.KEPT:
            context.session.add(
                DocumentTriage(
                    document_id=document.id,
                    classifier=gateway.classifier,
                    about_account_p=None,
                    service_relevance=service_relevance,
                    outcome=result.outcome,
                )
            )
            continue

        try:
            organisations = await gateway.extract_organisations(
                DiscoveryInput(
                    service_description=inputs.service_description,
                    text=document.text,
                    language=document.language,
                ),
                ai_context,
            )
        except (UpstreamUnavailable, BudgetExhausted, FixtureMissing) as error:
            errors.append(
                {
                    "stage": PipelineRunStage.TRIAGE.value,
                    "code": _error_code(error),
                    "message": str(error),
                }
            )
            continue

        context.session.add(
            DocumentTriage(
                document_id=document.id,
                classifier=gateway.classifier,
                about_account_p=None,
                service_relevance=service_relevance,
                outcome=DocumentTriageOutcome.KEPT,
            )
        )
        documents_kept += 1
        for organisation in organisations:
            mention = OrganisationMention(
                name=organisation.name,
                country_code=organisation.country_code,
                website=organisation.website,
                quote=organisation.quote,
                document_id=str(document.id),
                published_at=document.published_at,
            )
            company = validate_organisation(mention, document.text)
            if company is not None:
                companies.append(company)

    return documents_kept, companies, errors


async def _publish(
    context: StepContext, *, stage: PipelineRunStage, progress: dict[str, int]
) -> None:
    if context.sessions is None:
        raise RuntimeError("The DISCOVER step requires a session factory")
    async with context.sessions() as session, session.begin():
        await publish_run_state(
            session,
            job_id=context.job.id,
            run_id=context.job.run_id,
            stage=stage,
            progress=progress,
        )


async def run_discover_step(context: StepContext) -> None:
    """The `DISCOVER` step: one job over every available discovery source for one service, then
    ranks and caps its candidates ([Discovery](/architecture/rules.md#discovery))."""
    if context.sessions is None:
        raise RuntimeError("The DISCOVER step requires a session factory")

    async with context.sessions() as session, session.begin():
        inputs = await _read_inputs(session, context)

    items, news_searched, fetch_errors = await _fetch_news(context, inputs)
    documents, documents_new = await _store_documents(context, items)
    for error in fetch_errors:
        await add_run_error(
            context.session, job_id=context.job.id, run_id=context.job.run_id, error=error
        )
    await _publish(
        context,
        stage=PipelineRunStage.TRIAGE,
        progress={
            "documents_fetched": len(items),
            "documents_new": documents_new,
            "news_searched": news_searched,
        },
    )

    already_triaged: frozenset[uuid.UUID] = frozenset()
    if documents:
        document_ids = [document.id for document in documents]
        already_triaged = frozenset(
            (
                await context.session.execute(
                    select(DocumentTriage.document_id).where(
                        DocumentTriage.document_id.in_(document_ids)
                    )
                )
            ).scalars()
        )
    to_triage = [document for document in documents if document.id not in already_triaged]

    documents_kept, companies, triage_errors = await _triage_and_extract(context, inputs, to_triage)
    for error in triage_errors:
        await add_run_error(
            context.session, job_id=context.job.id, run_id=context.job.run_id, error=error
        )
    await context.session.flush()

    proposals = propose(
        companies,
        accounts=inputs.accounts,
        earlier_candidates=inputs.earlier_candidates,
        settings=inputs.settings,
        max_candidates=context.settings.discovery_max_candidates,
        now=context.now,
    )
    for proposal in proposals:
        context.session.add(
            DiscoveryCandidate(
                service_id=inputs.service_id,
                run_id=context.job.run_id,
                name=proposal.name,
                normalised_name=proposal.normalised_name,
                domain=proposal.domain,
                country_code=proposal.country_code,
                industry=None,
                employee_count=None,
                origin=DiscoveryCandidateOrigin.NEWS_MENTION,
                document_id=uuid.UUID(proposal.document_id),
                quote=proposal.quote,
                fit_estimate=proposal.fit_estimate,
                status=DiscoveryCandidateStatus.PENDING,
                decided_by=None,
                decided_at=None,
                reject_reason=None,
                account_id=None,
            )
        )
    await context.session.flush()
    await _publish(
        context,
        stage=PipelineRunStage.SCORE,
        progress={
            "documents_kept": documents_kept,
            "organisations_found": len(companies),
            "candidates": len(proposals),
        },
    )
