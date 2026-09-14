"""
Keyless metadata from the Steam *store* (not the Web API - that one needs a key).

  storesearch  - find app IDs by title
  appdetails   - genres, developer, release year, art for one app

Steam's genres are coarser than IGDB's, and there are no themes, but it's free,
unauthenticated, and covers most PC games including the Game Pass ones. Rate
limit is roughly 200 requests per 5 minutes, so callers should batch sensibly.
"""
import json
import logging
import re
from datetime import datetime

import httpx

from ..models import Game
from .cache import cached
from .matching import similarity
from .steam import steam_cover

log = logging.getLogger("uvicorn.error")

# game id -> time of last lookup attempt. Keeps a page refresh from re-querying
# Steam for the same unresolvable game over and over. Process-local on purpose.
_attempted: dict[int, float] = {}
RETRY_AFTER = 60 * 60


def recently_tried(game_id: int) -> bool:
    import time
    return time.time() - _attempted.get(game_id, 0) < RETRY_AFTER


def mark_tried(game_id: int) -> None:
    import time
    _attempted[game_id] = time.time()
DEMO_SUFFIX = re.compile(r"\s*[-:(]?\s*(demo|playtest|beta|open beta|early access)\)?\s*$", re.I)

SEARCH = "https://store.steampowered.com/api/storesearch/"
DETAILS = "https://store.steampowered.com/api/appdetails"
# what the Steam client uses; returns exact (sometimes hashed) asset filenames
ITEMS = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
ASSET_BASE = "https://shared.cloudflare.steamstatic.com/store_item_assets/"

# Steam category ids -> our modes vocabulary
CATEGORY_MODES = {2: "Single player", 1: "Multiplayer", 9: "Co-operative", 38: "Co-operative", 49: "Multiplayer"}


FEATURED = "https://store.steampowered.com/api/featuredcategories"


SECTIONS = ("top_sellers", "specials", "new_releases", "coming_soon")


@cached(ttl=600)
def featured(limit: int = 24) -> list[dict]:
    """
    Keyless "what's popular right now" from the store's own featured endpoint.
    Returns raw items with id/name; the caller upserts them into our catalogue.
    """
    try:
        r = httpx.get(FEATURED, params={"cc": "gb", "l": "en"}, timeout=4)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return []
    items: list[dict] = []
    seen: set[int] = set()
    sections = ("top_sellers", "specials", "new_releases", "coming_soon")
    for key in sections:
        for item in (data.get(key) or {}).get("items", []):
            appid = item.get("id")
            if appid and appid not in seen and item.get("name"):
                seen.add(appid)
                items.append({"id": appid, "name": item["name"], "section": key,
                              "discount_percent": item.get("discount_percent") or 0,
                              "final_price": item.get("final_price"), "currency": item.get("currency")})
    return items[:limit]


@cached(ttl=900)
def search(term: str, limit: int = 10) -> list[dict]:
    try:
        r = httpx.get(SEARCH, params={"term": term, "cc": "gb", "l": "en"}, timeout=4)
        r.raise_for_status()
    except httpx.HTTPError:
        return []
    items = r.json().get("items", [])
    for it in items:
        # storesearch gives price in pence/cents under `price`
        price = it.get("price") or {}
        it["final_price"] = price.get("final")
        it["initial_price"] = price.get("initial")
        it["currency"] = price.get("currency")
    return items[:limit]


def find_appid(title: str) -> int | None:
    """Best store match for a scanner/launcher title, or None if nothing's close."""
    best, best_score = None, 0.0
    for item in search(title, limit=5):
        score = similarity(item.get("name", ""), title)
        if score > best_score:
            best, best_score = item, score
    return int(best["id"]) if best and best_score >= 0.8 else None


@cached(ttl=3600)
def assets(appid: int) -> dict | None:
    """Exact asset filenames for an app, e.g. {'library_capsule': 'abc123/library_600x900.jpg', ...}."""
    payload = {
        "ids": [{"appid": appid}],
        "context": {"language": "english", "country_code": "GB"},
        "data_request": {"include_assets": True},
    }
    try:
        r = httpx.get(ITEMS, params={"input_json": json.dumps(payload)}, timeout=4)
        r.raise_for_status()
        items = r.json().get("response", {}).get("store_items", [])
    except (httpx.HTTPError, ValueError):
        return None
    return items[0].get("assets") if items else None


@cached(ttl=1800)
def portrait_urls(appids: list[int]) -> dict[int, str]:
    """Portrait capsules for many apps in one GetItems call (browse pages need a screenful)."""
    if not appids:
        return {}
    payload = {
        "ids": [{"appid": a} for a in appids[:50]],
        "context": {"language": "english", "country_code": "GB"},
        "data_request": {"include_assets": True},
    }
    try:
        r = httpx.get(ITEMS, params={"input_json": json.dumps(payload)}, timeout=6)
        r.raise_for_status()
        items = r.json().get("response", {}).get("store_items", [])
    except (httpx.HTTPError, ValueError):
        return {}
    out: dict[int, str] = {}
    for item in items:
        a = item.get("assets") or {}
        fmt, name = a.get("asset_url_format"), a.get("library_capsule") or a.get("library_capsule_2x")
        if item.get("appid") and fmt and name:
            out[int(item["appid"])] = ASSET_BASE + fmt.replace("${FILENAME}", name).split("?")[0]
    return out


def hero_url(appid: int) -> str | None:
    """Wide key art for the page backdrop, from the same asset manifest as the capsule."""
    a = assets(appid)
    if not a:
        return None
    fmt = a.get("asset_url_format")
    name = a.get("library_hero") or a.get("page_background")
    return ASSET_BASE + fmt.replace("${FILENAME}", name).split("?")[0] if fmt and name else None


def portrait_url(appid: int) -> str | None:
    """Real URL of the 600x900 library capsule, or None if the app has none (playtests, some demos)."""
    a = assets(appid)
    if not a:
        return None
    fmt = a.get("asset_url_format")
    name = a.get("library_capsule") or a.get("library_capsule_2x")
    if not fmt or not name:
        return None
    return ASSET_BASE + fmt.replace("${FILENAME}", name).split("?")[0]


@cached(ttl=3600)
def details(appid: int) -> dict | None:
    try:
        r = httpx.get(DETAILS, params={"appids": appid, "cc": "gb", "l": "en"}, timeout=4)
        r.raise_for_status()
    except httpx.HTTPError:
        return None
    entry = r.json().get(str(appid), {})
    return entry.get("data") if entry.get("success") else None


TAGS = re.compile(r"<[^>]+>")


def _clean_requirements(html: str | None) -> str | None:
    """Steam returns requirements as a blob of HTML; flatten it to readable lines."""
    if not html:
        return None
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("</li>", "\n").replace("</p>", "\n")
    text = TAGS.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    lines = [" ".join(l.split()) for l in text.split("\n")]
    return "\n".join(l for l in lines if l) or None


def apply(game: Game, data: dict) -> None:
    """Fill gaps on a Game from an appdetails payload. Never overwrites existing values."""
    if not game.developer and data.get("developers"):
        game.developer = data["developers"][0]
    if not game.genres and data.get("genres"):
        game.genres = [g["description"] for g in data["genres"] if g["description"] not in ("Free To Play", "Early Access")]
    if not game.modes and data.get("categories"):
        game.modes = sorted({CATEGORY_MODES[c["id"]] for c in data["categories"] if c["id"] in CATEGORY_MODES})
    if not game.release_year and data.get("release_date", {}).get("date"):
        for fmt in ("%d %b, %Y", "%b %d, %Y", "%b %Y", "%Y"):
            try:
                game.release_year = datetime.strptime(data["release_date"]["date"], fmt).year
                break
            except ValueError:
                continue
    if not game.critic_score and data.get("metacritic"):
        game.critic_score = float(data["metacritic"]["score"])
    if not game.summary and data.get("short_description"):
        game.summary = data["short_description"]

    # up to eight screenshots; Steam gives both a thumbnail and a full-size URL
    if not game.screenshots and data.get("screenshots"):
        game.screenshots = [
            s["path_full"].split("?")[0]
            for s in data["screenshots"][:8]
            if s.get("path_full")
        ]

    # trailers. Steam hosts the files itself, so these play without an embed;
    # it serves http URLs in places, which a https page would block - hence the
    # rewrite to https rather than trusting the field as given.
    if not game.videos and data.get("movies"):
        vids = []
        for m in data["movies"][:4]:
            src = (m.get("mp4") or {}).get("max") or (m.get("webm") or {}).get("max")
            if src:
                vids.append({
                    "kind": "mp4",
                    "src": src.replace("http://", "https://").split("?")[0],
                    "title": m.get("name") or "Trailer",
                    "thumb": (m.get("thumbnail") or "").replace("http://", "https://") or None,
                })
        game.videos = vids

    # PC system requirements (Steam only ships these for Windows/Mac/Linux titles)
    reqs = data.get("pc_requirements") or {}
    if isinstance(reqs, dict) and not game.requirements:
        minimum, recommended = _clean_requirements(reqs.get("minimum")), _clean_requirements(reqs.get("recommended"))
        if minimum or recommended:
            game.requirements = {k: v for k, v in (("minimum", minimum), ("recommended", recommended)) if v}

    # a game on the Steam store is by definition on PC
    if "PC (Microsoft Windows)" not in (game.platforms or []):
        extra = ["PC (Microsoft Windows)"]
        if (data.get("platforms") or {}).get("mac"):
            extra.append("Mac")
        if (data.get("platforms") or {}).get("linux"):
            extra.append("Linux")
        game.platforms = list(dict.fromkeys((game.platforms or []) + extra))
    # The store's header_image is the one URL we *know* works - newer games sit on
    # a different CDN host, sometimes inside a hashed folder, so guessed paths 404.
    # Store the exact header; the frontend tries portrait variants first and falls
    # back to this. Only replace a cover we guessed ourselves, never a real one.
    header = data.get("header_image")
    if header and (not game.cover_url or is_guessed_steam_url(game.cover_url)):
        game.cover_url = header.split("?")[0]
    elif not game.cover_url:
        game.cover_url = steam_cover(int(data["steam_appid"]))


def is_guessed_steam_url(url: str) -> bool:
    return url.startswith("https://cdn.cloudflare.steamstatic.com/steam/apps/")


def is_landscape_steam_url(url: str) -> bool:
    return "steamstatic.com" in url and url.endswith("/header.jpg")


def is_portrait_steam_url(url: str) -> bool:
    return "steamstatic.com" in url and "library_600x900" in url and not is_guessed_steam_url(url)


_verified: set[str] = set()


def url_exists(url: str) -> bool:
    """
    Does this URL really serve an image? Remembered for the life of the process.
    Steam's CDN answers HEAD with 200 even for missing files, so this has to be a
    GET - streamed, so we read headers and bail without downloading the picture.
    """
    if url in _verified:
        return True
    try:
        with httpx.stream("GET", url, timeout=4, follow_redirects=True) as r:
            ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")
    except httpx.HTTPError:
        return False
    if ok:
        _verified.add(url)
    else:
        log.info("steam art: stored url is not an image (%s), re-resolving", url)
    return ok


def needs_enrich(game: Game) -> bool:
    """Missing metadata, media, or art that isn't a verified portrait capsule."""
    if not game.cover_url or not game.genres or not game.platforms:
        return True
    if game.steam_appid and (game.requirements is None or not game.screenshots or not game.hero_url or not game.videos):
        return True
    if "steamstatic.com" not in game.cover_url:
        return False
    return not (is_portrait_steam_url(game.cover_url) and game.cover_url in _verified)


def best_portrait(game: Game, data: dict | None) -> str | None:
    """
    Try hard to find real portrait art for a Steam install:
      1. the installed app's own library capsule
      2. the parent game, if this is a demo/playtest (appdetails says so via `fullgame`)
      3. a store search on the cleaned-up title
    """
    tried: list[int] = []
    candidates: list[int] = []
    if game.steam_appid:
        candidates.append(game.steam_appid)
    if data and data.get("fullgame", {}).get("appid"):
        try:
            candidates.append(int(data["fullgame"]["appid"]))
        except (TypeError, ValueError):
            pass
    clean = DEMO_SUFFIX.sub("", game.title).strip()
    alt = find_appid(clean)
    if alt:
        candidates.append(alt)

    for appid in candidates:
        if appid in tried:
            continue
        tried.append(appid)
        url = portrait_url(appid)
        if url:
            if appid != game.steam_appid:
                log.info("steam art: %s -> using app %s (%s)", game.title, appid, "parent/search")
            return url
    log.info("steam art: no portrait capsule for %s (tried %s), keeping header", game.title, tried)
    return None


def _appid_taken_by(db, appid: int, game: Game) -> Game | None:
    """Another catalogue row already holding this appid, if any."""
    if db is None:
        return None
    return db.query(Game).filter(Game.steam_appid == appid, Game.id != game.id).first()


def _borrow_metadata(game: Game, twin: Game) -> None:
    """
    Copy what we can from the row that already owns this appid. Two rows for one
    game happen legitimately - a scanner import and a store search can both
    create one before we know they're the same - and `steam_appid` is unique, so
    the second row can't claim it. Rather than fail, it inherits the details.
    """
    game.cover_url = game.cover_url or twin.cover_url
    game.genres = game.genres or twin.genres
    game.themes = game.themes or twin.themes
    game.modes = game.modes or twin.modes
    game.platforms = game.platforms or twin.platforms
    game.requirements = game.requirements or twin.requirements
    game.developer = game.developer or twin.developer
    game.release_year = game.release_year or twin.release_year
    game.critic_score = game.critic_score or twin.critic_score
    game.summary = game.summary or twin.summary
    game.hours_main = game.hours_main or twin.hours_main


def enrich(game: Game, db=None) -> bool:
    """
    Look a game up by title if it has no appid, then fill in details.
    Pass `db` so a clash on the unique `steam_appid` can be detected before the
    flush rather than blowing up the caller's transaction.
    """
    if game.steam_appid is None:
        # try the title as-is, then with edition/demo noise stripped, then the
        # first few words (launchers often append subtitles the store lacks)
        clean = DEMO_SUFFIX.sub("", game.title).strip()
        words = clean.split()
        for attempt in dict.fromkeys([game.title, clean, " ".join(words[:4]), " ".join(words[:2])]):
            if len(attempt) < 3:
                continue
            found = find_appid(attempt)
            if not found:
                continue
            twin = _appid_taken_by(db, found, game)
            if twin is not None:
                # can't claim the id; take the metadata instead
                log.info("steam: %r matches app %s, already held by %r - copying its details", game.title, found, twin.title)
                _borrow_metadata(game, twin)
                return True
            game.steam_appid = found
            log.info("steam: matched %r to app %s", game.title, found)
            break
        if game.steam_appid is None:
            return False

    data = None
    art_appid = game.steam_appid
    if not game.genres or game.requirements is None or is_guessed_steam_url(game.cover_url or ""):
        data = details(game.steam_appid)
        if data is None:
            # playtests and demos have no store page of their own: find the real game
            alt = find_appid(game.title)
            if alt and alt != game.steam_appid:
                data = details(alt)
                art_appid = alt
        if data:
            apply(game, data)

    if game.steam_appid and not game.hero_url:
        game.hero_url = hero_url(game.steam_appid)

    # upgrade anything that isn't a confirmed portrait capsule - including a
    # portrait-looking URL that turns out to 404 (older versions guessed those)
    cover = game.cover_url or ""
    if is_portrait_steam_url(cover) and url_exists(cover):
        pass
    elif not cover or "steamstatic.com" in cover:
        if data is None:
            data = details(art_appid)
        portrait = best_portrait(game, data)
        if portrait:
            game.cover_url = portrait

    if game.cover_url is None:
        game.cover_url = steam_cover(game.steam_appid)
    return True
