"""[Classifier](/architecture/interfaces.md#classifier) port shapes and validation.

``API-62``: ``classify(ClassifierRequest) -> list[ClassifierAnswer]``

This module defines the request/answer Pydantic shapes and the probability-sum validation
rule.  The gateway (``gateway.py``) drives the actual I/O.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class ClassifierQuestion(BaseModel):
    """One question in a ``ClassifierRequest``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: str  # YES_NO | SCALE | CHOICE
    text: str
    options: list[dict[str, str]] | None = None


class ClassifierRequest(BaseModel):
    """[``ClassifierRequest``](/architecture/interfaces.md#classifierrequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: str
    context: str | None = None
    questions: list[ClassifierQuestion]


class ClassifierAnswer(BaseModel):
    """[``ClassifierAnswer``](/architecture/interfaces.md#classifieranswer)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: str
    probabilities: dict[str, float]

    @model_validator(mode="after")
    def _probabilities_sum_to_one(self) -> ClassifierAnswer:
        """Probabilities for one question must sum to 1 within 0.001.

        [API-62](/architecture/interfaces.md#classifier): *"The answer's probabilities for
        a question sum to 1 within 0.001; any other output is ``INVALID_OUTPUT``."*
        """
        total = sum(self.probabilities.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"probabilities sum to {total:.6f}, expected 1.0 ± 0.001 "
                f"(question_id={self.question_id!r})"
            )
        return self
