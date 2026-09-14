from app.models import Game
from app.services import steamstore


def test_apply_fills_gaps_without_overwriting():
    g = Game(title="Stray", slug="stray", steam_appid=1332010, developer="BlueTwelve Studio")
    steamstore.apply(g, {
        "steam_appid": 1332010,
        "developers": ["Someone Else"],
        "genres": [{"id": "25", "description": "Adventure"}, {"id": "23", "description": "Indie"}],
        "categories": [{"id": 2, "description": "Single-player"}],
        "release_date": {"date": "19 Jul, 2022"},
        "metacritic": {"score": 83},
        "short_description": "Lost, alone and separated from family, a stray cat...",
    })
    assert g.developer == "BlueTwelve Studio"  # existing value kept
    assert g.genres == ["Adventure", "Indie"]
    assert g.modes == ["Single player"]
    assert g.release_year == 2022
    assert g.critic_score == 83
    assert g.cover_url.endswith("/1332010/library_600x900.jpg")


def test_find_appid_requires_close_match(monkeypatch):
    monkeypatch.setattr(steamstore, "search", lambda term, limit=10: [{"id": 1, "name": "Completely Different Game"}, {"id": 2, "name": "Little Kitty, Big City"}])
    assert steamstore.find_appid("Little Kitty, Big City") == 2
    assert steamstore.find_appid("inKONBINI") is None
