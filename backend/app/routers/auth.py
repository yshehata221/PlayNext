from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user, hash_password, verify_password
from ..config import settings
from ..limiter import limiter
from ..database import get_db
from ..models import User
from ..models import EmailToken, TokenPurpose  # noqa: F401
from ..schemas import ForgotPassword, PasswordChange, ResetPassword, Token, UserCreate, UserOut, VerifyEmail
from ..services import mailer, tokens

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=201)
@limiter.limit(settings.login_rate_limit)
def register(request: Request, body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "An account with that email already exists")
    # usernames are compared case-insensitively, so they're stored lowercase
    username = body.username.lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(409, "That username is taken")
    user = User(email=body.email, display_name=body.display_name, username=username,
                password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    _send_verification(db, user)
    return Token(access_token=create_token(user.id))


@router.post("/login", response_model=Token)
@limiter.limit(settings.login_rate_limit)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2 form uses "username" - we treat it as the email
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    if settings.require_email_verification and not user.email_verified:
        raise HTTPException(403, "Confirm your email address first - check your inbox for the link.")
    return Token(access_token=create_token(user.id))


def _send_verification(db: Session, user: User) -> None:
    raw = tokens.issue(db, user, TokenPurpose.verify_email, settings.verify_token_hours)
    mailer.send_verification(user.email, user.display_name, f"{settings.frontend_url}/verify?token={raw}")


@router.post("/verify/resend", status_code=202)
@limiter.limit(settings.email_rate_limit)
def resend_verification(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Send another confirmation link. Quietly does nothing if already verified."""
    if not user.email_verified:
        _send_verification(db, user)
    return {"sent": True}


@router.post("/verify", response_model=UserOut)
def verify_email(body: VerifyEmail, db: Session = Depends(get_db)):
    user = tokens.redeem(db, body.token, TokenPurpose.verify_email)
    if user is None:
        raise HTTPException(400, "That link has expired or has already been used. Request a new one.")
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/forgot-password", status_code=202)
@limiter.limit(settings.email_rate_limit)
def forgot_password(request: Request, body: ForgotPassword, db: Session = Depends(get_db)):
    """
    Always reports success, whether or not the address exists. Saying "no such
    account" would turn this into a way to discover who has registered.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if user is not None:
        raw = tokens.issue(db, user, TokenPurpose.reset_password, settings.reset_token_hours)
        mailer.send_password_reset(user.email, user.display_name, f"{settings.frontend_url}/reset?token={raw}")
    return {"sent": True}


@router.post("/reset-password", response_model=Token)
def reset_password(body: ResetPassword, db: Session = Depends(get_db)):
    """
    Consumes the token and signs the user in, so they don't have to type the
    password they just set. Confirming the reset also verifies the address -
    they've demonstrably received mail there.
    """
    user = tokens.redeem(db, body.token, TokenPurpose.reset_password)
    if user is None:
        raise HTTPException(400, "That reset link has expired or has already been used. Request a new one.")
    user.password_hash = hash_password(body.new_password)
    user.email_verified = True
    db.commit()
    return Token(access_token=create_token(user.id))


@router.post("/demo", response_model=Token)
@limiter.limit("30/minute")
def demo_login(request: Request, db: Session = Depends(get_db)):
    """
    One-click sign-in to the demo account, so someone evaluating the project
    can see a populated library immediately instead of registering and then
    facing an empty app. Seeds the account on first use, which also means a
    fresh deployment needs no manual setup step.
    """
    if not settings.enable_demo_login:
        raise HTTPException(404, "Demo sign-in is disabled")

    user = db.query(User).filter(User.email == settings.demo_email).first()
    if user is None:
        from ..demo import seed

        seed(db, quiet=True)   # uses this request's session, so tests and requests agree
        user = db.query(User).filter(User.email == settings.demo_email).first()
        if user is None:
            raise HTTPException(503, "Demo account could not be created")
    return Token(access_token=create_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/username-available/{username}")
def username_available(username: str, db: Session = Depends(get_db)):
    """Used by the sign-up form so people aren't told after submitting."""
    import re

    if not re.fullmatch(r"[a-zA-Z0-9_]{3,20}", username):
        return {"available": False, "reason": "3-20 letters, numbers or underscores"}
    taken = db.query(User).filter(User.username == username.lower()).first() is not None
    return {"available": not taken, "reason": "That username is taken" if taken else None}


@router.post("/change-password", status_code=204)
def change_password(body: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Changing a password requires the current one, so a stolen token can't lock
    the owner out. There's no email-based reset: sending mail needs a provider
    and deliverability setup, and a half-built reset flow is worse than none.
    """
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(403, "Current password is wrong")
    user.password_hash = hash_password(body.new_password)
    db.commit()
