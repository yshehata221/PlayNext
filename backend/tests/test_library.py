def find(client, auth, title):
    r = client.get("/games/search", params={"q": title}, headers=auth)
    assert r.status_code == 200
    return r.json()[0]


def test_add_update_remove(client, auth):
    game = find(client, auth, "Hades")

    r = client.post("/library", json={"game_id": game["id"], "status": "backlog"}, headers=auth)
    assert r.status_code == 201
    entry = r.json()
    assert entry["game"]["title"] == "Hades"

    # can't add the same game twice
    assert client.post("/library", json={"game_id": game["id"]}, headers=auth).status_code == 409

    r = client.patch(f"/library/{entry['id']}", json={"status": "completed", "rating": 9, "hours_played": 24}, headers=auth)
    assert r.status_code == 200
    assert r.json()["rating"] == 9

    # rating outside 1-10 is a validation error
    assert client.patch(f"/library/{entry['id']}", json={"rating": 11}, headers=auth).status_code == 422

    assert client.get("/library", params={"status": "completed"}, headers=auth).json()[0]["id"] == entry["id"]
    assert client.delete(f"/library/{entry['id']}", headers=auth).status_code == 204
    assert client.get("/library", headers=auth).json() == []


def test_stats_backlog_estimate(client, auth):
    for title, status, hours in [("Elden Ring", "backlog", 0), ("Hades", "playing", 10)]:
        g = find(client, auth, title)
        r = client.post("/library", json={"game_id": g["id"], "status": status}, headers=auth)
        client.patch(f"/library/{r.json()['id']}", json={"hours_played": hours}, headers=auth)

    s = client.get("/stats", headers=auth).json()
    assert s["total_games"] == 2
    # Elden Ring 60h + Hades (22 - 10 played) = 72h left in the backlog
    assert s["backlog_hours"] == 72
    assert s["backlog_years_at_current_pace"] is not None
    assert s["backlog_months_at_current_pace"] is not None
    # no ratings yet, so the rating figures must be absent rather than 0
    assert s["average_rating"] is None and s["rated_games"] == 0
    assert s["personality"]["title"] and s["personality"]["evidence"]


def test_stats_are_honest_about_what_they_measure(client, auth):
    """An average from one rated game must report that it came from one game."""
    g = find(client, auth, "Hades")
    r = client.post("/library", json={"game_id": g["id"], "status": "playing"}, headers=auth)
    client.patch(f"/library/{r.json()['id']}", json={"rating": 10, "hours_played": 4}, headers=auth)
    for title in ["Elden Ring", "Portal 2", "Celeste"]:
        client.post("/library", json={"game_id": find(client, auth, title)["id"]}, headers=auth)

    s = client.get("/stats", headers=auth).json()
    assert s["total_games"] == 4
    assert s["average_rating"] == 10 and s["rated_games"] == 1   # 10/10 "from 1 rated game"
    assert s["played_games"] == 1
    assert s["completed_games"] == 0 and s["started_games"] == 1
    assert s["backlog_games"] == 3
    # a 4-game library gets the newcomer profile, not a confident label
    assert s["personality"]["key"] == "newcomer"


def test_personality_picks_a_specialist_from_playtime(client, auth):
    for title, hours in [("Counter-Strike 2", 200), ("Overwatch 2", 150), ("Portal 2", 3)]:
        g = find(client, auth, title)
        e = client.post("/library", json={"game_id": g["id"], "status": "playing"}, headers=auth).json()
        client.patch(f"/library/{e['id']}", json={"hours_played": hours}, headers=auth)
    for title in ["Hades", "Elden Ring", "Celeste"]:
        client.post("/library", json={"game_id": find(client, auth, title)["id"]}, headers=auth)

    s = client.get("/stats", headers=auth).json()
    assert s["by_genre"][0]["genre"] == "Shooter"
    assert s["by_genre"][0]["hours_share"] > 45
    assert "Shooter" in s["personality"]["title"]
