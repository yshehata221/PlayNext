from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import Game, LibraryEntry, Status, User
from ..schemas import PlanItem, Recommendation
from ..services.recommender import MOODS, get_recommender, plan_night

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[Recommendation])
def recommend(
    source: str = Query("backlog", pattern="^(backlog|discover|all)$"),
    hours: float | None = Query(None, gt=0, le=24, description="How long you've got tonight"),
    mood: str | None = Query(None, pattern="^(" + "|".join(MOODS) + ")$"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    backlog  - what to play next out of what you already own
    discover - games you don't own yet
    all      - both, ranked together
    """
    entries = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(user_id=user.id).all()
    owned = {e.game_id: e for e in entries}

    # building the matrix over every game each request is fine for a few thousand
    # rows; cache it (or precompute per-game vectors) if the catalogue grows
    games = db.query(Game).all()
    rec = get_recommender(db)

    candidates: list[Game] = []
    if source in ("backlog", "all"):
        candidates += [e.game for e in entries if e.status in (Status.backlog, Status.playing)]
    if source in ("discover", "all"):
        candidates += [g for g in games if g.id not in owned]

    out = []
    for s in rec.recommend(entries, candidates, hours_available=hours, limit=limit, mood=mood):
        entry = owned.get(s.game.id)
        out.append(
            Recommendation(
                game=s.game,
                score=s.score,
                reasons=s.reasons,
                in_library=entry is not None,
                status=entry.status if entry else None,
                hours_remaining=s.hours_remaining,
            )
        )
    return out


@router.get("/plan", response_model=list[PlanItem])
def plan(
    hours: float = Query(..., gt=0, le=12),
    mood: str | None = Query(None, pattern="^(" + "|".join(MOODS) + ")$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Build a multi-game session that fits the time you have, from your backlog and in-progress games."""
    entries = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(user_id=user.id).all()
    owned = {e.game_id: e for e in entries}
    games = db.query(Game).all()
    rec = get_recommender(db)
    candidates = [e.game for e in entries if e.status in (Status.backlog, Status.playing)]
    ranked = rec.recommend(entries, candidates, hours_available=None, limit=30, mood=mood)
    out = []
    for s, minutes in plan_night(ranked, hours):
        entry = owned.get(s.game.id)
        out.append(PlanItem(
            game=s.game, score=s.score, reasons=s.reasons, in_library=True,
            status=entry.status if entry else None, hours_remaining=s.hours_remaining, minutes=minutes,
        ))
    return out
