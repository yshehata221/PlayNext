def find_local(client, auth, title):
    r = client.get("/browse/search", params={"q": title}, headers=auth)
    assert r.status_code == 200
    return next(i for i in r.json()["items"] if i["game"]["title"] == title)


def test_browse_search_flags_ownership(client, auth):
    item = find_local(client, auth, "Hades")
    assert item["in_library"] is False

    client.post("/library", json={"game_id": item["game"]["id"], "status": "backlog"}, headers=auth)
    assert find_local(client, auth, "Hades")["in_library"] is True


def test_wishlist_lives_outside_the_library(client, auth):
    game = find_local(client, auth, "Elden Ring")["game"]
    r = client.post("/wishlist", json={"game_id": game["id"]}, headers=auth)
    assert r.status_code == 201
    entry_id = r.json()["id"]

    assert [e["game"]["title"] for e in client.get("/wishlist", headers=auth).json()] == ["Elden Ring"]
    # and it does NOT show up in the library listing
    assert client.get("/library", headers=auth).json() == []

    # buying it moves it across, keeping the same row
    r = client.post(f"/wishlist/{entry_id}/own", params={"platform": "steam"}, headers=auth)
    assert r.json()["status"] == "backlog"
    assert client.get("/wishlist", headers=auth).json() == []
    assert [e["id"] for e in client.get("/library", headers=auth).json()] == [entry_id]


def test_cannot_wishlist_something_you_own(client, auth):
    game = find_local(client, auth, "Portal 2")["game"]
    client.post("/library", json={"game_id": game["id"], "status": "completed"}, headers=auth)
    assert client.post("/wishlist", json={"game_id": game["id"]}, headers=auth).status_code == 409


def test_for_you_excludes_owned(client, auth):
    game = find_local(client, auth, "Hades")["game"]
    client.post("/library", json={"game_id": game["id"], "status": "completed"}, headers=auth)
    body = client.get("/browse/for-you", headers=auth).json()
    assert "Hades" not in [i["game"]["title"] for i in body["items"]]
    assert all(i["in_library"] is False for i in body["items"])


def test_browse_search_filters_and_pages(client, auth):
    # genre filter narrows to RPGs from the seeded catalogue
    r = client.get("/browse/search", params={"q": "the", "genre": "role-playing", "limit": 50}, headers=auth).json()
    assert r["items"], "expected some RPGs"
    assert all(any("role-playing" in g.lower() for g in i["game"]["genres"]) for i in r["items"])

    # paging: first page of 2, then the next, no overlap
    p1 = client.get("/browse/search", params={"q": "the", "sort": "title", "limit": 2, "offset": 0}, headers=auth).json()
    p2 = client.get("/browse/search", params={"q": "the", "sort": "title", "limit": 2, "offset": 2}, headers=auth).json()
    assert len(p1["items"]) == 2 and p1["has_more"] is True
    assert {i["game"]["id"] for i in p1["items"]} & {i["game"]["id"] for i in p2["items"]} == set()
    assert p1["genres"]


def test_browse_search_can_hide_owned(client, auth):
    game = find_local(client, auth, "Celeste")["game"]
    client.post("/library", json={"game_id": game["id"], "status": "backlog"}, headers=auth)
    r = client.get("/browse/search", params={"q": "celeste", "hide_owned": "true"}, headers=auth).json()
    assert all(i["game"]["title"] != "Celeste" for i in r["items"])


def test_requirements_are_parsed_and_platforms_recorded(db):
    from app.models import Game
    from app.services import steamstore

    g = Game(title="Test Game", slug="test-game", steam_appid=1)
    steamstore.apply(g, {
        "steam_appid": 1,
        "genres": [{"id": "1", "description": "Action"}],
        "platforms": {"windows": True, "mac": False, "linux": True},
        "pc_requirements": {
            "minimum": "<strong>Minimum:</strong><br><ul><li><strong>OS:</strong> Windows 10</li><li><strong>Memory:</strong> 8 GB RAM</li></ul>",
            "recommended": "<strong>Recommended:</strong><br><ul><li><strong>Memory:</strong> 16 GB RAM</li></ul>",
        },
    })
    assert g.platforms == ["PC (Microsoft Windows)", "Linux"]
    assert "Windows 10" in g.requirements["minimum"]
    assert "8 GB RAM" in g.requirements["minimum"]
    assert "<" not in g.requirements["minimum"]      # HTML stripped
    assert "16 GB RAM" in g.requirements["recommended"]


def test_game_detail_works_for_unowned_games(client, auth):
    game = find_local(client, auth, "Hades")["game"]
    r = client.get(f"/browse/game/{game['id']}", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["in_library"] is False
    assert body["game"]["genres"]           # seeded metadata survives
    assert client.get("/browse/game/999999", headers=auth).status_code == 404


def test_game_detail_survives_a_failing_lookup(client, auth, monkeypatch):
    """A third-party API falling over must not take the detail page down."""
    from app.services import steamstore

    game = find_local(client, auth, "Starfield")["game"]
    monkeypatch.setattr(steamstore, "needs_enrich", lambda g: True)
    monkeypatch.setattr(steamstore, "enrich", lambda g: (_ for _ in ()).throw(RuntimeError("store down")))

    r = client.get(f"/browse/game/{game['id']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["game"]["title"] == "Starfield"


def test_duplicate_appid_copies_metadata_instead_of_failing(client, auth, db, monkeypatch):
    """
    Two catalogue rows can legitimately describe the same game (a scanner import
    and a store search). steam_appid is unique, so the second must not try to
    claim it - it should inherit the first row's details.
    """
    from app.models import Game
    from app.services import steamstore

    original = db.query(Game).filter(Game.title == "Red Dead Redemption 2").one()
    original.steam_appid = 1174180
    duplicate = Game(title="Red Dead Redemption 2 Enhanced", slug="rdr2-enhanced")
    db.add(duplicate)
    db.commit()

    monkeypatch.setattr(steamstore, "find_appid", lambda title: 1174180)
    assert steamstore.enrich(duplicate, db=db) is True
    db.commit()  # must not raise

    assert duplicate.steam_appid is None                 # id stays with the original row
    assert duplicate.cover_url == original.cover_url     # details copied across
    assert duplicate.genres == original.genres


def test_game_detail_recovers_from_an_integrity_error(client, auth, db, monkeypatch):
    """The endpoint must still respond after a failed flush, not 500."""
    from app.models import Game
    from app.services import steamstore

    db.query(Game).filter(Game.title == "Hades").one().steam_appid = 1145360
    db.commit()
    clash = Game(title="Hades Special", slug="hades-special")
    db.add(clash)
    db.commit()

    # simulate the old bug: enrichment assigns a taken appid with no db to check against
    monkeypatch.setattr(steamstore, "needs_enrich", lambda g: True)
    monkeypatch.setattr(steamstore, "enrich", lambda g, db=None: setattr(g, "steam_appid", 1145360))

    r = client.get(f"/browse/game/{clash.id}", headers=auth)
    assert r.status_code == 200
    assert r.json()["game"]["title"] == "Hades Special"


def test_similar_games_uses_tag_similarity(client, auth):
    """An open-world Rockstar game should be most like other open-world action games."""
    rdr = find_local(client, auth, "Red Dead Redemption 2")["game"]
    r = client.get(f"/browse/game/{rdr['id']}/similar", headers=auth)
    assert r.status_code == 200
    items = r.json()
    assert items and items[0]["game"]["title"] != "Red Dead Redemption 2"
    # the closest match should share the open-world theme, not be a card game
    assert "Open world" in items[0]["game"]["themes"]
    assert all(i["match"] is not None for i in items)


def test_trailers_are_normalised_from_both_sources():
    """Steam serves files (sometimes over http); IGDB gives YouTube ids."""
    from app.models import Game
    from app.services import igdb, steamstore

    steam_game = Game(title="A", slug="a", steam_appid=1)
    steamstore.apply(steam_game, {
        "steam_appid": 1,
        "movies": [{"name": "Launch Trailer", "mp4": {"max": "http://cdn.steam/movie.mp4?t=99"}, "thumbnail": "http://cdn.steam/t.jpg"}],
    })
    v = steam_game.videos[0]
    assert v["kind"] == "mp4"
    assert v["src"] == "https://cdn.steam/movie.mp4"   # https, query stripped
    assert v["thumb"].startswith("https://")

    igdb_game = igdb.to_game({"id": 9, "name": "B", "slug": "b", "videos": [{"video_id": "xyz", "name": "Reveal"}]})
    assert igdb_game.videos[0] == {"kind": "youtube", "src": "xyz", "title": "Reveal",
                                   "thumb": "https://img.youtube.com/vi/xyz/hqdefault.jpg"}
