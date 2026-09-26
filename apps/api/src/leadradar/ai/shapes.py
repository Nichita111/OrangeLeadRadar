"""The gateway's port shapes: [Classifier shapes](/architecture/interfaces.md#classifier-shapes)
and [LLM shapes](/architecture/interfaces.md#llm-shapes), as Pydantic models, since they cross the
boundary to a provider. An output model's JSON schema is the `response_format` schema of its
role ([AI gateway](/architecture/services/worker.md#ai-gateway)), so every output field is
required and has no default."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from leadradar.core.enums import (
    ContactPersona,
    FindingStrength,
    OutreachDraftChannel,
    SignalQuestionAnswerType,
)

YES = "YES"
NO = "NO"


class _Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClassifierOption(_Shape):
    key: str
    label: str


class ClassifierQuestion(_Shape):
    """One question of a [`ClassifierRequest`](/architecture/interfaces.md#classifierrequest)."""

    id: str
    kind: SignalQuestionAnswerType
    text: str
    options: list[ClassifierOption] | None = None

    def answer_keys(self) -> list[str]:
        """The keys of the answer's `probabilities`: `YES` and `NO` for `YES_NO`, the option
        keys otherwise ([`ClassifierAnswer`](/architecture/interfaces.md#classifieranswer))."""
        if self.kind == SignalQuestionAnswerType.YES_NO:
            return [YES, NO]
        return [option.key for option in self.options or []]


class ClassifierRequest(_Shape):
    """[`ClassifierRequest`](/architecture/interfaces.md#classifierrequest)."""

    state: str
    context: str | None = None
    questions: list[ClassifierQuestion]


class ClassifierAnswer(_Shape):
    """[`ClassifierAnswer`](/architecture/interfaces.md#classifieranswer)."""

    question_id: str
    probabilities: dict[str, float]


class QuestionOption(_Shape):
    """One of a `CHOICE` question's `options` of [`signal_question`]
    (/architecture/sql-store.md#signal_question)."""

    key: str
    label: str
    strength: FindingStrength


class EscalationQuestion(_Shape):
    text: str
    answer_type: SignalQuestionAnswerType
    options: list[QuestionOption] | None


class EscalationInput(_Shape):
    """[`EscalationInput`](/architecture/interfaces.md#escalationinput)."""

    account_name: str
    question: EscalationQuestion
    passage: str
    language: str
    header: str


class EscalationOutput(_Shape):
    """[`EscalationOutput`](/architecture/interfaces.md#escalationoutput)."""

    strength: FindingStrength
    option_key: str | None
    confidence: float = Field(ge=0, le=1)
    quote: str | None
    quote_en: str | None
    rationale: str | None


class EvidenceInput(EscalationInput):
    """[`EvidenceInput`](/architecture/interfaces.md#evidenceinput)."""

    strength: FindingStrength


class EvidenceOutput(_Shape):
    """[`EvidenceOutput`](/architecture/interfaces.md#evidenceoutput)."""

    quote: str
    quote_en: str | None
    rationale: str


class DiscoveryInput(_Shape):
    """[`DiscoveryInput`](/architecture/interfaces.md#discoveryinput)."""

    service_description: str
    text: str
    language: str


class Organisation(_Shape):
    """[`Organisation`](/architecture/interfaces.md#organisation)."""

    name: str
    country_code: str | None
    website: str | None
    quote: str


class Organisations(_Shape):
    """The `extract_organisations` output: structured output needs an object at its root, so the
    `Organisation[]` of `API-65` is its one field."""

    organisations: list[Organisation]


class OutreachFinding(_Shape):
    id: str
    question_text: str
    quote: str
    quote_en: str | None
    observed_at: datetime
    url: str


class OutreachService(_Shape):
    name: str
    value_proposition: str


class OutreachContact(_Shape):
    full_name: str
    job_title: str
    persona: ContactPersona


class OutreachInput(_Shape):
    """[`OutreachInput`](/architecture/interfaces.md#outreachinput)."""

    account_name: str
    service: OutreachService
    findings: list[OutreachFinding]
    contact: OutreachContact | None
    channel: OutreachDraftChannel
    sender_name: str


class OutreachOutput(_Shape):
    """[`OutreachOutput`](/architecture/interfaces.md#outreachoutput)."""

    subject: str | None
    body: str
    cited_finding_ids: list[str]
