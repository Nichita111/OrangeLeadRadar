"""[Account attributes](/architecture/rules.md#account-attributes) (`S-ING-06`): the precedence
that decides whether a Crunchbase- or classifier-derived value may write an [`account`]
(/architecture/sql-store.md#account) column, and reading the classified operational-complexity
level off a classifier answer. Pure functions; the capability that applies them to a loaded
account row is [`leadradar.accounts.attributes`](../accounts/attributes.py)."""

from __future__ import annotations

from leadradar.core.enums import AccountOperationalComplexity

#: `MANUAL > CRUNCHBASE > CLASSIFIER` ([Account attributes]
#: (/architecture/rules.md#account-attributes) Precedence), as the three origins `account`
#: `attribute_origin` records them.
ATTRIBUTE_PRECEDENCE: dict[str, int] = {"CLASSIFIER": 0, "CRUNCHBASE": 1, "MANUAL": 2}


def should_write_attribute(current_origin: str | None, new_origin: str) -> bool:
    """[Account attributes](/architecture/rules.md#account-attributes) Precedence: "A value is
    written only when the attribute is null or its `attribute_origin` is of lower precedence"."""
    if current_origin is None:
        return True
    return ATTRIBUTE_PRECEDENCE[new_origin] > ATTRIBUTE_PRECEDENCE[current_origin]


def operational_complexity_from_probabilities(
    probabilities: dict[str, float], min_p: float
) -> AccountOperationalComplexity | None:
    """[Account attributes](/architecture/rules.md#account-attributes) Operational complexity:
    the most probable level, when its probability is at least `min_p` (`ATTRIBUTE_MIN_P`);
    `None` when no level reaches it, leaving the attribute unknown."""
    if not probabilities:
        return None
    level, probability = max(probabilities.items(), key=lambda item: item[1])
    if probability < min_p:
        return None
    return AccountOperationalComplexity(level)
