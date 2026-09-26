"""Applies [Account attributes](/architecture/rules.md#account-attributes) (`S-ING-06`) to a
loaded [`account`](/architecture/sql-store.md#account) row: the Crunchbase profile fields the
`CRUNCHBASE` plug-in fetched, and the operational-complexity level the classifier answers.
Precedence is [`leadradar.core.account_attributes`](../core/account_attributes.py); this module
only writes the account row it is given, in the caller's transaction. Called by the `CRUNCHBASE`
and `WEBSITE` adapters' fetch handling — a later task's own step handler. Writes no audit row and
enqueues no rescore: the rule's "After" leaves that to the refresh's own `SCORE` stage."""

from __future__ import annotations

from leadradar.ai.shapes import ClassifierOption, ClassifierQuestion, ClassifierRequest
from leadradar.core.account_attributes import (
    operational_complexity_from_probabilities,
    should_write_attribute,
)
from leadradar.core.enums import AccountOperationalComplexity, SignalQuestionAnswerType
from leadradar.db.models.accounts import Account

#: [Account attributes](/architecture/rules.md#account-attributes) Operational complexity: the
#: exact question text, and its three levels labelled with the [`account`]
#: (/architecture/sql-store.md#account) `operational_complexity` meanings.
OPERATIONAL_COMPLEXITY_QUESTION_ID = "operational_complexity"
OPERATIONAL_COMPLEXITY_QUESTION_TEXT = (
    "How complex are this company's operations, judged by the countries it operates in and its "
    "business units?"
)
_COMPLEXITY_OPTIONS = (
    ClassifierOption(key="LOW", label="At most 2 countries and one business unit"),
    ClassifierOption(key="MEDIUM", label="3 to 10 countries, or 2 to 4 business units"),
    ClassifierOption(key="HIGH", label="More than 10 countries, or 5 or more business units"),
)

#: The four Crunchbase-mapped fields ([Account attributes]
#: (/architecture/rules.md#account-attributes) Crunchbase mapping), each writable at origin
#: `CRUNCHBASE`.
_CRUNCHBASE_FIELDS = ("country_code", "industry", "employee_count", "revenue_eur")


def _current_origin(origin: dict[str, object], field: str) -> str | None:
    value = origin.get(field)
    return None if value is None else str(value)


def operational_complexity_request(profile_text: str) -> ClassifierRequest:
    """The one-question [`ClassifierRequest`](/architecture/interfaces.md#classifierrequest) of
    [Account attributes](/architecture/rules.md#account-attributes) Operational complexity, over
    the account's `COMPANY_PROFILE` document or home page text."""
    return ClassifierRequest(
        state=profile_text,
        context=None,
        questions=[
            ClassifierQuestion(
                id=OPERATIONAL_COMPLEXITY_QUESTION_ID,
                kind=SignalQuestionAnswerType.SCALE,
                text=OPERATIONAL_COMPLEXITY_QUESTION_TEXT,
                options=list(_COMPLEXITY_OPTIONS),
            )
        ],
    )


def apply_crunchbase_attributes(
    account: Account,
    *,
    country_code: str | None,
    industry: str | None,
    employee_count: int | None,
    revenue_eur: int | None,
) -> dict[str, object]:
    """Writes each known Crunchbase field to `account` at origin `CRUNCHBASE`, only where
    [Account attributes](/architecture/rules.md#account-attributes) Precedence allows it; returns
    the fields actually changed, for the caller's `progress` counters."""
    values = {
        "country_code": country_code,
        "industry": industry,
        "employee_count": employee_count,
        "revenue_eur": revenue_eur,
    }
    origin = dict(account.attribute_origin)
    changes: dict[str, object] = {}
    for field in _CRUNCHBASE_FIELDS:
        value = values[field]
        if value is None:
            continue
        if not should_write_attribute(_current_origin(origin, field), "CRUNCHBASE"):
            continue
        setattr(account, field, value)
        origin[field] = "CRUNCHBASE"
        changes[field] = value
    if changes:
        account.attribute_origin = origin
    return changes


def apply_operational_complexity(
    account: Account, probabilities: dict[str, float], *, min_p: float
) -> AccountOperationalComplexity | None:
    """Writes the classified operational complexity to `account` at origin `CLASSIFIER`, only
    when [Account attributes](/architecture/rules.md#account-attributes) Precedence allows it and
    a level reaches `min_p` (`ATTRIBUTE_MIN_P`); returns the level written, or `None`."""
    origin = dict(account.attribute_origin)
    if not should_write_attribute(_current_origin(origin, "operational_complexity"), "CLASSIFIER"):
        return None
    level = operational_complexity_from_probabilities(probabilities, min_p)
    if level is None:
        return None
    account.operational_complexity = level
    origin["operational_complexity"] = "CLASSIFIER"
    account.attribute_origin = origin
    return level
