from app.services import msstore


def test_poster_prefers_tallest_poster_then_falls_back():
    product = {"LocalizedProperties": [{"ProductTitle": "inKONBINI", "Images": [
        {"ImagePurpose": "Tile", "Uri": "//img/tile.png", "Height": 300},
        {"ImagePurpose": "Poster", "Uri": "//img/poster-small.png", "Height": 600},
        {"ImagePurpose": "Poster", "Uri": "//img/poster-big.png", "Height": 1080},
    ]}]}
    assert msstore.poster_url(product) == "https://img/poster-big.png"
    assert msstore.title(product) == "inKONBINI"

    only_tile = {"LocalizedProperties": [{"Images": [{"ImagePurpose": "Tile", "Uri": "//img/tile.png", "Height": 300}]}]}
    assert msstore.poster_url(only_tile) == "https://img/tile.png"


def test_import_uses_store_poster(client, auth, monkeypatch):
    monkeypatch.setattr(msstore, "lookup", lambda sid, market="GB": {"LocalizedProperties": [{"Images": [{"ImagePurpose": "Poster", "Uri": "//img/p.png", "Height": 900}]}]})
    r = client.post("/library/import", json={"games": [{"title": "PBA Pro Bowling 2026", "platform": "xbox", "store_id": "9NBLGGH4R315"}]}, headers=auth)
    assert r.status_code == 200
    assert client.get("/library", headers=auth).json()[0]["game"]["cover_url"] == "https://img/p.png"
