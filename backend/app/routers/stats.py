from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import LibraryEntry, Status, User
from ..schemas import Stats
from ..services.stats import build_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=Stats)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    entries = db.query(LibraryEntry).options(joinedload(LibraryEntry.game)).filter_by(user_id=user.id).all()
    # wishlisted games aren't owned, so they don't count toward the library stats
    return build_stats([e for e in entries if e.status != Status.wishlist])
