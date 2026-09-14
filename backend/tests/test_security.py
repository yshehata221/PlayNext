import pytest

from app.limiter import limiter


@pytest.fixture()
def rate_limited():
    """Re-enable the limiter that conftest switches off for every other test."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False


def test_login_is_rate_limited(client, rate_limited):
    """Brute-forcing a password should hit a wall rather than run forever."""
    codes = [
        client.post("/auth/login", data={"username": "nobody@example.com", "password": f"guess{i}"}).status_code
        for i in range(14)
    ]
    assert 401 in codes          # the first attempts are processed normally
    assert 429 in codes          # and then it starts refusing
    assert codes.index(429) >= 10


def test_security_headers_are_set(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_password_change_requires_the_current_one(client, auth):
    bad = client.post("/auth/change-password", json={"current_password": "wrong", "new_password": "newpassword1"}, headers=auth)
    assert bad.status_code == 403

    ok = client.post("/auth/change-password", json={"current_password": "password123", "new_password": "newpassword1"}, headers=auth)
    assert ok.status_code == 204

    # the old password stops working and the new one starts
    assert client.post("/auth/login", data={"username": "t@example.com", "password": "password123"}).status_code == 401
    assert client.post("/auth/login", data={"username": "t@example.com", "password": "newpassword1"}).status_code == 200


def test_new_password_must_be_long_enough(client, auth):
    r = client.post("/auth/change-password", json={"current_password": "password123", "new_password": "short"}, headers=auth)
    assert r.status_code == 422


def test_one_users_library_is_invisible_to_another(client, auth, auth2):
    """Entry ids are sequential, so the ownership check matters."""
    game = client.get("/browse/search", params={"q": "Hades"}, headers=auth).json()["items"][0]["game"]
    mine = client.post("/library", json={"game_id": game["id"]}, headers=auth).json()

    assert client.get(f"/library/{mine['id']}", headers=auth2).status_code == 404
    assert client.patch(f"/library/{mine['id']}", json={"rating": 1}, headers=auth2).status_code == 404
    assert client.delete(f"/library/{mine['id']}", headers=auth2).status_code == 404
    assert client.get("/library", headers=auth2).json() == []
