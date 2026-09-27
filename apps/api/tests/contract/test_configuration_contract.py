"""Contract tests of `API-07` to `API-13` and `API-71` to `API-76` ([Services and questions]
(/architecture/interfaces.md#services-and-questions), [Industries and markets]
(/architecture/interfaces.md#industries-and-markets); `S-CFG-01`, `S-CFG-02`, `S-CFG-07`).

Role refusal (`401`/`403` per the roles column) is covered once, for every mounted route, by
`test_roles_matrix_contract.py`; these tests exercise the shape of each response and its typed
errors against the real database `admin_client` signs into."""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.contract


def _suffix() -> str:
    return uuid.uuid4().hex[:8].upper()


async def _create_service(admin_client: httpx.AsyncClient) -> dict[str, object]:
    suffix = _suffix()
    response = await admin_client.post(
        "/api/v1/services",
        json={
            "code": f"SERVICE_{suffix}",
            "name": f"Service {suffix}",
            "description": "A service.",
            "value_proposition": "A value proposition.",
        },
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


# --- Services ------------------------------------------------------------------------------


async def test_creating_a_service_lists_it_active_with_draft_version_1_holding_the_default_settings(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await _create_service(admin_client)
    assert created["status"] == "ACTIVE"
    assert created["active_version"] is None
    assert created["draft_version"] == 1
    assert created["question_count"] == 0

    listed = await admin_client.get("/api/v1/services")
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())

    configs = await admin_client.get(f"/api/v1/services/{created['id']}/scoring-configs")
    assert configs.status_code == 200
    [draft] = configs.json()
    assert (draft["version"], draft["status"]) == (1, "DRAFT")

    detail = await admin_client.get(f"/api/v1/scoring-configs/{draft['id']}")
    assert detail.status_code == 200
    settings = detail.json()["settings"]
    assert settings["fit_weight"] == 0.4
    assert settings["intent_weight"] == 0.6
    assert settings["icp_criteria"] == []
    assert settings["questions"] == []


async def test_a_second_service_with_the_same_code_is_refused_409_with_entity_id(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await _create_service(admin_client)

    conflicting = await admin_client.post(
        "/api/v1/services",
        json={
            "code": created["code"],
            "name": f"Service {_suffix()}",
            "description": "Another service.",
            "value_proposition": "Another value proposition.",
        },
    )

    assert conflicting.status_code == 409
    body = conflicting.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"]["entity_id"] == created["id"]


async def test_a_service_patch_carrying_code_is_refused_422_naming_code(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await _create_service(admin_client)

    response = await admin_client.patch(
        f"/api/v1/services/{created['id']}", json={"code": "NEW_CODE"}
    )

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert any(field["field"] == "code" for field in fields)


# --- Signal questions ------------------------------------------------------------------------


async def test_a_new_question_has_revision_1_a_run_id_and_joins_the_draft_at_medium(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)

    created = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "A_SIGNAL",
            "text": "Does it show a signal?",
            "answer_type": "YES_NO",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
        },
    )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["revision"] == 1
    assert body["run_id"] is not None
    assert body["status"] == "ACTIVE"

    configs = await admin_client.get(f"/api/v1/services/{service['id']}/scoring-configs")
    draft_id = next(c["id"] for c in configs.json() if c["status"] == "DRAFT")
    detail = await admin_client.get(f"/api/v1/scoring-configs/{draft_id}")
    [setting] = detail.json()["settings"]["questions"]
    assert setting == {"question_key": "A_SIGNAL", "weight": "MEDIUM", "half_life_days": None}


async def test_a_choice_to_yes_no_patch_answers_the_question_without_options(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)
    created = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "A_CHOICE",
            "text": "Which option?",
            "answer_type": "CHOICE",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
            "options": [
                {"key": "YES", "label": "Yes", "strength": "STRONG"},
                {"key": "NO", "label": "No", "strength": "NONE"},
            ],
        },
    )
    assert created.status_code == 200, created.text
    question_id = created.json()["id"]

    patched = await admin_client.patch(
        f"/api/v1/questions/{question_id}", json={"answer_type": "YES_NO"}
    )

    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["answer_type"] == "YES_NO"
    assert body["options"] is None
    assert body["revision"] == 2


async def test_a_choice_to_yes_no_patch_carrying_options_is_refused_422_naming_options(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)
    created = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "A_CHOICE",
            "text": "Which option?",
            "answer_type": "CHOICE",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
            "options": [
                {"key": "YES", "label": "Yes", "strength": "STRONG"},
                {"key": "NO", "label": "No", "strength": "NONE"},
            ],
        },
    )
    assert created.status_code == 200, created.text
    question_id = created.json()["id"]

    patched = await admin_client.patch(
        f"/api/v1/questions/{question_id}",
        json={
            "answer_type": "YES_NO",
            "options": [
                {"key": "YES", "label": "Yes", "strength": "STRONG"},
                {"key": "NO", "label": "No", "strength": "NONE"},
            ],
        },
    )

    assert patched.status_code == 422, patched.text
    fields = patched.json()["error"]["details"]["fields"]
    assert any(field["field"] == "/options" for field in fields)


async def test_a_choice_question_without_a_none_option_is_refused_422_naming_options(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)

    response = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "A_CHOICE",
            "text": "Which option?",
            "answer_type": "CHOICE",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
            "options": [
                {"key": "YES", "label": "Yes", "strength": "STRONG"},
                {"key": "NO", "label": "No", "strength": "WEAK"},
            ],
        },
    )

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert any(field["field"] == "/options" for field in fields)


async def test_a_question_without_source_types_is_refused_422_naming_source_types(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)

    response = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "NO_SOURCES",
            "text": "Does it show a signal?",
            "answer_type": "YES_NO",
            "polarity": "POSITIVE",
            "source_types": [],
        },
    )

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert any(field["field"] == "source_types" for field in fields)


async def test_a_question_patch_carrying_polarity_is_refused_422(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)
    created = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "A_SIGNAL",
            "text": "Does it show a signal?",
            "answer_type": "YES_NO",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
        },
    )
    question_id = created.json()["id"]

    response = await admin_client.patch(
        f"/api/v1/questions/{question_id}", json={"polarity": "NEGATIVE"}
    )

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert any(field["field"] == "polarity" for field in fields)


async def test_deactivating_a_question_removes_it_from_the_draft(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)
    created = await admin_client.post(
        f"/api/v1/services/{service['id']}/questions",
        json={
            "key": "A_SIGNAL",
            "text": "Does it show a signal?",
            "answer_type": "YES_NO",
            "polarity": "POSITIVE",
            "source_types": ["NEWS"],
        },
    )
    question_id = created.json()["id"]

    deactivated = await admin_client.patch(
        f"/api/v1/questions/{question_id}", json={"status": "INACTIVE"}
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["run_id"] is None

    configs = await admin_client.get(f"/api/v1/services/{service['id']}/scoring-configs")
    draft_id = next(c["id"] for c in configs.json() if c["status"] == "DRAFT")
    detail = await admin_client.get(f"/api/v1/scoring-configs/{draft_id}")
    assert detail.json()["settings"]["questions"] == []


# --- Scoring drafts ------------------------------------------------------------------------


async def test_an_invalid_draft_is_refused_422_with_a_field_error_per_pointer_unchanged(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)
    configs = await admin_client.get(f"/api/v1/services/{service['id']}/scoring-configs")
    draft_id = next(c["id"] for c in configs.json() if c["status"] == "DRAFT")
    original = (await admin_client.get(f"/api/v1/scoring-configs/{draft_id}")).json()["settings"]

    invalid_settings = {
        **original,
        "fit_weight": 0.5,
        "intent_weight": 0.6,
        "warm_threshold": 80,
        "hot_threshold": 70,
        "disqualifiers": [
            {
                "key": "D1",
                "label": "Unknown question",
                "kind": "SIGNAL",
                "question_key": "UNKNOWN_KEY",
                "min_strength": "WEAK",
            }
        ],
    }

    response = await admin_client.put(
        f"/api/v1/services/{service['id']}/scoring-configs/draft",
        json={"settings": invalid_settings},
    )

    assert response.status_code == 422
    fields = {field["field"] for field in response.json()["error"]["details"]["fields"]}
    assert "/intent_weight" in fields
    assert "/warm_threshold" in fields
    assert "/disqualifiers/0/question_key" in fields

    unchanged = (await admin_client.get(f"/api/v1/scoring-configs/{draft_id}")).json()["settings"]
    assert unchanged == original


async def test_saving_a_draft_when_none_exists_creates_it_from_the_active_version(
    admin_client: httpx.AsyncClient,
) -> None:
    service = await _create_service(admin_client)
    configs = await admin_client.get(f"/api/v1/services/{service['id']}/scoring-configs")
    draft = next(c for c in configs.json() if c["status"] == "DRAFT")
    settings = (await admin_client.get(f"/api/v1/scoring-configs/{draft['id']}")).json()["settings"]

    activated = await admin_client.post(
        f"/api/v1/scoring-configs/{draft['id']}/activate", json={"change_note": "Go live."}
    )
    assert activated.status_code == 200, activated.text

    saved = await admin_client.put(
        f"/api/v1/services/{service['id']}/scoring-configs/draft",
        json={"settings": settings, "change_note": "A new draft."},
    )

    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["version"] == 2
    assert body["status"] == "DRAFT"


# --- Industries and markets ------------------------------------------------------------------


async def test_a_second_industry_with_the_same_code_is_refused_409(
    admin_client: httpx.AsyncClient,
) -> None:
    code = f"IND_{_suffix()}"
    first = await admin_client.post("/api/v1/industries", json={"code": code, "label": "Label 1"})
    assert first.status_code == 200, first.text

    second = await admin_client.post("/api/v1/industries", json={"code": code, "label": "Label 2"})

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


async def test_a_non_upper_snake_code_is_refused_422(admin_client: httpx.AsyncClient) -> None:
    response = await admin_client.post(
        "/api/v1/industries", json={"code": "not-upper-snake", "label": "Label"}
    )

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert any(field["field"] == "code" for field in fields)


async def test_a_market_with_an_invalid_country_is_refused_422(
    admin_client: httpx.AsyncClient,
) -> None:
    response = await admin_client.post(
        "/api/v1/markets",
        json={"code": f"MARKET_{_suffix()}", "name": "A market", "country_codes": ["ZZ"]},
    )

    assert response.status_code == 422
    fields = response.json()["error"]["details"]["fields"]
    assert any(field["field"] == "country_codes" for field in fields)


async def test_a_retired_industry_leaves_the_active_list_and_a_draft_naming_it_is_refused_422(
    admin_client: httpx.AsyncClient,
) -> None:
    code = f"IND_{_suffix()}"
    created = await admin_client.post("/api/v1/industries", json={"code": code, "label": "Label"})
    assert created.status_code == 200, created.text

    service = await _create_service(admin_client)
    configs = await admin_client.get(f"/api/v1/services/{service['id']}/scoring-configs")
    draft = next(c for c in configs.json() if c["status"] == "DRAFT")
    settings = (await admin_client.get(f"/api/v1/scoring-configs/{draft['id']}")).json()["settings"]
    settings_with_industry = {
        **settings,
        "icp_criteria": [{"key": "IND", "kind": "INDUSTRY", "weight": "HIGH", "values": [code]}],
    }
    saved = await admin_client.put(
        f"/api/v1/services/{service['id']}/scoring-configs/draft",
        json={"settings": settings_with_industry},
    )
    assert saved.status_code == 200, saved.text

    retired = await admin_client.patch(f"/api/v1/industries/{code}", json={"status": "INACTIVE"})
    assert retired.status_code == 200, retired.text

    active_list = await admin_client.get("/api/v1/industries", params={"status": "ACTIVE"})
    assert all(item["code"] != code for item in active_list.json())

    resaved = await admin_client.put(
        f"/api/v1/services/{service['id']}/scoring-configs/draft",
        json={"settings": settings_with_industry},
    )
    assert resaved.status_code == 422
    fields = resaved.json()["error"]["details"]["fields"]
    assert any(field["field"] == "/icp_criteria/0/values" for field in fields)


async def test_an_industry_or_market_patch_carrying_code_is_refused_422(
    admin_client: httpx.AsyncClient,
) -> None:
    industry_code = f"IND_{_suffix()}"
    await admin_client.post("/api/v1/industries", json={"code": industry_code, "label": "Label"})
    market_code = f"MARKET_{_suffix()}"
    await admin_client.post(
        "/api/v1/markets",
        json={"code": market_code, "name": "A market", "country_codes": ["DE"]},
    )

    industry_patch = await admin_client.patch(
        f"/api/v1/industries/{industry_code}", json={"code": "NEW_CODE"}
    )
    market_patch = await admin_client.patch(
        f"/api/v1/markets/{market_code}", json={"code": "NEW_CODE"}
    )

    assert industry_patch.status_code == 422
    assert any(
        field["field"] == "code" for field in industry_patch.json()["error"]["details"]["fields"]
    )
    assert market_patch.status_code == 422
    assert any(
        field["field"] == "code" for field in market_patch.json()["error"]["details"]["fields"]
    )
