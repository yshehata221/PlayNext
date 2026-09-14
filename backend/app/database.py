from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# sqlite needs this flag because FastAPI may hit the db from different threads
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)

if settings.database_url.startswith("sqlite"):
    # WAL mode lets readers proceed while a writer (e.g. an import doing network
    # lookups) has a transaction open; without it the whole app stalls behind it
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# create_all() only creates missing *tables*, never missing columns, so a database
# from an earlier version needs its new columns adding by hand. SQLite and Postgres
# both support ADD COLUMN, and IF NOT EXISTS keeps this safe to run every startup.
# (column, type, backfill value). ADD COLUMN leaves existing rows NULL, and a
# model-level `default=list` only applies to new inserts, so list columns must be
# backfilled or every response carrying an old row fails validation.
NEW_COLUMNS = {
    "users": [
        ("username", "VARCHAR(32)", None),
        ("email_verified", "BOOLEAN", "0"),
    ],
    "games": [
        ("platforms", "JSON", "'[]'"),
        ("requirements", "JSON", None),
        ("hero_url", "VARCHAR(512)", None),
        ("screenshots", "JSON", "'[]'"),
        ("videos", "JSON", "'[]'"),
    ],
}


def ensure_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in NEW_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, sql_type, backfill in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))
                if backfill is not None:
                    conn.execute(text(f"UPDATE {table} SET {name} = {backfill} WHERE {name} IS NULL"))


def backfill_usernames() -> None:
    """
    Give pre-existing accounts a handle. Usernames are unique, so this can't be
    a single UPDATE - each one is derived from the display name and then nudged
    with a suffix until it's free.
    """
    import re

    from .models import User

    with SessionLocal() as db:
        missing = db.query(User).filter(User.username.is_(None)).all()
        if not missing:
            return
        taken = {u.username for u in db.query(User).filter(User.username.isnot(None)).all()}
        for user in missing:
            base = re.sub(r"[^a-z0-9_]", "", (user.display_name or user.email.split("@")[0]).lower())[:20] or "player"
            candidate, n = base, 1
            while candidate in taken or len(candidate) < 3:
                n += 1
                candidate = f"{base}{n}"
            user.username = candidate
            taken.add(candidate)
        db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
