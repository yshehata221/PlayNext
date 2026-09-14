def test_register_login_me(client):
    body = {"email": "a@example.com", "display_name": "A", "username": "alice", "password": "password123"}
    assert client.post("/auth/register", json=body).status_code == 201
    # duplicate email is rejected
    assert client.post("/auth/register", json=body).status_code == 409

    r = client.post("/auth/login", data={"username": body["email"], "password": body["password"]})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["display_name"] == "A"


def test_wrong_password(client):
    client.post("/auth/register", json={"email": "b@example.com", "display_name": "B", "username": "bob", "password": "password123"})
    r = client.post("/auth/login", data={"username": "b@example.com", "password": "nope-nope"})
    assert r.status_code == 401


def test_requires_auth(client):
    assert client.get("/library").status_code == 401


def test_usernames_are_unique_and_case_insensitive(client):
    base = {"display_name": "X", "password": "password123"}
    assert client.post("/auth/register", json={**base, "email": "x1@e.com", "username": "Gamer_99"}).status_code == 201
    # same handle in different case is the same handle
    r = client.post("/auth/register", json={**base, "email": "x2@e.com", "username": "gamer_99"})
    assert r.status_code == 409 and "username" in r.json()["detail"].lower()
    # and it's stored lowercase so people can find each other
    tok = client.post("/auth/login", data={"username": "x1@e.com", "password": "password123"}).json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["username"] == "gamer_99"


def test_username_rules_are_enforced(client):
    base = {"display_name": "X", "password": "password123", "email": "y@e.com"}
    for bad in ["ab", "has space", "no-dashes", "way_too_long_a_username_here", "emoji😀"]:
        assert client.post("/auth/register", json={**base, "username": bad}).status_code == 422

    assert client.get("/auth/username-available/ab").json()["available"] is False
    assert client.get("/auth/username-available/freehandle").json()["available"] is True
