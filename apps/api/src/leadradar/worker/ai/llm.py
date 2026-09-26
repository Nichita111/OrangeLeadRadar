"""[LLM](/architecture/interfaces.md#llm) port shapes for escalation and evidence extraction.

``API-63``: ``escalate(EscalationInput) -> EscalationOutput``
``API-64``: ``extract_evidence(EvidenceInput) -> EvidenceOutput``

Shapes only — the gateway (``gateway.py``) drives the actual I/O.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.core.enums import FindingStrength


class EscalationInput(BaseModel):
    """[``EscalationInput``](/architecture/interfaces.md#escalationinput)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    account_name: str
    question: dict[str, object]  # {text, answer_type, options}
    passage: str
    language: str
    header: str


class EscalationOutput(BaseModel):
    """[``EscalationOutput``](/architecture/interfaces.md#escalationoutput)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    strength: FindingStrength
    option_key: str | None = None
    confidence: float
    quote: str | None = None
    quote_en: str | None = None
    rationale: str | None = None


class EvidenceInput(BaseModel):
    """[``EvidenceInput``](/architecture/interfaces.md#evidenceinput).

    Extends ``EscalationInput`` with the classifier's candidate strength.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    account_name: str
    question: dict[str, object]
    passage: str
    language: str
    header: str
    strength: FindingStrength


class EvidenceOutput(BaseModel):
    """[``EvidenceOutput``](/architecture/interfaces.md#evidenceoutput)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quote: str
    quote_en: str | None = None
    rationale: str
