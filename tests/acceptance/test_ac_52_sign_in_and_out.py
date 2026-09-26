"""AC-52 (docs/requirements/acceptance.md):
"Given the seeded Sales user, when they sign in with the right password, then the response
sets an HTTP-only, `Secure`, `SameSite=Lax` cookie and `API-03` returns role `SALES`; a wrong
password answers `401`; the `LOGIN_MAX_FAILURES`-th consecutive failure and every attempt
during the lock answer `423`; after sign-out the cookie no longer authenticates; the database
holds no plain password or token."

Driven through `API-01`/`API-02`/`API-03` (docs/architecture/interfaces.md#authentication-and-
users-contracts) of the composed stack, seeded by `make seed-demo`
(docs/architecture/overview.md#demo-dataset gives the seeded Sales user's email
`sales@leadradar.local`; its password is the acceptance harness's `SEED_SALES_PASSWORD`). The
database check reads only `app_user.password_hash` and `auth_session.token_hash`
(docs/architecture/sql-store.md#app_user, docs/architecture/sql-store.md#auth_session), never
the implementation.
"""

from __future__ import annotations

import pytest

from conftest import api_get, api_post, login, psql

SALES_EMAIL = "sales@leadradar.local"

LOGIN_MAX_FAILURES = 5  # docs/architecture/services/api.md#runtime default


@pytest.mark.ac("AC-52")
def test_sign_in_sets_cookie_wrong_password_is_401_lockout_is_423_signout_invalidates_no_plaintext_stored(
    seeded,
):
    env = seeded["env"]
    project = seeded["project"]
    sales_password = env["SEED_SALES_PASSWORD"]

    # "when they sign in with the right password, then the response sets an HTTP-only, Secure,
    # SameSite=Lax cookie"
    response, client = login(SALES_EMAIL, sales_password)
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("Set-Cookie", "")
    assert "leadradar_session=" in set_cookie, set_cookie
    assert "HttpOnly" in set_cookie, set_cookie
    assert "Secure" in set_cookie, set_cookie
    assert "SameSite=Lax" in set_cookie, set_cookie
    assert client is not None
    session_cookie_value = client.cookie_value

    # "and API-03 returns role SALES"
    me = api_get("/auth/me", client=client)
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "SALES"

    # "after sign-out the cookie no longer authenticates"
    logout = api_post("/auth/logout", client=client)
    assert logout.status_code == 204, logout.text
    after_logout = api_get("/auth/me", client=client)
    assert after_logout.status_code == 401, after_logout.text

    # "a wrong password answers 401" - the first of LOGIN_MAX_FAILURES consecutive failures.
    wrong = api_post("/auth/login", json={"email": SALES_EMAIL, "password": "not-the-password"})
    assert wrong.status_code == 401, wrong.text

    # "the LOGIN_MAX_FAILURES-th consecutive failure ... answer 423" - failures 2 to
    # LOGIN_MAX_FAILURES - 1 stay 401, the LOGIN_MAX_FAILURES-th locks and answers 423 itself.
    for _ in range(LOGIN_MAX_FAILURES - 2):
        again = api_post("/auth/login", json={"email": SALES_EMAIL, "password": "still-wrong"})
        assert again.status_code == 401, again.text

    locking_attempt = api_post("/auth/login", json={"email": SALES_EMAIL, "password": "still-wrong"})
    assert locking_attempt.status_code == 423, locking_attempt.text

    # "and every attempt during the lock answer 423" - even with the right password.
    during_lock = api_post("/auth/login", json={"email": SALES_EMAIL, "password": sales_password})
    assert during_lock.status_code == 423, during_lock.text

    # "the database holds no plain password or token"
    password_hash = psql(
        project, env, "leadradar", env["POSTGRES_PASSWORD"],
        f"SELECT password_hash FROM app_user WHERE email = '{SALES_EMAIL}';",
    ).stdout.strip()
    assert password_hash, "expected the seeded Sales user to exist"
    assert password_hash != sales_password
    assert sales_password not in password_hash
    assert password_hash.startswith("$argon2id$"), password_hash

    token_hashes = psql(
        project, env, "leadradar", env["POSTGRES_PASSWORD"],
        "SELECT token_hash FROM auth_session ash "
        f"JOIN app_user u ON u.id = ash.user_id WHERE u.email = '{SALES_EMAIL}';",
    ).stdout.strip().splitlines()
    assert token_hashes, "expected the successful sign-in to have created an auth_session row"
    for token_hash in token_hashes:
        assert token_hash != session_cookie_value
        assert session_cookie_value not in token_hash
