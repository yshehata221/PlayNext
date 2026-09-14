"""
Browse: find games you don't own yet.

  GET /browse/search     the whole Steam catalogue plus our own, with filters
  GET /browse/popular    top sellers / new releases / deals / coming soon
  GET /browse/for-you    the recommender over games you don't own

All paged (limit + offset) so the UI can offer "Load more". Everything is
keyless: search and popular come from public Steam store endpoints, taste
scores from the user's own ratings.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Game, LibraryEntry, User
from ..schemas import BrowseItem, BrowsePage
from ..services import igdb, steamstore
from ..services.matching import normalise
from ..services.recommender import collaborative_scores, get_recommender
from ..services.steam import steam_cover

log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/browse", tags=["browse"])

SORTS = ("relevance", "title", "year", "score", "price")


def _from_igdb(db: Session, raws: list[dict]) -> list[Game]:
    """Upsert IGDB results into our catalogue, keyed on igdb_id then slug."""
    out: list[Game] = []
    for raw in raws:
        game = db.query(Game).filter(Game.igdb_id == raw["id"]).first()
        if game is None:
            fresh = igdb.to_game(raw)
            clash = db.query(Game).filter(Game.slug == fresh.slug).first()
            if clash:
                clash.igdb_id = fresh.igdb_id
                clash.cover_url = clash.cover_url or fresh.cover_url
                clash.genres = clash.genres or fresh.genres
                game = clash
            else:
                game = fresh
                db.add(game)
            db.flush()
        out.append(game)
    return out


def _owned(db: Session, user: User) -> dict[int, LibraryEntry]:
    return {e.game_id: e for e in db.query(LibraryEntry).filter_by(user_id=user.id).all()}


def _fix_art(db: Session, games: list[Game]) -> None:
    """One batched asset lookup for every game still on a guessed cover URL."""
    need = [g for g in games if g.steam_appid and (g.cover_url is None or steamstore.is_guessed_steam_url(g.cover_url))]
    if not need:
        return
    urls = steamstore.portrait_urls([g.steam_appid for g in need if g.steam_appid])
    for g in need:
        url = urls.get(g.steam_appid or 0)
        if url:
            g.cover_url = url
        elif g.cover_url is None and g.steam_appid:
            g.cover_url = steam_cover(g.steam_appid)


def _upsert(db: Session, appid: int, title: str) -> Game:
    """Get or create the catalogue row for a store result; art is filled in by _fix_art."""
    game = db.query(Game).filter(Game.steam_appid == appid).first()
    if game is None:
        slug = igdb.slugify(title) or f"steam-{appid}"
        game = db.query(Game).filter(Game.slug == slug).first()
        if game is not None and game.steam_appid is None:
            game.steam_appid = appid
        if game is None:
            game = Game(title=title, slug=slug, steam_appid=appid)
            db.add(game)
            db.flush()
    return game


def _item(game: Game, owned: dict[int, LibraryEntry], **extra) -> BrowseItem:
    entry = owned.get(game.id)
    return BrowseItem(
        game=game, in_library=entry is not None,
        status=entry.status if entry else None, entry_id=entry.id if entry else None,
        **extra,
    )


def _price(final: int | None, currency: str | None) -> str | None:
    if final is None or not currency:
        return None
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency, "")
    return f"{symbol}{final / 100:.2f}" if final else "Free"


def _apply_filters(games: list[Game], genre: str | None, year_min: int | None, year_max: int | None, unreleased: bool) -> list[Game]:
    out = []
    for g in games:
        if genre and not any(genre.lower() in x.lower() for x in (g.genres or []) + (g.themes or [])):
            continue
        if year_min and (g.release_year or 0) < year_min:
            continue
        if year_max and (g.release_year or 9999) > year_max:
            continue
        if not unreleased and g.release_year is None and not g.genres:
            pass  # unknown year is not the same as unreleased; keep it
        out.append(g)
    return out


def _sort(games: list[Game], sort: str) -> list[Game]:
    if sort == "title":
        return sorted(games, key=lambda g: g.title.lower())
    if sort == "year":
        return sorted(games, key=lambda g: g.release_year or 0, reverse=True)
    if sort == "score":
        return sorted(games, key=lambda g: g.critic_score or 0, reverse=True)
    return games  # relevance: keep the store's own ordering


def _page(items: list, limit: int, offset: int) -> tuple[list, bool]:
    return items[offset:offset + limit], offset + limit < len(items)


def _genres_of(games: list[Game]) -> list[str]:
    """Genre options: IGDB's canonical list when available, else whatever's in the results."""
    if igdb.configured():
        return igdb.GENRES
    seen: dict[str, int] = {}
    for g in games:
        for x in g.genres or []:
            seen[x] = seen.get(x, 0) + 1
    return [g for g, _ in sorted(seen.items(), key=lambda kv: -kv[1])][:18]


def _platform_options() -> list[dict]:
    """Platform filter options. Only meaningful with IGDB; Steam's catalogue is PC-only."""
    if not igdb.configured():
        return []
    return [{"value": value, "label": label} for value, label in igdb.PLATFORMS]


@router.get("/game/{game_id}", response_model=BrowseItem)
def game_detail(game_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Full detail for any catalogue game, owned or not. Fills in anything missing
    on demand (art, genres, platforms, PC requirements) so a browse result opens
    with real data rather than a stub.
    """
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(404, "Game not found")

    # Read the title up front: after a failed flush the session is in a rolled
    # back state, and touching an ORM attribute then raises a *second* exception
    # from inside the error handler.
    title = game.title

    # Enrichment hits two third-party APIs. Either can rate-limit, time out or
    # return something unexpected, and none of that should stop the page opening
    # with whatever we already know - so failures are logged, not raised.
    try:
        if steamstore.needs_enrich(game):
            steamstore.enrich(game, db=db)
    except Exception as e:
        db.rollback()
        log.warning("browse detail: Steam enrichment failed for %s: %s", title, e)

    try:
        # Steam only knows about PC, so ask IGDB for the full platform list
        if igdb.configured() and len(game.platforms or []) <= 1:
            for raw in igdb.search(game.title, limit=3):
                if normalise(raw.get("name", "")) == normalise(game.title):
                    names = [p["name"] for p in raw.get("platforms", []) if p.get("name")]
                    if names:
                        game.platforms = list(dict.fromkeys((game.platforms or []) + names))
                    if not game.igdb_id:
                        game.igdb_id = raw["id"]
                    break
    except Exception as e:
        db.rollback()
        log.warning("browse detail: IGDB platform lookup failed for %s: %s", title, e)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        log.warning("browse detail: could not save enrichment for %s: %s", title, e)

    # re-read after any rollback so the response reflects what's actually stored
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(404, "Game not found")
    owned = _owned(db, user)
    return _item(game, owned)


@router.get("/game/{game_id}/similar", response_model=list[BrowseItem])
def similar(game_id: int, limit: int = Query(8, ge=1, le=24),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Games most like this one, by the same tag-vector similarity the recommender
    uses - so "you might also like" is driven by the same engine as Tonight,
    not a separate heuristic.
    """
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(404, "Game not found")

    games = db.query(Game).all()
    rec = get_recommender(db)
    if game.id not in rec.index:
        return []

    vec = rec.matrix[rec.index[game.id]]
    scored: list[tuple[float, Game]] = []
    for other in games:
        if other.id == game.id or other.id not in rec.index:
            continue
        sim = float(vec @ rec.matrix[rec.index[other.id]])
        if sim > 0:
            scored.append((sim, other))
    scored.sort(key=lambda p: (p[0], p[1].critic_score or 0), reverse=True)

    page = [g for _, g in scored[:limit]]
    _fix_art(db, page)
    db.commit()
    owned = _owned(db, user)
    return [_item(g, owned, match=round(100 * sim, 1)) for sim, g in zip([s for s, _ in scored[:limit]], page)]


@router.get("/search", response_model=BrowsePage)
def search(
    q: str = Query(min_length=2),
    genre: str | None = None,
    platform: str | None = None,
    year_min: int | None = Query(None, ge=1970, le=2100),
    year_max: int | None = Query(None, ge=1970, le=2100),
    sort: str = Query("relevance", pattern="^(" + "|".join(SORTS) + ")$"),
    hide_owned: bool = False,
    limit: int = Query(48, ge=1, le=120),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned = _owned(db, user)
    prices: dict[int, tuple[int | None, str | None]] = {}

    if igdb.configured():
        # IGDB pages server-side across every platform, so ask for exactly this page
        raws = igdb.search(q, limit=limit + 1, offset=offset, genre=genre, platform=platform,
                           year_min=year_min, year_max=year_max)
        results = _from_igdb(db, raws[:limit])
        has_more = len(raws) > limit
        if offset == 0:
            like = f"%{q}%"
            have = {g.id for g in results}
            for g in db.query(Game).filter(Game.title.ilike(like)).limit(10).all():
                if g.id not in have:
                    results.append(g)
        # IGDB already applied genre/platform/year server-side
        if hide_owned:
            results = [g for g in results if g.id not in owned]
        page = _sort(results, sort)
        # a name match plus filters: ask IGDB how many there really are
        safe = q.replace('"', "")
        total = igdb.count([f'name ~ *"{safe}"*'] + igdb.filters(genre, platform, year_min, year_max)) or (offset + len(page))
    else:
        # Steam-only: one search, filtered and paged locally
        results = []
        for hit in steamstore.search(q, limit=60):
            game = _upsert(db, int(hit["id"]), hit["name"])
            results.append(game)
            prices[game.id] = (hit.get("final_price"), hit.get("currency"))
        like = f"%{q}%"
        have = {g.id for g in results}
        for g in db.query(Game).filter(or_(Game.title.ilike(like), Game.developer.ilike(like))).limit(60).all():
            if g.id not in have:
                results.append(g)
        if hide_owned:
            results = [g for g in results if g.id not in owned]
        filtered = _sort(_apply_filters(results, genre, year_min, year_max, True), sort)
        page, has_more = _page(filtered, limit, offset)
        total = len(filtered)

    _fix_art(db, page)
    db.commit()
    return BrowsePage(
        items=[_item(g, owned, price=_price(*prices.get(g.id, (None, None)))) for g in page],
        total=total, has_more=has_more, genres=_genres_of(page), platforms=_platform_options(),
        source="igdb" if igdb.configured() else "steam",
    )


@router.get("/popular", response_model=BrowsePage)
def popular(
    section: str = Query("all", pattern="^(all|catalogue|top_sellers|specials|new_releases|coming_soon)$"),
    genre: str | None = None,
    platform: str | None = None,
    sort: str = Query("relevance", pattern="^(" + "|".join(SORTS) + ")$"),
    limit: int = Query(48, ge=1, le=120),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned = _owned(db, user)

    # With IGDB we can offer a real catalogue browse (every platform); the Steam
    # sections only exist when we're in Steam-only mode.
    if igdb.configured() and section in ("all", "catalogue"):
        if section == "all":
            raws = igdb.popular(limit=limit + 1, offset=offset, genre=genre, platform=platform)
            where = igdb.popular_where(genre, platform)
        else:
            raws = igdb.browse(genre=genre, platform=platform, sort=sort, limit=limit + 1, offset=offset)
            where = igdb.browse_where(genre, platform, None, None, sort)
        page = _from_igdb(db, raws[:limit])
        _fix_art(db, page)
        db.commit()
        # IGDB can count the whole match set, so the UI can show a real total
        total = igdb.count(where) or (offset + len(page))
        return BrowsePage(items=[_item(g, owned) for g in page], total=total,
                          has_more=len(raws) > limit, genres=_genres_of(page),
                          platforms=_platform_options(), source="igdb")

    raws = [r for r in steamstore.featured(limit=200) if section == "all" or r["section"] == section]
    page_raws, has_more = _page(raws, limit, offset)
    games = {int(r["id"]): _upsert(db, int(r["id"]), r["name"]) for r in page_raws}
    _fix_art(db, list(games.values()))
    db.commit()
    return BrowsePage(
        items=[
            _item(games[int(r["id"])], owned,
                  discount_percent=r.get("discount_percent") or None,
                  price=_price(r.get("final_price"), r.get("currency")))
            for r in page_raws
        ],
        total=len(raws), has_more=has_more, genres=_genres_of(list(games.values())),
        platforms=_platform_options(), source="steam",
    )


def _collaborative(db: Session, user: User, owned: set[int]) -> dict[int, tuple[float, int]]:
    """Predicted interest from users with similar ratings. Empty until a few people have rated things."""
    rows = (
        db.query(LibraryEntry.user_id, LibraryEntry.game_id, LibraryEntry.rating)
        .filter(LibraryEntry.rating.isnot(None))
        .all()
    )
    return collaborative_scores([(r[0], r[1], r[2]) for r in rows], user.id, owned)


@router.get("/for-you", response_model=BrowsePage)
def for_you(
    genre: str | None = None,
    limit: int = Query(48, ge=1, le=120),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entries = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(user_id=user.id).all()
    owned = {e.game_id: e for e in entries}
    games = db.query(Game).all()
    rec = get_recommender(db)
    # note: only genre applies here - "picked for you" ranks our own catalogue,
    # which doesn't record which hardware each game is on
    candidates = _apply_filters([g for g in games if g.id not in owned], genre, None, None, True)
    ranked = rec.recommend(entries, candidates, limit=max(200, offset + limit + 1))

    # blend in collaborative signal: 70% your own taste, 30% what similar users
    # rated highly. CF is only mixed in where there's actually evidence for a
    # game, so a thin dataset degrades to the content model rather than noise.
    cf = _collaborative(db, user, set(owned))
    if cf:
        for s in ranked:
            pred = cf.get(s.game.id)
            if pred is None:
                continue
            score, neighbours = pred
            s.score = round(0.7 * s.score + 0.3 * (100 * score), 1)
            s.reasons = ([f"People with your taste rated this {1 + 9 * score:.1f}/10"]
                         + s.reasons)[:4]
        ranked.sort(key=lambda s: s.score, reverse=True)

    page, has_more = _page(ranked, limit, offset)
    _fix_art(db, [s.game for s in page])
    db.commit()
    return BrowsePage(
        items=[_item(s.game, owned, match=s.score, reasons=s.reasons) for s in page],
        total=len(ranked), has_more=has_more, genres=_genres_of(candidates),
        platforms=_platform_options(), source="igdb" if igdb.configured() else "steam",
    )
