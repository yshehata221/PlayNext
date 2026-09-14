"""
Friends, and deciding what to play together.

The interesting endpoint is /friends/{id}/coop: it averages both people's taste
vectors and ranks only games *both* of them own, preferring things that actually
support playing together. Everything else here is the plumbing that makes that
possible - handles to find each other by, and a request/accept flow so nobody's
library is visible without consent.
"""
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Friendship, FriendState, Game, LibraryEntry, Status, User
from ..schemas import CoopPick, FriendOut, FriendRequest, FriendSearchResult, FriendUser
from ..services.recommender import Recommender, get_recommender

router = APIRouter(prefix="/friends", tags=["friends"])

# Modes that mean two people can actually play. Names differ between sources:
# Steam says "Multiplayer"/"Co-operative", IGDB adds MMO and split screen.
TOGETHER = ("Multiplayer", "Co-operative", "Co-op", "Split screen", "Massively Multiplayer Online (MMO)", "Battle Royale")


def plays_together(game: Game) -> bool | None:
    """True if it supports playing together, False if single-player only, None if we don't know."""
    modes = set(game.modes or [])
    if not modes:
        return None
    return bool(modes & set(TOGETHER))


def _link(db: Session, a: int, b: int) -> Friendship | None:
    return (
        db.query(Friendship)
        .filter(or_(
            (Friendship.requester_id == a) & (Friendship.addressee_id == b),
            (Friendship.requester_id == b) & (Friendship.addressee_id == a),
        ))
        .first()
    )


def _friend_or_404(db: Session, me: User, user_id: int) -> User:
    link = _link(db, me.id, user_id)
    if link is None or link.state != FriendState.accepted:
        raise HTTPException(403, "You're not friends with that person yet")
    other = db.get(User, user_id)
    if other is None:
        raise HTTPException(404, "User not found")
    return other


def _entries(db: Session, user_id: int) -> list[LibraryEntry]:
    return (
        db.query(LibraryEntry)
        .options(joinedload(LibraryEntry.game))
        .filter(LibraryEntry.user_id == user_id, LibraryEntry.status != Status.wishlist)
        .all()
    )


def _compatibility(rec: Recommender, mine: list[LibraryEntry], theirs: list[LibraryEntry]) -> float | None:
    """
    Cosine similarity between two taste vectors, mapped to 0-100. None when
    either side hasn't rated anything, because a number from no data is worse
    than no number.
    """
    a, b = rec.taste_vector(mine), rec.taste_vector(theirs)
    if a is None or b is None:
        return None
    return round(100 * (float(a @ b) + 1) / 2, 1)


@router.get("", response_model=list[FriendOut])
def list_friends(db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    """Accepted friends and outstanding requests, in one list the UI can group."""
    links = (
        db.query(Friendship)
        .filter(or_(Friendship.requester_id == me.id, Friendship.addressee_id == me.id))
        .all()
    )
    if not links:
        return []

    mine = _entries(db, me.id)
    my_game_ids = {e.game_id for e in mine}
    rec = get_recommender(db)

    out: list[FriendOut] = []
    for link in links:
        other_id = link.addressee_id if link.requester_id == me.id else link.requester_id
        other = db.get(User, other_id)
        if other is None:
            continue
        theirs = _entries(db, other_id)
        accepted = link.state == FriendState.accepted
        out.append(FriendOut(
            friendship_id=link.id,
            user=FriendUser.model_validate(other),
            state=link.state.value,
            direction="mutual" if accepted else ("outgoing" if link.requester_id == me.id else "incoming"),
            games=len(theirs),
            shared_games=len({e.game_id for e in theirs} & my_game_ids),
            compatibility=_compatibility(rec, mine, theirs) if accepted else None,
        ))
    # friends first, then newest requests
    out.sort(key=lambda f: (f.state != "accepted", -(f.compatibility or 0)))
    return out


@router.get("/search", response_model=list[FriendSearchResult])
def search_users(q: str = Query(min_length=2, max_length=32), db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    users = (
        db.query(User)
        .filter(User.username.isnot(None), User.username.ilike(f"{q.lower()}%"))
        .order_by(User.username)
        .limit(10)
        .all()
    )
    results = []
    for u in users:
        if u.id == me.id:
            results.append(FriendSearchResult(user=FriendUser.model_validate(u), relationship="self"))
            continue
        link = _link(db, me.id, u.id)
        rel = "none"
        if link and link.state == FriendState.accepted:
            rel = "friends"
        elif link:
            rel = "pending_out" if link.requester_id == me.id else "pending_in"
        results.append(FriendSearchResult(user=FriendUser.model_validate(u), relationship=rel))
    return results


@router.post("/request", response_model=FriendOut, status_code=201)
def send_request(body: FriendRequest, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    other = db.query(User).filter(User.username == body.username.lower()).first()
    if other is None:
        raise HTTPException(404, "No one with that username")
    if other.id == me.id:
        raise HTTPException(400, "You can't add yourself")

    existing = _link(db, me.id, other.id)
    if existing:
        if existing.state == FriendState.accepted:
            raise HTTPException(409, "You're already friends")
        if existing.requester_id == other.id:
            # they'd already asked us - treat this as accepting
            existing.state = FriendState.accepted
            db.commit()
        else:
            raise HTTPException(409, "Request already sent")
        link = existing
    else:
        link = Friendship(requester_id=me.id, addressee_id=other.id)
        db.add(link)
        db.commit()
        db.refresh(link)

    theirs = _entries(db, other.id)
    mine = _entries(db, me.id)
    return FriendOut(
        friendship_id=link.id, user=FriendUser.model_validate(other), state=link.state.value,
        direction="mutual" if link.state == FriendState.accepted else "outgoing",
        games=len(theirs), shared_games=len({e.game_id for e in theirs} & {e.game_id for e in mine}),
    )


@router.post("/{friendship_id}/accept", response_model=FriendOut)
def accept(friendship_id: int, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    link = db.get(Friendship, friendship_id)
    if link is None or link.addressee_id != me.id:
        raise HTTPException(404, "No such request")
    link.state = FriendState.accepted
    db.commit()

    other = db.get(User, link.requester_id)
    mine, theirs = _entries(db, me.id), _entries(db, link.requester_id)
    rec = get_recommender(db)
    return FriendOut(
        friendship_id=link.id, user=FriendUser.model_validate(other), state="accepted", direction="mutual",
        games=len(theirs), shared_games=len({e.game_id for e in theirs} & {e.game_id for e in mine}),
        compatibility=_compatibility(rec, mine, theirs),
    )


@router.delete("/{friendship_id}", status_code=204)
def remove(friendship_id: int, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    """Declines a request or removes a friend - same row either way."""
    link = db.get(Friendship, friendship_id)
    if link is None or me.id not in (link.requester_id, link.addressee_id):
        raise HTTPException(404, "Not found")
    db.delete(link)
    db.commit()


@router.get("/by-username/{username}", response_model=FriendOut)
def by_username(username: str, db: Session = Depends(get_db), me: User = Depends(get_current_user)):
    """Look up a friend by handle, so a shared link doesn't need a numeric id."""
    other = db.query(User).filter(User.username == username.lower()).first()
    if other is None:
        raise HTTPException(404, "No one with that username")
    link = _link(db, me.id, other.id)
    if link is None:
        raise HTTPException(404, "Not connected to that person")
    mine, theirs = _entries(db, me.id), _entries(db, other.id)
    rec = get_recommender(db)
    return FriendOut(
        friendship_id=link.id, user=FriendUser.model_validate(other), state=link.state.value,
        direction="mutual" if link.state == FriendState.accepted else ("outgoing" if link.requester_id == me.id else "incoming"),
        games=len(theirs), shared_games=len({e.game_id for e in theirs} & {e.game_id for e in mine}),
        compatibility=_compatibility(rec, mine, theirs) if link.state == FriendState.accepted else None,
    )


@router.get("/{user_id}/coop", response_model=list[CoopPick])
def coop(
    user_id: int,
    hours: float | None = Query(None, gt=0, le=12),
    together_only: bool = Query(True, description="Only games that support multiplayer or co-op"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    """
    What the two of you should play. Only games you both own are candidates, and
    by default only ones that actually support playing together - a shared
    single-player game is a poor answer to "what shall we play tonight?".
    Ranking blends both taste vectors equally.

    Games whose modes we haven't fetched yet count as unknown and are excluded
    from the strict list rather than guessed at.
    """
    other = _friend_or_404(db, me, user_id)

    mine = _entries(db, me.id)
    theirs = _entries(db, other.id)
    my_by_game = {e.game_id: e for e in mine}
    their_by_game = {e.game_id: e for e in theirs}
    shared_ids = set(my_by_game) & set(their_by_game)
    if not shared_ids:
        return []

    rec = get_recommender(db)
    a, b = rec.taste_vector(mine), rec.taste_vector(theirs)
    # average the two tastes; if only one side has ratings, use that one
    if a is not None and b is not None:
        taste = (a + b) / 2
        taste = taste / (np.linalg.norm(taste) or 1)
    else:
        taste = a if a is not None else b

    picks: list[CoopPick] = []
    for game_id in shared_ids:
        game = my_by_game[game_id].game
        if game.id not in rec.index:
            continue
        together = plays_together(game)
        if together_only and together is not True:
            continue

        vec = rec.matrix[rec.index[game.id]]
        sim = float(taste @ vec) if taste is not None else 0.0

        mine_e, theirs_e = my_by_game[game_id], their_by_game[game_id]
        score = 100 * (0.55 * (sim + 1) / 2 + 0.2 * ((game.critic_score or 70) / 100) + (0.25 if together else 0))

        reasons = ["You both own it"]
        if together is True:
            modes = [m for m in (game.modes or []) if m in TOGETHER]
            reasons.append(f"Plays together: {', '.join(modes).lower()}")
        elif together is False:
            reasons.append("Single-player — one plays, one watches")
        else:
            reasons.append("Multiplayer support unknown")
        if mine_e.rating and theirs_e.rating:
            reasons.append(f"You rated it {mine_e.rating}/10, they rated it {theirs_e.rating}/10")
        elif mine_e.rating or theirs_e.rating:
            who = "You" if mine_e.rating else "They"
            reasons.append(f"{who} rated it {(mine_e.rating or theirs_e.rating)}/10")
        if mine_e.hours_played < 1 and theirs_e.hours_played < 1:
            reasons.append("Neither of you has started it")
        if game.avg_session_minutes:
            reasons.append(f"Sessions run about {game.avg_session_minutes} minutes")

        minutes = game.avg_session_minutes
        if hours is not None:
            if not (minutes and minutes <= hours * 60):
                continue

        picks.append(CoopPick(
            game=game, score=round(score, 1), reasons=reasons[:4], plays_together=together,
            your_rating=mine_e.rating, their_rating=theirs_e.rating,
            your_hours=mine_e.hours_played, their_hours=theirs_e.hours_played,
            minutes=minutes,
        ))

    picks.sort(key=lambda p: p.score, reverse=True)
    return picks[:limit]
