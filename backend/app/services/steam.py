"""
Steam library import. Only needs the user's 64-bit SteamID and a public profile.
GetOwnedGames gives us appid, name and lifetime playtime in minutes - enough to
create library entries. Genre data for games Steam adds that we've never seen
gets filled in later by a metadata refresh (see routers/games.py refresh).
"""
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Game, LibraryEntry, Status, User
from .igdb import slugify


def steam_cover(appid: int) -> str:
    """Portrait art from Steam's public CDN - no API key needed."""
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_600x900.jpg"


def fetch_owned_games(steam_id: str) -> list[dict]:
    if not settings.steam_api_key:
        raise RuntimeError("STEAM_API_KEY is not configured")
    r = httpx.get(
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
        params={
            "key": settings.steam_api_key,
            "steamid": steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1,
            "format": "json",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("response", {}).get("games", [])


def import_library(db: Session, user: User, owned: list[dict]) -> dict:
    """Idempotent: re-running updates playtime rather than duplicating entries."""
    imported = updated = skipped = 0

    for item in owned:
        appid = item.get("appid")
        name = item.get("name")
        if not appid or not name:
            skipped += 1
            continue

        game = db.query(Game).filter(Game.steam_appid == appid).first()
        if game is None:
            # try to match a seeded/IGDB game by slug before creating a bare one
            game = db.query(Game).filter(Game.slug == slugify(name)).first()
            if game is not None and game.steam_appid is None:
                game.steam_appid = appid
        if game is None:
            game = Game(
                title=name,
                slug=slugify(name) or f"steam-{appid}",
                steam_appid=appid,
                cover_url=steam_cover(appid),
            )
            db.add(game)
            db.flush()

        hours = round(item.get("playtime_forever", 0) / 60, 1)
        last = item.get("rtime_last_played")
        last_played = datetime.fromtimestamp(last, tz=timezone.utc) if last else None

        entry = db.query(LibraryEntry).filter_by(user_id=user.id, game_id=game.id).first()
        if entry is None:
            entry = LibraryEntry(
                user_id=user.id,
                game_id=game.id,
                platform="steam",
                # a game with real hours on it has clearly been started
                status=Status.playing if hours >= 1 else Status.backlog,
                hours_played=hours,
                last_played=last_played,
            )
            db.add(entry)
            imported += 1
        else:
            # never lower hours the user typed in themselves
            if hours > entry.hours_played:
                entry.hours_played = hours
            if last_played and (entry.last_played is None or last_played > entry.last_played):
                entry.last_played = last_played
            updated += 1

    db.commit()
    return {"imported": imported, "updated": updated, "skipped": skipped}
