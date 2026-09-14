def add(client, headers, title, **kwargs):
    game = client.get("/browse/search", params={"q": title}, headers=headers).json()["items"]
    game = next(i for i in game if i["game"]["title"] == title)["game"]
    entry = client.post("/library", json={"game_id": game["id"], "status": kwargs.pop("status", "backlog")}, headers=headers).json()
    if kwargs:
        entry = client.patch(f"/library/{entry['id']}", json=kwargs, headers=headers).json()
    return entry


def befriend(client, a, b):
    """a sends, b accepts. Returns the friendship id and both user ids."""
    me_a = client.get("/auth/me", headers=a).json()
    me_b = client.get("/auth/me", headers=b).json()
    r = client.post("/friends/request", json={"username": me_b["username"]}, headers=a)
    assert r.status_code == 201
    fid = r.json()["friendship_id"]
    assert client.post(f"/friends/{fid}/accept", headers=b).status_code == 200
    return fid, me_a["id"], me_b["id"]


def test_request_accept_and_remove(client, auth, auth2):
    r = client.get("/friends/search", params={"q": "bud"}, headers=auth).json()
    assert [x["user"]["username"] for x in r] == ["buddy"]
    assert r[0]["relationship"] == "none"

    fid, _, b_id = befriend(client, auth, auth2)

    mine = client.get("/friends", headers=auth).json()
    assert len(mine) == 1 and mine[0]["state"] == "accepted" and mine[0]["direction"] == "mutual"
    assert client.get("/friends/search", params={"q": "bud"}, headers=auth).json()[0]["relationship"] == "friends"

    assert client.delete(f"/friends/{fid}", headers=auth).status_code == 204
    assert client.get("/friends", headers=auth).json() == []


def test_cannot_add_yourself_or_duplicate(client, auth, auth2):
    me = client.get("/auth/me", headers=auth).json()
    assert client.post("/friends/request", json={"username": me["username"]}, headers=auth).status_code == 400
    assert client.post("/friends/request", json={"username": "nobody"}, headers=auth).status_code == 404

    client.post("/friends/request", json={"username": "buddy"}, headers=auth)
    assert client.post("/friends/request", json={"username": "buddy"}, headers=auth).status_code == 409


def test_a_request_back_is_treated_as_accepting(client, auth, auth2):
    client.post("/friends/request", json={"username": "buddy"}, headers=auth)
    r = client.post("/friends/request", json={"username": "tester"}, headers=auth2)
    assert r.status_code == 201 and r.json()["state"] == "accepted"


def test_coop_needs_friendship(client, auth, auth2):
    other_id = client.get("/auth/me", headers=auth2).json()["id"]
    assert client.get(f"/friends/{other_id}/coop", headers=auth).status_code == 403


def test_coop_only_suggests_games_both_own_and_prefers_multiplayer(client, auth, auth2):
    # shared: Overwatch 2 (multiplayer) and Disco Elysium (single player)
    add(client, auth, "Overwatch 2", rating=9, hours_played=50)
    add(client, auth2, "Overwatch 2", rating=8, hours_played=30)
    add(client, auth, "Disco Elysium", rating=9)
    add(client, auth2, "Disco Elysium", rating=8)
    # only one of them owns these
    add(client, auth, "Hades", rating=10)
    add(client, auth2, "Celeste", rating=9)

    _, _, b_id = befriend(client, auth, auth2)

    # by default only games you can actually play together
    picks = client.get(f"/friends/{b_id}/coop", headers=auth).json()
    assert [p["game"]["title"] for p in picks] == ["Overwatch 2"]
    assert picks[0]["plays_together"] is True
    assert picks[0]["your_rating"] == 9 and picks[0]["their_rating"] == 8
    assert any("both own it" in r for r in picks[0]["reasons"])
    assert any("Plays together" in r for r in picks[0]["reasons"])

    # single-player shared games only appear when explicitly asked for
    loose = client.get(f"/friends/{b_id}/coop", params={"together_only": "false"}, headers=auth).json()
    titles = [p["game"]["title"] for p in loose]
    assert set(titles) == {"Overwatch 2", "Disco Elysium"}   # shared only, still
    assert titles[0] == "Overwatch 2"                         # multiplayer still ranks first
    solo = next(p for p in loose if p["game"]["title"] == "Disco Elysium")
    assert solo["plays_together"] is False
    assert any("Single-player" in r for r in solo["reasons"])


def test_coop_respects_a_time_budget(client, auth, auth2):
    add(client, auth, "Overwatch 2")        # 30 minute sessions
    add(client, auth2, "Overwatch 2")
    add(client, auth, "Baldur's Gate 3")    # 120 minute sessions
    add(client, auth2, "Baldur's Gate 3")
    _, _, b_id = befriend(client, auth, auth2)

    picks = client.get(f"/friends/{b_id}/coop", params={"hours": 1}, headers=auth).json()
    assert [p["game"]["title"] for p in picks] == ["Overwatch 2"]


def test_compatibility_needs_ratings_from_both(client, auth, auth2):
    add(client, auth, "Overwatch 2", rating=9)
    _, _, b_id = befriend(client, auth, auth2)
    assert client.get("/friends", headers=auth).json()[0]["compatibility"] is None

    add(client, auth2, "Counter-Strike 2", rating=9)
    score = client.get("/friends", headers=auth).json()[0]["compatibility"]
    assert score is not None and score > 60      # two shooter fans


def test_games_with_unknown_modes_are_not_assumed_multiplayer(client, auth, auth2, db):
    """A game we haven't fetched modes for must not be presented as co-op."""
    from app.models import Game

    mystery = Game(title="Unfetched Game", slug="unfetched", genres=["Action"], modes=[])
    db.add(mystery)
    db.commit()
    for headers in (auth, auth2):
        client.post("/library", json={"game_id": mystery.id, "status": "backlog"}, headers=headers)
    _, _, b_id = befriend(client, auth, auth2)

    assert client.get(f"/friends/{b_id}/coop", headers=auth).json() == []
    loose = client.get(f"/friends/{b_id}/coop", params={"together_only": "false"}, headers=auth).json()
    assert loose[0]["plays_together"] is None
    assert any("unknown" in r.lower() for r in loose[0]["reasons"])
