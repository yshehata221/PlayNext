"""
The wishlist is its own space in the UI but shares the library_entries table
(status = wishlist), so moving a game you bought into your backlog keeps its
notes and rating instead of creating a duplicate row.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Game, LibraryEntry, Status, User
from ..schemas import EntryOut, WishlistAdd
from ..services import steamstore

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[EntryOut])
def list_wishlist(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(LibraryEntry)
        .options(joinedload(LibraryEntry.game))
        .filter_by(user_id=user.id, status=Status.wishlist)
        .order_by(LibraryEntry.added_at.desc())
        .all()
    )


@router.post("", response_model=EntryOut, status_code=201)
def add(body: WishlistAdd, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    game = db.get(Game, body.game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    if not game.genres:
        steamstore.enrich(game, db=db)  # store-search results arrive bare

    entry = db.query(LibraryEntry).filter_by(user_id=user.id, game_id=game.id).first()
    if entry and entry.status != Status.wishlist:
        raise HTTPException(409, f"That's already in your library as {entry.status.value}")
    if entry is None:
        entry = LibraryEntry(user_id=user.id, game_id=game.id, status=Status.wishlist, platform="other")
        db.add(entry)
    if body.note:
        entry.review = body.note
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{entry_id}/own", response_model=EntryOut)
def mark_owned(entry_id: int, platform: str = "steam", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """"I bought it" - moves the game to your backlog, keeping notes and rating."""
    entry = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(id=entry_id, user_id=user.id).first()
    if not entry:
        raise HTTPException(404, "Not on your wishlist")
    entry.status = Status.backlog
    entry.platform = platform
    db.commit()
    db.refresh(entry)
    return entry
