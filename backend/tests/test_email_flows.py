"""
Email verification and password reset. Mail is captured rather than sent, and
the token is read back out of the captured message the way a user would read it
out of their inbox.
"""
import re

import pytest

from app.limiter import limiter


@pytest.fixture()
def outbox(monkeypatch):
    """Capture outgoing mail instead of sending or logging it."""
    sent: list[dict] = []

    def fake_send(to, subject, text, html):
        sent.append({"to": to, "subject": subject, "text": text})
        return True

    from app.services import mailer

    monkeypatch.setattr(mailer, "send", fake_send)
    return sent


def token_from(message: dict) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", message["text"])
    assert match, f"no token in email: {message['text']}"
    return match.group(1)


def register(client, email="new@example.com", username="newbie"):
    return client.post("/auth/register", json={
        "email": email, "display_name": "New", "username": username, "password": "password123",
    })


def test_registration_sends_a_verification_link(client, outbox):
    assert register(client).status_code == 201
    assert len(outbox) == 1
    assert outbox[0]["to"] == "new@example.com"
    assert "confirm" in outbox[0]["subject"].lower()

    r = client.post("/auth/verify", json={"token": token_from(outbox[0])})
    assert r.status_code == 200
    assert r.json()["email_verified"] is True


def test_a_verification_link_only_works_once(client, outbox):
    register(client)
    token = token_from(outbox[0])
    assert client.post("/auth/verify", json={"token": token}).status_code == 200
    # replaying the same link fails, so a forwarded email is useless
    assert client.post("/auth/verify", json={"token": token}).status_code == 400


def test_expired_tokens_are_rejected(client, outbox, db):
    from datetime import datetime, timedelta, timezone

    from app.models import EmailToken

    register(client)
    token = token_from(outbox[0])
    row = db.query(EmailToken).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    assert client.post("/auth/verify", json={"token": token}).status_code == 400


def test_garbage_tokens_are_rejected(client):
    assert client.post("/auth/verify", json={"token": "not-a-real-token"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": "nope", "new_password": "password1"}).status_code == 400


def test_tokens_are_not_stored_in_the_clear(client, outbox, db):
    """A database leak must not hand over working reset links."""
    from app.models import EmailToken

    register(client)
    raw = token_from(outbox[0])
    stored = db.query(EmailToken).one().token_hash
    assert raw not in stored
    assert len(stored) == 64          # sha256 hex


def test_forgot_password_resets_and_signs_in(client, auth, outbox):
    r = client.post("/auth/forgot-password", json={"email": "t@example.com"})
    assert r.status_code == 202
    token = token_from(outbox[-1])

    reset = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnew123"})
    assert reset.status_code == 200
    assert reset.json()["access_token"]          # signed straight in

    assert client.post("/auth/login", data={"username": "t@example.com", "password": "password123"}).status_code == 401
    assert client.post("/auth/login", data={"username": "t@example.com", "password": "brandnew123"}).status_code == 200


def test_a_reset_link_only_works_once(client, auth, outbox):
    client.post("/auth/forgot-password", json={"email": "t@example.com"})
    token = token_from(outbox[-1])
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "firstpass1"}).status_code == 200
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "secondpass1"}).status_code == 400


def test_requesting_a_new_link_invalidates_the_old_one(client, auth, outbox):
    client.post("/auth/forgot-password", json={"email": "t@example.com"})
    first = token_from(outbox[-1])
    client.post("/auth/forgot-password", json={"email": "t@example.com"})
    second = token_from(outbox[-1])

    assert first != second
    assert client.post("/auth/reset-password", json={"token": first, "new_password": "password999"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": second, "new_password": "password999"}).status_code == 200


def test_forgot_password_does_not_reveal_who_has_an_account(client, outbox):
    """Same response either way, so this can't be used to enumerate users."""
    unknown = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert unknown.status_code == 202
    assert unknown.json() == {"sent": True}
    assert outbox == []                # but nothing was actually sent


def test_reset_also_confirms_the_address(client, auth, outbox):
    """Receiving the mail proves the address works."""
    client.post("/auth/forgot-password", json={"email": "t@example.com"})
    token = client.post("/auth/reset-password", json={"token": token_from(outbox[-1]), "new_password": "password999"}).json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email_verified"] is True


def test_login_can_be_gated_on_verification(client, outbox, monkeypatch):
    from app.config import settings

    register(client)
    monkeypatch.setattr(settings, "require_email_verification", True)
    blocked = client.post("/auth/login", data={"username": "new@example.com", "password": "password123"})
    assert blocked.status_code == 403 and "Confirm your email" in blocked.json()["detail"]

    client.post("/auth/verify", json={"token": token_from(outbox[0])})
    assert client.post("/auth/login", data={"username": "new@example.com", "password": "password123"}).status_code == 200


def test_email_requests_are_rate_limited(client, auth):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [client.post("/auth/forgot-password", json={"email": "t@example.com"}).status_code for _ in range(8)]
        assert 202 in codes and 429 in codes
    finally:
        limiter.enabled = False


def test_a_failing_mail_server_does_not_break_registration(client, monkeypatch):
    """The account should exist even if the provider is down; the link can be re-requested."""
    from app.services import mailer

    monkeypatch.setattr(mailer, "_send_smtp", lambda *a, **k: (_ for _ in ()).throw(OSError("smtp down")))
    monkeypatch.setattr("app.config.settings.mail_mode", "smtp")
    monkeypatch.setattr("app.config.settings.smtp_host", "localhost")

    assert register(client).status_code == 201
