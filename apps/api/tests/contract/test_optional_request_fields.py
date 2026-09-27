"""Request fields documented as `optional` are absent-only, never `null`."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from leadradar.api.accounts import AccountCreate, AccountUpdate
from leadradar.api.auth_and_users import UserUpdate
from leadradar.api.configuration import ScoringDraftUpdate
from leadradar.api.discovery import CandidateDecision
from leadradar.core.scoring.settings import ScoringSettings

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    ("model", "absent", "present_null"),
    [
        (AccountCreate, {"domain": "example.com", "name": "Example"}, {"country_code": None}),
        (AccountUpdate, {}, {"name": None}),
        (UserUpdate, {}, {"display_name": None}),
        (CandidateDecision, {}, {"domain": None}),
        (ScoringDraftUpdate, {"settings": ScoringSettings().model_dump()}, {"change_note": None}),
    ],
)
def test_optional_request_fields_accept_absence_but_refuse_null(
    model: type[BaseModel], absent: dict[str, object], present_null: dict[str, object]
) -> None:
    model.model_validate(absent)

    with pytest.raises(ValidationError):
        model.model_validate({**absent, **present_null})
