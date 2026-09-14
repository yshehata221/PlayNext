"""
Thin IGDB client. IGDB sits behind Twitch OAuth, so we grab a client-credentials
token, cache it, and query with their Apicalypse query language.

Everything here degrades gracefully: with no credentials configured, `search`
returns [] and the games router falls back to the local database.
"""
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings
from ..models import Game
from .cache import cached

log = logging.getLogger("uvicorn.error")

_token: dict = {"value": None, "expires": 0}


def configured() -> bool:
    return bool(settings.igdb_client_id and settings.igdb_client_secret)


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _get_token() -> str:
    if _token["value"] and _token["expires"] > time.time():
        return _token["value"]
    r = httpx.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": settings.igdb_client_id,
            "client_secret": settings.igdb_client_secret,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + data["expires_in"] - 60
    return _token["value"]


# IGDB deprecates fields from time to time (`category` became `game_type`), and a
# query naming a dead field returns nothing rather than an error - so we keep the
# field list conservative and fall back to a minimal set if a query is rejected.
FIELDS = (
    "name,slug,summary,first_release_date,aggregated_rating,total_rating,total_rating_count,"
    "genres.name,themes.name,player_perspectives.name,game_modes.name,"
    "involved_companies.developer,involved_companies.company.name,platforms.abbreviation,"
    "cover.image_id,screenshots.image_id,artworks.image_id,videos.video_id,videos.name,"
    "parent_game,version_parent,platforms.name,external_games.uid,external_games.category"
)
MINIMAL_FIELDS = "name,slug,summary,first_release_date,genres.name,cover.image_id,parent_game,version_parent"

# DLC, expansions and "Game of the Year" re-releases point at a parent; real
# games don't. This is a relational check, so it survives enum renames.
def is_standalone(raw: dict) -> bool:
    return not raw.get("parent_game") and not raw.get("version_parent")


def _post(body: str, endpoint: str = "games") -> list[dict] | dict:
    r = httpx.post(
        f"https://api.igdb.com/v4/{endpoint}",
        headers={"Client-ID": settings.igdb_client_id, "Authorization": f"Bearer {_get_token()}"},
        content=body,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def count(where: str) -> int:
    """Total rows matching a where clause, via IGDB's /games/count endpoint."""
    if not configured():
        return 0
    try:
        r = httpx.post(
            "https://api.igdb.com/v4/games/count",
            headers={"Client-ID": settings.igdb_client_id, "Authorization": f"Bearer {_get_token()}"},
            content=f"where {where};",
            timeout=6,
        )
        r.raise_for_status()
        return int(r.json().get("count", 0))
    except (httpx.HTTPError, ValueError, TypeError):
        return 0


@cached(ttl=600)
def _query(body: str) -> list[dict]:
    """Run a query; on rejection, retry once with the minimal field set."""
    try:
        return _post(body)  # type: ignore[return-value]
    except httpx.HTTPStatusError as e:
        if e.response.status_code not in (400, 422):
            raise
        log.warning("IGDB rejected a query (%s): %s", e.response.status_code, e.response.text[:200])
        return _post(body.replace(FIELDS, MINIMAL_FIELDS))  # type: ignore[return-value]


@cached(ttl=1800)
def count(where: list[str] | None = None) -> int:
    """How many games match, via IGDB's /count endpoint - used for 'N games' labels."""
    if not configured():
        return 0
    clause = f'where {" & ".join(where)};' if where else ""
    try:
        data = _post(f"{clause}", endpoint="games/count")
        return int(data.get("count", 0)) if isinstance(data, dict) else 0
    except (httpx.HTTPError, ValueError, TypeError):
        return 0


def _clauses(genre: str | None, platform: str | None, year_min: int | None, year_max: int | None) -> list[str]:
    where: list[str] = []
    if genre:
        where.append(f'genres.name ~ *"{genre.replace(chr(34), "")}"*')
    if platform:
        where.append(f'platforms.name ~ *"{platform.replace(chr(34), "")}"*')
    if year_min:
        where.append(f"first_release_date > {int(datetime(year_min, 1, 1).timestamp())}")
    if year_max:
        where.append(f"first_release_date < {int(datetime(year_max, 12, 31).timestamp())}")
    return where


def filters(genre=None, platform=None, year_min=None, year_max=None) -> list[str]:
    """Public wrapper over the filter clauses, for callers building count queries."""
    return _clauses(genre, platform, year_min, year_max)


def search(
    query: str, limit: int = 10, offset: int = 0,
    genre: str | None = None, platform: str | None = None,
    year_min: int | None = None, year_max: int | None = None,
) -> list[dict]:
    """
    IGDB's `search` can't be combined with `where` or `offset`, so as soon as
    there's a filter or a second page we switch to a name match, which supports
    both. Plain first-page searches keep `search` for its better relevance.
    """
    if not configured():
        return []
    extra = _clauses(genre, platform, year_min, year_max)
    if offset or extra:
        safe = query.replace('"', "")
        where = " & ".join([f'name ~ *"{safe}"*'] + extra)
        body = (f'fields {FIELDS}; where {where}; '
                f'sort total_rating_count desc; limit {limit * 2}; offset {offset};')
    else:
        body = f'search "{query}"; fields {FIELDS}; limit {limit * 3};'
    return [g for g in _query(body) if is_standalone(g)][:limit]


# Canonical filter options. IGDB's own genre and platform lists run to hundreds
# of entries, most of them long-dead hardware, so we offer the ones people
# actually search by. Filtering is done on the nested name, which means no
# brittle numeric ids to keep in sync.
GENRES = [
    "Adventure", "Role-playing (RPG)", "Shooter", "Platform", "Puzzle", "Racing",
    "Simulator", "Sport", "Strategy", "Real Time Strategy (RTS)", "Turn-based strategy (TBS)",
    "Fighting", "Hack and slash/Beat 'em up", "Indie", "Arcade", "Music",
    "Point-and-click", "Tactical", "Visual Novel", "Card & Board Game", "MOBA",
]
PLATFORMS = [
    ("PC (Microsoft Windows)", "PC"),
    ("PlayStation 5", "PlayStation 5"),
    ("PlayStation 4", "PlayStation 4"),
    ("Xbox Series X|S", "Xbox Series X|S"),
    ("Xbox One", "Xbox One"),
    ("Nintendo Switch", "Nintendo Switch"),
    ("Nintendo Switch 2", "Nintendo Switch 2"),
    ("Mac", "Mac"),
    ("Linux", "Linux"),
    ("iOS", "iOS"),
    ("Android", "Android"),
    ("Nintendo 3DS", "Nintendo 3DS"),
    ("PlayStation 3", "PlayStation 3"),
    ("Xbox 360", "Xbox 360"),
    ("Wii U", "Wii U"),
    ("Nintendo 64", "Nintendo 64"),
    ("Super Nintendo Entertainment System", "SNES"),
    ("Sega Mega Drive/Genesis", "Mega Drive"),
]

SORTS = {
    "relevance": "total_rating_count desc",
    "title": "name asc",
    "year": "first_release_date desc",
    "score": "total_rating desc",
}


def catalogue_where(genre=None, platform=None, year_min=None, year_max=None) -> list[str]:
    """
    Shared filter for catalogue browsing: real games only, no DLC or re-releases.
    Deliberately no popularity floor - the point of a catalogue is that all
    ~350,000 entries are reachable by paging, not just the famous ones. Ordering
    by rating count keeps the first pages recognisable.
    """
    return ["parent_game = null", "version_parent = null", "cover != null"] + _clauses(genre, platform, year_min, year_max)


def browse(
    genre: str | None = None,
    platform: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    sort: str = "relevance",
    limit: int = 24,
    offset: int = 0,
) -> list[dict]:
    """Catalogue browse across every platform IGDB knows, with filters and paging."""
    if not configured():
        return []
    body = (f'fields {FIELDS}; where {browse_where(genre, platform, year_min, year_max, sort)}; '
            f'sort {SORTS.get(sort, SORTS["relevance"])}; limit {limit}; offset {offset};')
    return _query(body)


def browse_where(genre, platform, year_min, year_max, sort: str = "relevance") -> str:
    """The where clause behind a catalogue browse, shared with count()."""
    where = ["parent_game = null", "version_parent = null"] + _clauses(genre, platform, year_min, year_max)
    if sort == "relevance":
        # ranking by popularity needs *some* signal, or page one is a wall of
        # unknown titles; a single rating is enough to sort by
        where.append("total_rating_count > 0")
    return " & ".join(where)


def popular_where(genre, platform) -> str:
    since = int((datetime.now(tz=timezone.utc) - timedelta(days=730)).timestamp())
    return " & ".join(["parent_game = null", "version_parent = null",
                       f"first_release_date > {since}", "total_rating_count > 1"] + _clauses(genre, platform, None, None))


def popular(limit: int = 24, offset: int = 0, genre: str | None = None, platform: str | None = None) -> list[dict]:
    """Games released in the last couple of years, most-rated first."""
    if not configured():
        return []
    body = (f'fields {FIELDS}; where {popular_where(genre, platform)}; '
            f'sort total_rating_count desc; limit {limit}; offset {offset};')
    return _query(body)


def _image(image_id: str, size: str) -> str:
    return f"https://images.igdb.com/igdb/image/upload/{size}/{image_id}.jpg"


def to_game(raw: dict) -> Game:
    """Map an IGDB response object onto our Game model (unsaved)."""
    developer = None
    for ic in raw.get("involved_companies", []):
        if ic.get("developer") and ic.get("company"):
            developer = ic["company"]["name"]
            break

    steam_appid = None
    for ext in raw.get("external_games", []):
        # category 1 is Steam; if the field is absent (deprecation), a numeric
        # uid that looks like an appid is still worth keeping as a guess
        uid = ext.get("uid")
        if ext.get("category") == 1 and uid and str(uid).isdigit():
            steam_appid = int(uid)
            break

    year = None
    if raw.get("first_release_date"):
        year = time.gmtime(raw["first_release_date"]).tm_year

    cover = raw.get("cover", {}).get("image_id")
    artworks = raw.get("artworks") or []
    hero = (artworks[0].get("image_id") if artworks else None) or (raw.get("screenshots") or [{}])[0].get("image_id")
    return Game(
        title=raw["name"],
        slug=raw.get("slug") or slugify(raw["name"]),
        igdb_id=raw["id"],
        steam_appid=steam_appid,
        developer=developer,
        release_year=year,
        genres=[g["name"] for g in raw.get("genres", [])],
        themes=[t["name"] for t in raw.get("themes", [])],
        perspectives=[p["name"] for p in raw.get("player_perspectives", [])],
        modes=[m["name"] for m in raw.get("game_modes", [])],
        platforms=[p["name"] for p in raw.get("platforms", []) if p.get("name")],
        critic_score=raw.get("aggregated_rating") or raw.get("total_rating"),
        # t_cover_big is only 264x374; the 2x variant is 528x748 and stays sharp
        # on a large display. IGDB also has t_720p/t_1080p, but those are 16:9
        # screenshots-style crops, not the portrait cover.
        cover_url=f"https://images.igdb.com/igdb/image/upload/t_cover_big_2x/{cover}.jpg" if cover else None,
        hero_url=_image(hero, "t_1080p") if hero else None,
        screenshots=[_image(s["image_id"], "t_screenshot_huge") for s in raw.get("screenshots", [])[:8] if s.get("image_id")],
        videos=[
            {"kind": "youtube", "src": v["video_id"], "title": v.get("name") or "Trailer",
             "thumb": f"https://img.youtube.com/vi/{v['video_id']}/hqdefault.jpg"}
            for v in raw.get("videos", [])[:4] if v.get("video_id")
        ],
        summary=raw.get("summary"),
    )
