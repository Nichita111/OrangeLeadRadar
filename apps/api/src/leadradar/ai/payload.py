"""Typed reading of a provider's JSON answer: every unexpected shape is `InvalidOutput`, never a
default value ([Errors](/guidelines/coding.md#errors))."""

from __future__ import annotations

from dataclasses import dataclass

from leadradar.ai.errors import InvalidOutput


@dataclass(frozen=True)
class Usage:
    """What a provider reported a call used; each figure None when it did not say."""

    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None


NO_USAGE = Usage(input_tokens=None, output_tokens=None, cost_usd=None)


def read_usage(payload: object, *, input_key: str, output_key: str) -> Usage:
    """`usage` of a response; a missing or malformed `usage` reports nothing rather than failing
    the call, whose output is judged on its own."""
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return NO_USAGE
    input_tokens = optional_number(usage.get(input_key))
    output_tokens = optional_number(usage.get(output_key))
    return Usage(
        input_tokens=None if input_tokens is None else int(input_tokens),
        output_tokens=None if output_tokens is None else int(output_tokens),
        cost_usd=optional_number(usage.get("cost")),
    )


def as_object(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise InvalidOutput(f"{what} is not a JSON object")
    return {str(key): item for key, item in value.items()}


def as_list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise InvalidOutput(f"{what} is not a JSON array")
    return list(value)


def as_probability(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 1:
        raise InvalidOutput(f"{what} is not a probability between 0 and 1")
    return float(value)


def optional_number(value: object) -> float | None:
    """A usage figure: a number, or None when the provider did not report it."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
