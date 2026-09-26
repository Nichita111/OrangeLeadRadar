"""Contract tests of `API-20` to `API-22` and `API-24` ([Accounts and contacts]
(/architecture/interfaces.md#accounts-and-contacts), `S-ACC-01` to `S-ACC-03`, `S-ACC-05`).

Role refusal (`401`/`403` per the roles column) is covered once, for every mounted route, by
`test_roles_matrix_contract.py`; these tests exercise the shape of each response and its typed
errors against the real database `sales_client` signs into."""

from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.contract

_ACCOUNT_FIELDS = {
    "id",
    "name",
    "domain",
    "country_code",
    "industry",
    "status",
    "origin",
    "last_refreshed_at",
    "active_run_id",
    "employee_count",
    "revenue_eur",
    "operational_complexity",
    "attribute_origin",
    "parent",
    "crunchbase_id",
    "linkedin_url",
    "notes",
    "aliases",
    "sources",
    "next_refresh_at",
}

_ACCOUNT_ROW_FIELDS = {
    "id",
    "name",
    "domain",
    "country_code",
    "industry",
    "status",
    "origin",
    "last_refreshed_at",
    "active_run_id",
}


def _domain() -> str:
    # The registrable domain is the label directly above a public suffix ("com"): nesting the
    # unique part under a fixed second-level domain (e.g. ".example.com") would make every call
    # normalise to the same "example.com" ([Account identity]
    # (/architecture/rules.md#account-identity)), so the random part is the second-level label.
    return f"{uuid.uuid4().hex[:12]}.com"


# --- API-21 POST /accounts ------------------------------------------------------------------


async def test_post_account_answers_200_with_exactly_the_account_fields(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.post(
        "/api/v1/accounts", json={"domain": f"https://{_domain()}/", "name": "A New Account"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == _ACCOUNT_FIELDS
    assert body["origin"] == "MANUAL"
    assert body["status"] == "ACTIVE"
    assert body["aliases"] == ["A New Account"]
    assert len(body["sources"]) == 1
    assert body["sources"][0]["kind"] == "WEBSITE"


async def test_post_account_normalises_the_domain(sales_client: httpx.AsyncClient) -> None:
    unique = uuid.uuid4().hex[:10]
    response = await sales_client.post(
        "/api/v1/accounts",
        json={"domain": f"https://www.{unique}.com/path", "name": "Example"},
    )

    assert response.status_code == 200
    assert response.json()["domain"] == f"{unique}.com"


async def test_post_account_missing_a_required_field_answers_422_naming_it(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.post("/api/v1/accounts", json={"domain": _domain()})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert any(entry["field"] == "name" for entry in body["error"]["details"]["fields"])


async def test_post_account_an_unknown_body_field_answers_422(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.post(
        "/api/v1/accounts",
        json={"domain": _domain(), "name": "X", "email": "not-a-field@example.com"},
    )

    assert response.status_code == 422


async def test_post_account_with_a_domain_already_used_answers_409_naming_the_existing_account(
    sales_client: httpx.AsyncClient,
) -> None:
    domain = _domain()
    first = await sales_client.post("/api/v1/accounts", json={"domain": domain, "name": "First"})
    assert first.status_code == 200
    existing_id = first.json()["id"]

    second = await sales_client.post(
        "/api/v1/accounts", json={"domain": f"https://{domain}/", "name": "Second"}
    )

    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"]["entity_id"] == existing_id


async def test_post_account_with_an_unparseable_domain_answers_422_validation(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.post(
        "/api/v1/accounts", json={"domain": "not a domain at all", "name": "X"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


# --- API-23 GET /accounts/{id} ----------------------------------------------------------------


async def test_get_account_answers_200_with_exactly_the_account_fields(
    sales_client: httpx.AsyncClient,
) -> None:
    created = await sales_client.post(
        "/api/v1/accounts", json={"domain": _domain(), "name": "Readable Account"}
    )
    account_id = created.json()["id"]

    response = await sales_client.get(f"/api/v1/accounts/{account_id}")

    assert response.status_code == 200
    assert set(response.json().keys()) == _ACCOUNT_FIELDS


async def test_get_account_on_an_unknown_id_answers_404(sales_client: httpx.AsyncClient) -> None:
    response = await sales_client.get(f"/api/v1/accounts/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_get_account_on_a_malformed_id_answers_422_naming_the_parameter(
    sales_client: httpx.AsyncClient,
) -> None:
    response = await sales_client.get("/api/v1/accounts/not-a-uuid")

    assert response.status_code == 422
    body = response.json()
    assert any(entry["field"] == "id" for entry in body["error"]["details"]["fields"])


# --- API-20 GET /accounts ---------------------------------------------------------------------


async def test_get_accounts_answers_a_page_of_account_rows(sales_client: httpx.AsyncClient) -> None:
    domain = _domain()
    await sales_client.post("/api/v1/accounts", json={"domain": domain, "name": "Listed Account"})

    response = await sales_client.get("/api/v1/accounts", params={"q": domain})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "page", "page_size", "total"}
    assert body["total"] >= 1
    assert set(body["items"][0].keys()) == _ACCOUNT_ROW_FIELDS
    assert any(item["domain"] == domain for item in body["items"])


async def test_get_accounts_filters_by_status(sales_client: httpx.AsyncClient) -> None:
    created = await sales_client.post(
        "/api/v1/accounts", json={"domain": _domain(), "name": "Filter Me"}
    )
    account_id = created.json()["id"]
    await sales_client.patch(f"/api/v1/accounts/{account_id}", json={"status": "INACTIVE"})

    active_only = await sales_client.get(
        "/api/v1/accounts", params={"q": created.json()["domain"], "status": "ACTIVE"}
    )

    assert active_only.status_code == 200
    assert all(item["id"] != account_id for item in active_only.json()["items"])


# --- API-24 PATCH /accounts/{id} --------------------------------------------------------------


async def test_patch_account_changes_an_attribute_and_records_its_origin_as_manual(
    sales_client: httpx.AsyncClient,
) -> None:
    created = await sales_client.post(
        "/api/v1/accounts", json={"domain": _domain(), "name": "Patchable"}
    )
    account_id = created.json()["id"]

    response = await sales_client.patch(
        f"/api/v1/accounts/{account_id}", json={"employee_count": 250}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["employee_count"] == 250
    assert body["attribute_origin"]["employee_count"] == "MANUAL"


async def test_patch_account_on_an_unknown_id_answers_404(sales_client: httpx.AsyncClient) -> None:
    response = await sales_client.patch(f"/api/v1/accounts/{uuid.uuid4()}", json={"notes": "hello"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_patch_account_with_an_unknown_field_answers_422(
    sales_client: httpx.AsyncClient,
) -> None:
    created = await sales_client.post(
        "/api/v1/accounts", json={"domain": _domain(), "name": "Strict"}
    )
    account_id = created.json()["id"]

    response = await sales_client.patch(
        f"/api/v1/accounts/{account_id}", json={"email": "nope@example.com"}
    )

    assert response.status_code == 422


# --- API-22 POST /accounts/import -------------------------------------------------------------


async def test_import_dry_run_reports_counts_and_writes_nothing(
    sales_client: httpx.AsyncClient,
) -> None:
    domain = _domain()
    csv_text = f"domain,name\n{domain},Imported Co\n"

    response = await sales_client.post(
        "/api/v1/accounts/import",
        files={"file": ("accounts.csv", csv_text, "text/csv")},
        data={"dry_run": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["created"] == 1
    assert body["rows"][0]["outcome"] == "CREATED"
    assert body["rows"][0]["account_id"] is None

    lookup = await sales_client.get("/api/v1/accounts", params={"q": domain})
    assert lookup.json()["total"] == 0


async def test_import_writes_the_valid_rows_and_reports_an_invalid_one(
    sales_client: httpx.AsyncClient,
) -> None:
    domain = _domain()
    csv_text = f"domain,name\n{domain},Imported Co\n,Missing Domain\n"

    response = await sales_client.post(
        "/api/v1/accounts/import",
        files={"file": ("accounts.csv", csv_text, "text/csv")},
        data={"dry_run": "false"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is False
    assert body["created"] == 1
    assert body["invalid"] == 1
    invalid_row = next(row for row in body["rows"] if row["outcome"] == "INVALID")
    assert invalid_row["errors"][0]["field"] == "domain"

    lookup = await sales_client.get("/api/v1/accounts", params={"q": domain})
    assert lookup.json()["total"] == 1
