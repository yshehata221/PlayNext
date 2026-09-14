"""
Issuing and redeeming the one-shot tokens behind email verification and
password resets.

The raw token only ever exists in the email; the database holds a SHA-256 hash
of it. Redeeming is a single transaction that checks expiry and prior use, so a
link can't be replayed.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import EmailToken, TokenPurpose, User


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue(db: Session, user: User, purpose: TokenPurpose, hours: int) -> str:
    """Create a token, returning the raw value to email. Older ones are dropped."""
    db.query(EmailToken).filter(
        EmailToken.user_id == user.id, EmailToken.purpose == purpose, EmailToken.used_at.is_(None)
    ).delete()

    raw = secrets.token_urlsafe(32)
    db.add(EmailToken(
        user_id=user.id, purpose=purpose, token_hash=_hash(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
    ))
    db.commit()
    return raw


def redeem(db: Session, raw: str, purpose: TokenPurpose) -> User | None:
    """Consume a token and return its user, or None if it's invalid/expired/used."""
    row = db.query(EmailToken).filter(
        EmailToken.token_hash == _hash(raw), EmailToken.purpose == purpose
    ).first()
    if row is None or row.used_at is not None:
        return None

    # stored timestamps come back naive from SQLite and aware from Postgres
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None

    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return db.get(User, row.user_id)
