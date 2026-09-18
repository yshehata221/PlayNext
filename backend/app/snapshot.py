"""
Capture a snapshot of the demo account's API responses.

    python -m app.snapshot ../frontend/src/demo/snapshot.json

The frontend can be built against this instead of a live API, which is what
makes the GitHub Pages demo work with no backend at all: every read is served
from the snapshot, and edits are applied to an in-memory copy.

Only GET responses are captured. Anything that changes data is simulated in the
browser, so the demo can't be broken by whoever clicks it.
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from .database import Base, SessionLocal, engine, ensure_columns
from .demo import DEMO, seed
from .main import app


def capture(out: Path) -> None:
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    with SessionLocal() as db:
        seed(db, quiet=True)

    client = TestClient(app)
    token = client.post("/auth/login", data={"username": DEMO["email"], "password": DEMO["password"]}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    paths: list[str] = [
        "/config",
        "/auth/me",
        "/library?sort=added",
        "/stats",
        "/wishlist",
        "/friends",
        "/recommendations/plan?hours=2",
        "/recommendations/plan?hours=3",
        "/browse/for-you?limit=48&offset=0",
        "/browse/popular?section=all&limit=48&offset=0",
    ]

    # the recommender is the point of the app, so capture every combination the
    # UI can ask for - time budgets crossed with moods, from both sources
    for source in ("backlog", "discover"):
        for hours in ("", "&hours=0.5", "&hours=1", "&hours=2", "&hours=3"):
            for mood in ("", "&mood=story", "&mood=relaxing", "&mood=quick", "&mood=new"):
                paths.append(f"/recommendations?source={source}&limit=8{hours}{mood}")

    data: dict[str, object] = {}

    def grab(path: str) -> object | None:
        response = client.get(path, headers=auth)
        if response.status_code != 200:
            return None
        data[path] = response.json()
        return data[path]

    for path in paths:
        grab(path)

    # every game page the demo library can reach
    for entry in data["/library?sort=added"]:  # type: ignore[index]
        grab(f"/library/{entry['id']}")
        grab(f"/browse/game/{entry['game']['id']}")
        grab(f"/browse/game/{entry['game']['id']}/similar?limit=6")

    for entry in data["/wishlist"]:  # type: ignore[index]
        grab(f"/browse/game/{entry['game']['id']}")

    for item in data.get("/browse/for-you?limit=48&offset=0", {}).get("items", [])[:12]:  # type: ignore[union-attr]
        grab(f"/browse/game/{item['game']['id']}")
        grab(f"/browse/game/{item['game']['id']}/similar?limit=6")

    # co-op picks, with and without the multiplayer filter
    for friend in data["/friends"]:  # type: ignore[index]
        uid = friend["user"]["id"]
        for extra in ("", "&together_only=false", "&hours=1", "&hours=2", "&hours=3"):
            grab(f"/friends/{uid}/coop?limit=10{extra}")

    # a few searches, so the search box isn't dead in the demo
    for term in ("red", "hades", "elden", "portal", "witcher", "overwatch", "grand"):
        grab(f"/browse/search?q={term}&limit=48&offset=0")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":")))
    size = out.stat().st_size / 1024
    print(f"captured {len(data)} responses -> {out} ({size:.0f} KB)")


if __name__ == "__main__":
    capture(Path(sys.argv[1] if len(sys.argv) > 1 else "snapshot.json"))
