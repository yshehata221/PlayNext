"""
Tests run on an in-memory SQLite database so CI needs no Postgres. The app's
get_db dependency is swapped for one bound to that engine.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seed import seed_games


@pytest.fixture(autouse=True)
def no_rate_limit():
    """
    Tests register and log in dozens of times; the production limit of ten a
    minute would fail them. Switched off here and exercised on purpose in
    test_security.py instead.
    """
    from app.limiter import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never talk to the Steam store."""
    from app.services import msstore, steamstore
    monkeypatch.setattr(steamstore, "search", lambda term, limit=10: [])
    monkeypatch.setattr(steamstore, "details", lambda appid: None)
    monkeypatch.setattr(msstore, "lookup", lambda store_id, market="GB": None)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as s:
        seed_games(s)
        yield s


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client):
    """Register a user and return the auth header."""
    r = client.post("/auth/register", json={"email": "t@example.com", "display_name": "Tester",
                                            "username": "tester", "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def auth2(client):
    """A second account, for anything involving two people."""
    r = client.post("/auth/register", json={"email": "f@example.com", "display_name": "Friend",
                                            "username": "buddy", "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
