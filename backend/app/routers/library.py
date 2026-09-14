from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import SessionLocal, get_db
from ..models import Game, LibraryEntry, Status, User
from ..schemas import EntryCreate, EntryOut, EntryUpdate

router = APIRouter(prefix="/library", tags=["library"])


def _owned(db: Session, user: User, entry_id: int) -> LibraryEntry:
    entry = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(id=entry_id, user_id=user.id).first()
    if not entry:
        raise HTTPException(404, "That game isn't in your library")
    return entry


@router.get("", response_model=list[EntryOut])
def list_library(
    status: Status | None = None,
    platform: str | None = None,
    sort: str = Query("added", pattern="^(added|title|rating|hours|last_played)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter(LibraryEntry.user_id == user.id)
    if status:
        q = q.filter(LibraryEntry.status == status)
    else:
        # wishlisted games are owned-by-nobody, so they live in /wishlist instead
        q = q.filter(LibraryEntry.status != Status.wishlist)
    if platform:
        q = q.filter(LibraryEntry.platform == platform)

    order = {
        "added": LibraryEntry.added_at.desc(),
        "rating": LibraryEntry.rating.desc().nullslast(),
        "hours": LibraryEntry.hours_played.desc(),
        "last_played": LibraryEntry.last_played.desc().nullslast(),
    }
    if sort == "title":
        q = q.join(Game).order_by(Game.title)
    else:
        q = q.order_by(order[sort])
    return q.all()


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _owned(db, user, entry_id)


@router.post("", response_model=EntryOut, status_code=201)
def add_entry(body: EntryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Game, body.game_id):
        raise HTTPException(404, "Game not found")
    if db.query(LibraryEntry).filter_by(user_id=user.id, game_id=body.game_id).first():
        raise HTTPException(409, "Already in your library")
    game = db.get(Game, body.game_id)
    if not game.genres:
        steamstore.enrich(game, db=db)  # store-search results arrive bare; fill them in on add
    entry = LibraryEntry(user_id=user.id, **body.model_dump())
    db.add(entry)
    db.commit()
    return _owned(db, user, entry.id)


@router.patch("/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: int, body: EntryUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entry = _owned(db, user, entry_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def remove_entry(entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_owned(db, user, entry_id))
    db.commit()


# ------------------------------------------------------------- bulk import
from ..schemas import BulkImportRequest, BulkImportResult  # noqa: E402
from ..services.igdb import slugify  # noqa: E402
from ..services.matching import normalise, similarity  # noqa: E402
from ..services.steam import steam_cover  # noqa: E402
from ..services import msstore, steamstore  # noqa: E402
from ..services.media import save_cover  # noqa: E402
import logging  # noqa: E402

log = logging.getLogger("uvicorn.error")

KNOWN_PLATFORMS = {"steam", "epic", "gog", "ubisoft", "ea", "battlenet", "xbox", "playstation", "switch", "other"}


@router.post("/import", response_model=BulkImportResult)
def bulk_import(body: BulkImportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Used by the local scanner. For each title: match on steam_appid, then exact
    normalised title, then fuzzy title (>= 0.9). Anything unmatched becomes a
    bare Game row so the entry still exists; metadata can be filled in later
    via IGDB. Idempotent - re-scanning never duplicates.
    """
    log.info(
        "import: %d games, %d with steam appid, %d with store id, %d with local art",
        len(body.games),
        sum(1 for g in body.games if g.steam_appid),
        sum(1 for g in body.games if g.store_id),
        sum(1 for g in body.games if g.cover_data),
    )
    catalogue = db.query(Game).all()
    by_appid = {g.steam_appid: g for g in catalogue if g.steam_appid}
    by_norm = {normalise(g.title): g for g in catalogue}
    owned = {e.game_id: e for e in db.query(LibraryEntry).filter_by(user_id=user.id).all()}

    imported = updated = skipped = 0
    unmatched: list[str] = []

    for item in body.games:
        platform = item.platform if item.platform in KNOWN_PLATFORMS else "other"
        game = by_appid.get(item.steam_appid) if item.steam_appid else None

        if game is None:
            game = by_norm.get(normalise(item.title))
        if game is None:
            best = max(catalogue, key=lambda g: similarity(g.title, item.title), default=None)
            if best is not None and similarity(best.title, item.title) >= 0.9:
                game = best

        if game is None:
            slug = slugify(item.title)
            if not slug:
                skipped += 1
                continue
            game = Game(
                title=item.title, slug=slug, steam_appid=item.steam_appid,
                cover_url=steam_cover(item.steam_appid) if item.steam_appid else None,
            )
            db.add(game)
            db.flush()
            catalogue.append(game)
            by_norm[normalise(game.title)] = game
            unmatched.append(item.title)
        elif item.steam_appid and game.steam_appid is None:
            game.steam_appid = item.steam_appid
            by_appid[item.steam_appid] = game

        # backfill art on anything that has an appid but no cover yet
        if game.cover_url is None and game.steam_appid:
            game.cover_url = steam_cover(game.steam_appid)
        # Xbox / Game Pass: the Store catalogue has the proper poster, so it wins over
        # anything we guessed from Steam or pulled off disk - unless we already have it
        if body.lookup_missing and item.store_id and "store-images.s-microsoft.com" not in (game.cover_url or ""):
            product = msstore.lookup(item.store_id)
            if product:
                poster = msstore.poster_url(product)
                if poster:
                    game.cover_url = poster
                    log.info("import: %s cover from Microsoft Store", item.title)
                if not game.summary and product.get("LocalizedProperties", [{}])[0].get("ShortDescription"):
                    game.summary = product["LocalizedProperties"][0]["ShortDescription"]
        # ask the Steam store for genres etc. if it knows the game (fills gaps only)
        if body.lookup_missing and (game.steam_appid is None or steamstore.needs_enrich(game)):
            steamstore.enrich(game, db=db)
        # still nothing (or only an old scanner-uploaded image)? use the square tile
        # the scanner pulled from the package itself
        if item.cover_data and (game.cover_url is None or "/media/covers/" in game.cover_url):
            game.cover_url = save_cover(game.slug, item.cover_data, item.cover_mime) or game.cover_url

        entry = owned.get(game.id)
        if entry is None:
            entry = LibraryEntry(user_id=user.id, game_id=game.id, platform=platform, status=Status.backlog)
            db.add(entry)
            owned[game.id] = entry
            imported += 1
        else:
            updated += 1  # already there; installed-elsewhere info is noted but we don't overwrite the platform
        steamstore.mark_tried(game.id)
        db.commit()  # per game: network lookups above must not hold the write lock for the whole scan

    return BulkImportResult(imported=imported, updated=updated, skipped=skipped, unmatched=unmatched)


@router.post("/enrich")
def enrich_library(background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Fill in art and metadata for library games that are missing it. The work
    runs in the background: this returns at once with how many games are queued,
    and the page re-fetches a few seconds later.
    """
    entries = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(user_id=user.id).all()
    todo = [e.game_id for e in entries if steamstore.needs_enrich(e.game) and not steamstore.recently_tried(e.game.id)][:20]
    for gid in todo:
        steamstore.mark_tried(gid)
    if todo:
        background.add_task(_enrich_games, todo)
    return {"queued": len(todo)}


def _fill_platforms(game: Game) -> None:
    """Steam only reports PC, so ask IGDB for the rest of a game's platforms."""
    from ..services import igdb
    from ..services.matching import normalise

    if not igdb.configured() or len(game.platforms or []) > 1:
        return
    for raw in igdb.search(game.title, limit=3):
        if normalise(raw.get("name", "")) == normalise(game.title):
            names = [p["name"] for p in raw.get("platforms", []) if p.get("name")]
            if names:
                game.platforms = list(dict.fromkeys((game.platforms or []) + names))
            if not game.igdb_id:
                game.igdb_id = raw["id"]
            return


def _enrich_games(game_ids: list[int]) -> None:
    """Background worker: own session, commit per game, never raises."""
    db = SessionLocal()
    try:
        updated = 0
        for gid in game_ids:
            game = db.get(Game, gid)
            if game is None:
                continue
            title = game.title  # see browse.game_detail: don't read attributes after a rollback
            before = (game.cover_url, list(game.genres or []))
            try:
                steamstore.enrich(game, db=db)
                _fill_platforms(game)
                changed = (game.cover_url, list(game.genres or [])) != before
                db.commit()
            except Exception as e:  # one bad lookup mustn't kill the batch
                db.rollback()
                log.warning("enrich: %s failed: %s", title, e)
                continue
            if changed:
                updated += 1
                log.info("enrich: %s updated", title)
        log.info("enrich: checked %d, updated %d", len(game_ids), updated)
    finally:
        db.close()
