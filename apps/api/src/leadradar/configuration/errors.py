"""Typed errors of the configuration capability, mapped once at the edge by
[`api/errors.py`](../api/errors.py) onto the envelope of
[Conventions](/architecture/interfaces.md#conventions)."""

from __future__ import annotations

from leadradar.core.scoring_settings import FieldError


class ConfigurationError(Exception):
    """Base of every typed error this capability raises."""


class NotFound(ConfigurationError):
    """A named service, question, scoring config, industry or market does not exist; `404`."""


class ServiceNotFound(NotFound):
    """`API-09`, `API-10`, `API-11`, `API-12`, `API-15`, `API-17`: no such service."""


class QuestionNotFound(NotFound):
    """`API-13`: no such question."""


class ScoringConfigNotFound(NotFound):
    """`API-16`: no such scoring config."""


class IndustryNotFound(NotFound):
    """`API-73`: no such industry."""


class MarketNotFound(NotFound):
    """`API-76`: no such market."""


class Conflict(ConfigurationError):
    """A uniqueness rule refuses the change; `409 CONFLICT` naming the conflicting row."""

    def __init__(self, message: str, *, entity_id: str) -> None:
        super().__init__(message)
        self.entity_id = entity_id


class ServiceConflict(Conflict):
    """`API-08`: a `code` or `name` already used ([Services and questions]
    (/architecture/interfaces.md#services-and-questions) `API-08`'s note)."""


class QuestionKeyConflict(Conflict):
    """`API-12`: a `key` already used within the service."""


class IndustryConflict(Conflict):
    """`API-72`: a `code` or `label` already used ([Industries and markets]
    (/architecture/interfaces.md#industries-and-markets) `API-72`'s note)."""


class MarketConflict(Conflict):
    """`API-75`: a `code` or `name` already used."""


class DraftInvalid(ConfigurationError):
    """`API-17`: the draft's settings fail [Scoring settings validation]
    (/architecture/rules.md#scoring-settings-validation); `422 VALIDATION`."""

    def __init__(self, fields: list[FieldError]) -> None:
        super().__init__("The scoring draft failed validation.")
        self.fields = fields


class QuestionInvalid(ConfigurationError):
    """`API-12`, `API-13`: the question's `options` fail [`signal_question`]
    (/architecture/sql-store.md#signal_question) shape; `422 VALIDATION`."""

    def __init__(self, fields: list[FieldError]) -> None:
        super().__init__("The question failed validation.")
        self.fields = fields
