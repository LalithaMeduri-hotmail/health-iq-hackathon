"""Contract tests for the account module (`POST /api/v1/auth/register|login|logout`, `GET /me`).

Runs entirely against the in-process demo account store (`DEMO_MODE=true`), no live Azure needed.
"""

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _isolated_account_store():
    """Each test starts from an empty `accounts` store so uniqueness/lockout stay deterministic."""
    from app.repositories.cosmos_repo import _DEMO_ACCOUNT_INDEX, _DEMO_ACCOUNTS

    _DEMO_ACCOUNTS.clear()
    _DEMO_ACCOUNT_INDEX.clear()
    yield
    _DEMO_ACCOUNTS.clear()
    _DEMO_ACCOUNT_INDEX.clear()


def _register(client, **overrides):
    body = {
        "username": "priya.k",
        "mobile": "+919876543210",
        "email": "priya@example.com",
        "pin": "4821",
    }
    body.update(overrides)
    return client.post("/api/v1/auth/register", json=body)


def test_register_creates_an_account_and_sets_a_session_cookie(client) -> None:
    response = _register(client)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account"]["username"] == "priya.k"
    assert "pinHash" not in data["account"]
    assert data["expiresIn"] > 0
    assert "hiq_session" in response.cookies


def test_local_session_cookie_is_accepted_over_http(client) -> None:
    response = _register(client)

    assert "Secure" not in response.headers["set-cookie"]


def test_register_requires_mobile_or_email(client) -> None:
    response = _register(client, mobile=None, email=None)

    assert response.status_code == 400


def test_register_rejects_a_trivial_pin(client) -> None:
    response = _register(client, pin="0000")

    assert response.status_code == 422


def test_register_rejects_a_duplicate_username(client) -> None:
    _register(client)

    response = _register(client, mobile="+919876500000", email="other@example.com")

    assert response.status_code == 409


def test_login_with_username_succeeds_and_returns_the_account(client) -> None:
    _register(client)

    response = client.post("/api/v1/auth/login", json={"identifier": "priya.k", "pin": "4821"})

    assert response.status_code == 200
    assert response.json()["data"]["account"]["username"] == "priya.k"
    assert "hiq_session" in response.cookies


def test_login_with_mobile_or_email_also_succeeds(client) -> None:
    _register(client)

    mobile_body = {"identifier": "+919876543210", "pin": "4821"}
    email_body = {"identifier": "priya@example.com", "pin": "4821"}
    by_mobile = client.post("/api/v1/auth/login", json=mobile_body)
    by_email = client.post("/api/v1/auth/login", json=email_body)

    assert by_mobile.status_code == 200
    assert by_email.status_code == 200


def test_login_with_wrong_pin_is_rejected_with_a_generic_message(client) -> None:
    _register(client)

    response = client.post("/api/v1/auth/login", json={"identifier": "priya.k", "pin": "0000"})

    assert response.status_code == 401
    assert "priya.k" not in response.json()["detail"]


def test_login_with_unknown_identifier_returns_the_same_generic_message(client) -> None:
    body = {"identifier": "nobody", "pin": "4821"}
    known_pin_wrong = client.post("/api/v1/auth/login", json=body)

    assert known_pin_wrong.status_code == 401
    assert known_pin_wrong.json()["detail"] == "Invalid username/mobile/email or PIN"


def test_login_locks_the_account_after_too_many_failed_attempts(client) -> None:
    _register(client)
    settings = get_settings()

    for _ in range(settings.pin_max_failed_attempts):
        client.post("/api/v1/auth/login", json={"identifier": "priya.k", "pin": "0000"})

    response = client.post("/api/v1/auth/login", json={"identifier": "priya.k", "pin": "4821"})

    assert response.status_code == 429


def test_me_returns_the_signed_in_account(client) -> None:
    _register(client)

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "priya.k"


def test_me_without_a_session_falls_back_to_demo_user_and_is_unauthenticated(client) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_logout_clears_the_session_cookie(client) -> None:
    _register(client)

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_expires_the_cookie_on_the_path_it_was_set_on(client) -> None:
    """A browser only overwrites a cookie whose name and path match the one it holds."""
    _register(client)

    header = client.post("/api/v1/auth/logout").headers["set-cookie"]

    assert "hiq_session=" in header
    assert "Path=/" in header
    # Either form tells the browser to drop it immediately.
    assert "Max-Age=0" in header or "1970" in header
