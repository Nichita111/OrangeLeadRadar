"""The AI gateway's typed errors ([AI gateway](/architecture/services/worker.md#ai-gateway)); the
api maps them once onto the envelope of [Conventions](/architecture/interfaces.md#conventions),
the worker records them in its run's `errors`. `FixtureMissing` lives with the fixture files in
`leadradar.ai.fixtures`, since source plug-ins raise it too."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

# `details.dependency` of `UPSTREAM_UNAVAILABLE`: the names of the Health checks.
AiDependency = Literal["classifier", "llm", "embedder"]

# `details.reason`: the call's `outcome`, or `NOT_CONFIGURED` for an unset key or model id.
UnavailableReason = Literal["TIMEOUT", "ERROR", "INVALID_OUTPUT", "NOT_CONFIGURED"]


class AiGatewayError(Exception):
    """Base of the gateway's errors."""


class InvalidOutput(Exception):
    """Inside the gateway only: a provider answered with output that is not the port's shape.
    The gateway records it as outcome `INVALID_OUTPUT` and raises `UpstreamUnavailable`."""


class UpstreamUnavailable(AiGatewayError):
    """`UPSTREAM_UNAVAILABLE`: the classifier or the LLM is unavailable or returned invalid
    output."""

    def __init__(self, dependency: AiDependency, reason: UnavailableReason, message: str) -> None:
        super().__init__(message)
        self.dependency: AiDependency = dependency
        self.reason: UnavailableReason = reason


class BudgetExhausted(AiGatewayError):
    """`BUDGET_EXHAUSTED`: the [Budget guard](/architecture/rules.md#budget-guard) stopped an LLM
    call."""

    def __init__(self, resets_at: datetime) -> None:
        super().__init__(f"The LLM daily budget is exhausted until {resets_at.isoformat()}")
        self.resets_at = resets_at
