from app.services.matching import normalise, similarity


def test_normalise_handles_launcher_names():
    assert normalise("AssassinsCreedValhalla") == normalise("Assassin's Creed Valhalla")
    assert normalise("The Witcher® 3: Wild Hunt – Game of the Year Edition") == normalise("The Witcher 3: Wild Hunt")
    assert normalise("Cyberpunk 2077 (GOG)") == "cyberpunk 2077"
    assert similarity("Red Dead Redemption 2", "Red Dead Redemption II") < 1  # not identical, close enough to review


def test_bulk_import_matches_and_dedupes(client, auth):
    scan = {"games": [
        {"title": "Cyberpunk 2077", "platform": "gog"},
        {"title": "AssassinsCreedValhalla", "platform": "ubisoft"},
        {"title": "Red Dead Redemption 2", "platform": "steam", "steam_appid": 1174180},
        {"title": "Some Indie Nobody Has Heard Of", "platform": "epic"},
    ]}
    r = client.post("/library/import", json=scan, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 4
    assert body["unmatched"] == ["Some Indie Nobody Has Heard Of"]

    titles = {e["game"]["title"]: e for e in client.get("/library", headers=auth).json()}
    # matched entries point at the catalogue game, with its metadata intact
    assert titles["Assassin's Creed Valhalla"]["platform"] == "ubisoft"
    assert titles["Assassin's Creed Valhalla"]["game"]["genres"]
    assert "Red Dead Redemption 2" in titles

    # second scan is a no-op
    r = client.post("/library/import", json=scan, headers=auth).json()
    assert r["imported"] == 0 and r["updated"] == 4
    assert len(client.get("/library", headers=auth).json()) == 4


def test_scanner_cover_is_saved(client, auth, tmp_path, monkeypatch):
    from app.services import media
    monkeypatch.setattr(media, "COVERS", tmp_path)
    # 1x1 transparent PNG
    png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    r = client.post("/library/import", json={"games": [{"title": "inKONBINI", "platform": "xbox", "cover_data": png, "cover_mime": "image/png"}]}, headers=auth)
    assert r.status_code == 200
    entry = client.get("/library", headers=auth).json()[0]
    assert entry["game"]["cover_url"].endswith("/media/covers/inkonbini.png")
    assert (tmp_path / "inkonbini.png").exists()
