"""
Seed a convincing demo account, so someone opening a deployed PlayNext sees a
working product rather than an empty library.

    python -m app.demo

Idempotent: re-running tops up anything missing instead of duplicating. Ratings
and hours are chosen so the recommender, the profile personality and the friend
comparison all have something real to work with.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .auth import hash_password
from .database import Base, SessionLocal, engine, ensure_columns
from .models import Friendship, FriendState, Game, LibraryEntry, Status, User
from .seed import seed_games
from .services.igdb import slugify

DEMO = {"email": "demo@playnext.app", "username": "demo", "display_name": "Demo", "password": "demo1234"}
FRIEND = {"email": "sam@playnext.app", "username": "sam", "display_name": "Sam", "password": "demo1234"}

# (title, status, rating, hours) - an open-world/shooter leaning player with a
# real backlog, a couple of abandoned games and enough ratings to profile
DEMO_LIBRARY = [
    ("Red Dead Redemption 2", Status.completed, 10, 92),
    ("Grand Theft Auto V", Status.completed, 9, 140),
    ("The Witcher 3: Wild Hunt", Status.completed, 9, 88),
    ("Cyberpunk 2077", Status.playing, 9, 18),
    ("Overwatch 2", Status.playing, 7, 310),
    ("Counter-Strike 2", Status.playing, 8, 220),
    ("Ghost of Tsushima", Status.completed, 8, 46),
    ("Portal 2", Status.completed, 10, 11),
    ("Civilization VI", Status.abandoned, 4, 6),
    ("Celeste", Status.abandoned, 5, 2),
    ("Elden Ring", Status.backlog, None, 0),
    ("Baldur's Gate 3", Status.backlog, None, 0),
    ("Hades", Status.backlog, None, 1.5),
    ("Starfield", Status.backlog, None, 0),
    ("Disco Elysium", Status.backlog, None, 0),
    ("Sekiro: Shadows Die Twice", Status.backlog, None, 0),
    ("Death Stranding", Status.backlog, None, 0),
    ("Alan Wake 2", Status.backlog, None, 0),
    ("Metaphor: ReFantazio", Status.backlog, None, 0),
    ("Resident Evil 4", Status.backlog, None, 0),
    ("Max Payne 3", Status.wishlist, None, 0),
    ("Kingdom Come: Deliverance II", Status.wishlist, None, 0),
]

# Sam overlaps on the multiplayer games, so "what should we play?" has answers
FRIEND_LIBRARY = [
    ("Overwatch 2", Status.playing, 8, 190),
    ("Counter-Strike 2", Status.playing, 9, 400),
    ("Red Dead Redemption 2", Status.completed, 9, 70),
    ("Elden Ring", Status.completed, 10, 120),
    ("Baldur's Gate 3", Status.playing, 9, 60),
    ("Portal 2", Status.completed, 9, 10),
    ("Factorio", Status.playing, 9, 150),
    ("Stardew Valley", Status.completed, 8, 90),
    ("Hollow Knight", Status.backlog, None, 0),
    ("Slay the Spire", Status.completed, 8, 40),
]

PLATFORMS = ["steam", "steam", "steam", "xbox", "playstation", "epic"]


def _user(db, spec: dict) -> User:
    user = db.query(User).filter(User.email == spec["email"]).first()
    if user:
        return user
    user = User(email=spec["email"], username=spec["username"], display_name=spec["display_name"],
                password_hash=hash_password(spec["password"]))
    db.add(user)
    db.flush()
    return user


def _stock(db, user: User, rows: list[tuple], rng: random.Random) -> int:
    added = 0
    now = datetime.now(timezone.utc)
    for i, (title, status, rating, hours) in enumerate(rows):
        game = db.query(Game).filter(Game.slug == slugify(title)).first()
        if game is None:
            continue
        if db.query(LibraryEntry).filter_by(user_id=user.id, game_id=game.id).first():
            continue
        db.add(LibraryEntry(
            user_id=user.id, game_id=game.id, status=status, rating=rating, hours_played=float(hours),
            platform=rng.choice(PLATFORMS),
            # stagger the timestamps so "recent activity" and "added this month" look real
            added_at=now - timedelta(days=rng.randint(1, 120)),
            updated_at=now - timedelta(hours=i * 7 + 1),
            last_played=(now - timedelta(days=rng.randint(1, 40))) if hours else None,
        ))
        added += 1
    return added


def seed(db: Session, quiet: bool = False) -> None:
    """
    Populate the demo accounts in an existing session. Takes the session rather
    than opening its own so it can run inside a request (the one-click demo
    login seeds on first use) as well as from the command line.
    """
    rng = random.Random(7)  # fixed seed: the demo looks the same every deploy
    seeded = seed_games(db)
    demo, friend = _user(db, DEMO), _user(db, FRIEND)
    db.flush()

    a = _stock(db, demo, DEMO_LIBRARY, rng)
    b = _stock(db, friend, FRIEND_LIBRARY, rng)

    if not db.query(Friendship).filter_by(requester_id=demo.id, addressee_id=friend.id).first():
        db.add(Friendship(requester_id=demo.id, addressee_id=friend.id, state=FriendState.accepted))

    db.commit()
    if not quiet:
        print(f"catalogue: +{seeded} games")
        print(f"{DEMO['email']} / {DEMO['password']}  (+{a} games)")
        print(f"{FRIEND['email']} / {FRIEND['password']}  (+{b} games, already friends with demo)")


def main() -> None:
    # run standalone: make sure the schema exists first, since this is often the
    # first thing executed on a fresh deployment
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
