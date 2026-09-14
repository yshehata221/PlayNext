from app.models import Game, LibraryEntry, Status
from app.services.recommender import Recommender, rating_weight


def by_title(db, title):
    return db.query(Game).filter(Game.title == title).one()


def entry(db, title, status, rating=None, hours=0.0):
    return LibraryEntry(user_id=1, game_id=by_title(db, title).id, game=by_title(db, title), status=status, rating=rating, hours_played=hours)


def test_rating_weight_scale():
    assert rating_weight(LibraryEntry(rating=10, status=Status.completed)) == 1.0
    assert rating_weight(LibraryEntry(rating=1, status=Status.completed)) == -1.0
    assert rating_weight(LibraryEntry(rating=None, status=Status.abandoned)) < 0
    assert rating_weight(LibraryEntry(rating=None, status=Status.backlog)) == 0


def test_open_world_fan_gets_open_world_recs(db):
    games = db.query(Game).all()
    rec = Recommender(games)
    history = [
        entry(db, "Red Dead Redemption 2", Status.completed, 10),
        entry(db, "Grand Theft Auto V", Status.completed, 9),
        entry(db, "The Witcher 3: Wild Hunt", Status.completed, 9),
        entry(db, "Slay the Spire", Status.abandoned, 3),
    ]
    owned = {e.game_id for e in history}
    results = rec.recommend(history, [g for g in games if g.id not in owned], limit=5)

    titles = [r.game.title for r in results]
    # something open-world and third-person should top the list...
    assert "Open world" in results[0].game.themes
    # ...and a card roguelike shouldn't be anywhere near it
    assert "Balatro" not in titles
    # every recommendation explains itself
    assert all(r.reasons for r in results)


def test_time_budget_filters(db):
    games = db.query(Game).all()
    rec = Recommender(games)
    history = [entry(db, "Hades", Status.playing, 9, hours=20)]  # 2h of a 22h main story left
    results = rec.recommend(history, [by_title(db, "Hades"), by_title(db, "Baldur's Gate 3")], hours_available=1)
    titles = [r.game.title for r in results]
    assert "Hades" in titles
    assert "Baldur's Gate 3" not in titles  # 120-minute sessions don't fit in an hour


def test_plan_night_fills_budget(db):
    from app.services.recommender import plan_night, Scored
    games = {g.title: g for g in db.query(Game).all()}
    ranked = [Scored(games["Hades"], 90, [], hours_remaining=0.5), Scored(games["Baldur's Gate 3"], 85, [], hours_remaining=66), Scored(games["Portal 2"], 80, [], hours_remaining=9)]
    plan = plan_night(ranked, hours=3)
    titles = [(s.game.title, m) for s, m in plan]
    assert titles[0] == ("Hades", 30)            # finishable, so it gets what's left of it
    assert titles[1] == ("Baldur's Gate 3", 120)  # one typical session
    assert sum(m for _, m in plan) <= 180
