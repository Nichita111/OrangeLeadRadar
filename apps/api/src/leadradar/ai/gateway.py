"""The [AI gateway](/architecture/services/worker.md#ai-gateway): the one module through which the
worker and the api make every classifier (`API-62`) and LLM (`API-63` to `API-66`) call. For each
call it checks the [Budget guard](/architecture/rules.md#budget-guard) when the call goes to
OpenRouter's chat completions API, sends it through the fixture-aware client with its timeout
and transport retries under the `AI_CONCURRENCY` semaphore, validates the output against the
port's shape, and writes one `AI_CALL` audit row in its own transaction, so the row stays when
the caller's work rolls back and the next budget check sees its cost."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from leadradar.ai.audit import AiCallContext, AiCallRecord, append_ai_call, read_llm_spend_eur
from leadradar.ai.classifier import (
    ClassifierAdapter,
    JevClassifier,
    LlmClassifier,
    ProviderRequest,
    validate_answers,
)
from leadradar.ai.errors import (
    AiDependency,
    BudgetExhausted,
    InvalidOutput,
    UnavailableReason,
    UpstreamUnavailable,
)
from leadradar.ai.fixtures import ADAPTER_EXTENSION, build_fixture_client
from leadradar.ai.openrouter import chat_body, chat_completions_url, chat_content, output_schema
from leadradar.ai.payload import NO_USAGE, Usage, read_usage
from leadradar.ai.prompts import Prompt, load_prompts
from leadradar.ai.settings import AiGatewaySettings
from leadradar.ai.shapes import (
    ClassifierAnswer,
    ClassifierRequest,
    DiscoveryInput,
    EscalationInput,
    EscalationOutput,
    EvidenceInput,
    EvidenceOutput,
    Organisation,
    Organisations,
    OutreachInput,
    OutreachOutput,
)
from leadradar.clock import build_clock
from leadradar.core.budget_guard import (
    budget_day_start,
    budget_resets_at,
    call_cost_eur,
    is_budget_exhausted,
)
from leadradar.core.enums import AiCallOutcome, AiCallProvider, AiRole, DocumentTriageClassifier

T = TypeVar("T")
OutputT = TypeVar("OutputT", bound=BaseModel)


def build_ai_http_client(
    settings: AiGatewaySettings, live: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """The gateway's client for `FIXTURE_MODE`; `live` replaces the network transport (tests)."""
    return build_fixture_client(settings.fixture_mode, settings.fixture_dir, live)


def _dependency(role: AiRole) -> AiDependency:
    return "classifier" if role == AiRole.CLASSIFIER else "llm"


def _reason(outcome: AiCallOutcome) -> UnavailableReason:
    if outcome == AiCallOutcome.TIMEOUT:
        return "TIMEOUT"
    if outcome == AiCallOutcome.INVALID_OUTPUT:
        return "INVALID_OUTPUT"
    return "ERROR"


class AiGateway:
    """Holds the settings, the client, the audit session factory, the prompts in use and the
    `AI_CONCURRENCY` semaphore of one process."""

    def __init__(
        self,
        settings: AiGatewaySettings,
        *,
        http: httpx.AsyncClient,
        sessions: async_sessionmaker[AsyncSession],
        prompts: dict[AiRole, Prompt] | None = None,
    ) -> None:
        self._settings = settings
        self._http = http
        self._sessions = sessions
        self._prompts = load_prompts() if prompts is None else prompts
        self._semaphore = asyncio.Semaphore(settings.ai_concurrency)
        self._clock = build_clock(settings)

    @property
    def classifier(self) -> DocumentTriageClassifier:
        """The adapter `CLASSIFIER_PROVIDER` selects; recorded on every classification."""
        return self._settings.classifier_provider

    def _now(self) -> datetime:
        return self._clock()

    # -- ports -------------------------------------------------------------------------------

    async def classify(
        self, request: ClassifierRequest, context: AiCallContext
    ) -> list[ClassifierAnswer]:
        """`API-62`: every question of the request answered in one call."""
        adapter = self._classifier_adapter()
        return await self._call(
            role=AiRole.CLASSIFIER,
            provider_request=adapter.build(request),
            items=len(request.questions),
            context=context,
            usage=adapter.usage,
            parse=lambda payload: validate_answers(request, adapter.answers(request, payload)),
        )

    async def escalate(
        self, role_input: EscalationInput, context: AiCallContext
    ) -> EscalationOutput:
        """`API-63`, on `LLM_EVIDENCE_MODEL`."""
        return await self._generate(
            AiRole.ESCALATION,
            self._settings.llm_evidence_model,
            role_input,
            EscalationOutput,
            1,
            context,
        )

    async def extract_evidence(
        self, role_input: EvidenceInput, context: AiCallContext
    ) -> EvidenceOutput:
        """`API-64`, on `LLM_EVIDENCE_MODEL`."""
        return await self._generate(
            AiRole.EVIDENCE,
            self._settings.llm_evidence_model,
            role_input,
            EvidenceOutput,
            1,
            context,
        )

    async def extract_organisations(
        self, role_input: DiscoveryInput, context: AiCallContext
    ) -> list[Organisation]:
        """`API-65`, on `LLM_EVIDENCE_MODEL`."""
        output = await self._generate(
            AiRole.DISCOVERY_EXTRACTION,
            self._settings.llm_evidence_model,
            role_input,
            Organisations,
            1,
            context,
        )
        return output.organisations

    async def draft_outreach(
        self, role_input: OutreachInput, context: AiCallContext
    ) -> OutreachOutput:
        """`API-66`, on `LLM_OUTREACH_MODEL`."""
        return await self._generate(
            AiRole.OUTREACH,
            self._settings.llm_outreach_model,
            role_input,
            OutreachOutput,
            len(role_input.findings),
            context,
        )

    # -- the per-call pipeline ---------------------------------------------------------------

    def _require_model(self, model: str | None, role: AiRole, key: str) -> str:
        if model is None:
            raise UpstreamUnavailable(_dependency(role), "NOT_CONFIGURED", f"{key} is not set")
        return model

    def _classifier_adapter(self) -> ClassifierAdapter:
        if self._settings.classifier_provider == DocumentTriageClassifier.JEV:
            return JevClassifier(
                model=self._settings.jev_model, decisions_url=self._settings.jev_decisions_url
            )
        return LlmClassifier(
            model=self._require_model(
                self._settings.llm_classifier_model, AiRole.CLASSIFIER, "LLM_CLASSIFIER_MODEL"
            ),
            openrouter_base_url=self._settings.openrouter_base_url,
            prompt=self._prompts[AiRole.CLASSIFIER],
        )

    async def _generate(
        self,
        role: AiRole,
        model: str | None,
        role_input: BaseModel,
        output_model: type[OutputT],
        items: int,
        context: AiCallContext,
    ) -> OutputT:
        model_key = "LLM_OUTREACH_MODEL" if role == AiRole.OUTREACH else "LLM_EVIDENCE_MODEL"
        chosen_model = self._require_model(model, role, model_key)
        prompt = self._prompts[role]
        provider_request = ProviderRequest(
            provider=AiCallProvider.OPENROUTER,
            model=chosen_model,
            prompt_version=prompt.version,
            url=chat_completions_url(self._settings.openrouter_base_url),
            body=chat_body(
                model=chosen_model,
                prompt=prompt,
                role_input=role_input,
                schema_name=output_model.__name__,
                schema=output_schema(output_model),
            ),
        )

        def parse(payload: object) -> OutputT:
            try:
                return output_model.model_validate(chat_content(payload))
            except ValidationError as error:
                raise InvalidOutput(f"The {role.value} output is not its shape") from error

        return await self._call(
            role=role,
            provider_request=provider_request,
            items=items,
            context=context,
            usage=lambda payload: read_usage(
                payload, input_key="prompt_tokens", output_key="completion_tokens"
            ),
            parse=parse,
        )

    async def _check_budget(self, at: datetime) -> None:
        day_start = budget_day_start(at)
        resets_at = budget_resets_at(at)
        async with self._sessions() as session:
            spent = await read_llm_spend_eur(session, since=day_start, until=resets_at)
        if is_budget_exhausted(
            spent_today_eur=spent, daily_budget_eur=self._settings.llm_daily_budget_eur
        ):
            raise BudgetExhausted(resets_at)

    async def _call(
        self,
        *,
        role: AiRole,
        provider_request: ProviderRequest,
        items: int,
        context: AiCallContext,
        usage: Callable[[object], Usage],
        parse: Callable[[object], T],
    ) -> T:
        settings = self._settings
        dependency = _dependency(role)
        replay = settings.fixture_mode == "replay"
        if settings.openrouter_api_key is None and not replay:
            raise UpstreamUnavailable(dependency, "NOT_CONFIGURED", "OPENROUTER_API_KEY is not set")
        occurred_at = self._now()
        if provider_request.provider == AiCallProvider.OPENROUTER:
            await self._check_budget(occurred_at)

        timeout_s = (
            settings.classifier_timeout_s
            if role == AiRole.CLASSIFIER
            else settings.ai_call_timeout_s
        )
        started = time.perf_counter()
        call_usage = NO_USAGE
        result: T | None = None
        try:
            async with self._semaphore:
                response = await self._send(provider_request, timeout_s)
        except httpx.TimeoutException:
            outcome = AiCallOutcome.TIMEOUT
        except httpx.TransportError:
            outcome = AiCallOutcome.ERROR
        else:
            outcome, call_usage, result = self._read(response, usage, parse)
        latency_ms = round((time.perf_counter() - started) * 1000)

        record = AiCallRecord(
            ai_role=role,
            provider=provider_request.provider,
            model=provider_request.model,
            prompt_version=provider_request.prompt_version,
            items=items,
            input_tokens=call_usage.input_tokens,
            output_tokens=call_usage.output_tokens,
            cost_eur=call_cost_eur(
                usage_cost_usd=call_usage.cost_usd, usd_eur_rate=settings.usd_eur_rate
            ),
            latency_ms=latency_ms,
            outcome=outcome,
            fixture=replay,
        )
        async with self._sessions() as session, session.begin():
            await append_ai_call(session, occurred_at=occurred_at, context=context, record=record)

        if result is None:
            raise UpstreamUnavailable(
                dependency, _reason(outcome), f"The {role.value} call ended {outcome.value}"
            )
        return result

    def _read(
        self,
        response: httpx.Response,
        usage: Callable[[object], Usage],
        parse: Callable[[object], T],
    ) -> tuple[AiCallOutcome, Usage, T | None]:
        if not response.is_success:
            return AiCallOutcome.ERROR, NO_USAGE, None
        try:
            payload: object = response.json()
        except ValueError:
            return AiCallOutcome.INVALID_OUTPUT, NO_USAGE, None
        call_usage = usage(payload)
        try:
            return AiCallOutcome.OK, call_usage, parse(payload)
        except InvalidOutput:
            return AiCallOutcome.INVALID_OUTPUT, call_usage, None

    async def _send(self, provider_request: ProviderRequest, timeout_s: float) -> httpx.Response:
        """Retries a transport error, `429` or `5xx` up to `AI_TRANSPORT_RETRIES` times after
        `AI_TRANSPORT_BACKOFF_MS × 2^(retry − 1)`; the last attempt's answer or error stands."""
        settings = self._settings
        headers = (
            {}
            if settings.openrouter_api_key is None
            else {"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"}
        )
        retry = 0
        while True:
            try:
                response = await self._http.post(
                    provider_request.url,
                    json=provider_request.body,
                    headers=headers,
                    timeout=timeout_s,
                    extensions={ADAPTER_EXTENSION: provider_request.provider.value},
                )
            except httpx.TransportError:
                if retry >= settings.ai_transport_retries:
                    raise
            else:
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable or retry >= settings.ai_transport_retries:
                    return response
            retry += 1
            await asyncio.sleep(settings.ai_transport_backoff_ms / 1000 * 2 ** (retry - 1))
