from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Game, User
from ..schemas import GameCreate, GameOut
from ..services import igdb, steamstore
from ..services.steam import steam_cover

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/search", response_model=list[GameOut])
def search(q: str = Query(min_length=2), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """
    Search IGDB if configured, upserting anything new into our games table so
    library entries can point at it. Without IGDB keys, search the local table.
    """
    if igdb.configured():
        results = []
        for raw in igdb.search(q):
            existing = db.query(Game).filter(Game.igdb_id == raw["id"]).first()
            if existing is None:
                existing = igdb.to_game(raw)
                # a seeded game with the same slug beats creating a duplicate
                clash = db.query(Game).filter(Game.slug == existing.slug).first()
                if clash:
                    clash.igdb_id = existing.igdb_id
                    existing = clash
                else:
                    db.add(existing)
                db.flush()
            results.append(existing)
        db.commit()
        return results

    # no IGDB: local catalogue first, then the keyless Steam store search
    like = f"%{q}%"
    local = (
        db.query(Game)
        .filter(or_(Game.title.ilike(like), Game.developer.ilike(like)))
        .order_by(Game.critic_score.desc().nullslast())
        .limit(20)
        .all()
    )
    seen_appids = {g.steam_appid for g in local}
    seen_slugs = {g.slug for g in local}
    for item in steamstore.search(q, limit=8):
        appid = int(item["id"])
        if appid in seen_appids:
            continue
        game = db.query(Game).filter(Game.steam_appid == appid).first()
        if game is None:
            slug = igdb.slugify(item["name"])
            if slug in seen_slugs:
                continue
            game = db.query(Game).filter(Game.slug == slug).first()
            if game is None:
                game = Game(title=item["name"], slug=slug, steam_appid=appid, cover_url=steam_cover(appid))
                db.add(game)
                db.flush()
            elif game.steam_appid is None:
                game.steam_appid, game.cover_url = appid, game.cover_url or steam_cover(appid)
        seen_appids.add(appid)
        local.append(game)
    db.commit()
    return local


@router.get("/{game_id}", response_model=GameOut)
def get_game(game_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    return game


@router.post("", response_model=GameOut, status_code=201)
def create_game(body: GameCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    slug = igdb.slugify(body.title)
    if db.query(Game).filter(Game.slug == slug).first():
        raise HTTPException(409, "That game already exists - search for it instead")
    game = Game(slug=slug, **body.model_dump())
    db.add(game)
    db.commit()
    db.refresh(game)
    return game
