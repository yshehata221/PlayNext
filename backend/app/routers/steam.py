"""
Two ways in:
  POST /steam/import     paste a SteamID64 (kept as a fallback)
  GET  /steam/login      "Sign in with Steam" - OpenID round-trip, then import
"""
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import User
from ..schemas import SteamImportRequest, SteamImportResult
from ..services import steam

router = APIRouter(prefix="/steam", tags=["steam"])

STEAM_OPENID = "https://steamcommunity.com/openid/login"


NO_KEY = ("Steam import isn't set up on this server. It needs a free Steam Web API key "
          "(steamcommunity.com/dev/apikey) in backend/.env as STEAM_API_KEY, then a restart.")


def _run_import(db: Session, user: User, steam_id: str) -> dict:
    if not settings.steam_api_key:
        raise HTTPException(503, NO_KEY)
    try:
        owned = steam.fetch_owned_games(steam_id)
    except RuntimeError:
        raise HTTPException(503, NO_KEY)
    except httpx.HTTPError:
        raise HTTPException(502, "Steam didn't respond - try again in a minute")
    if not owned:
        raise HTTPException(404, "No games found. Is the profile's game list set to public?")
    user.steam_id = steam_id
    return steam.import_library(db, user, owned)


@router.post("/import", response_model=SteamImportResult)
def import_steam(body: SteamImportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _run_import(db, user, body.steam_id)


@router.get("/login")
def steam_login(request: Request, user: User = Depends(get_current_user)):
    """
    Returns the Steam OpenID URL to send the browser to. The user's id travels
    in a short-lived signed `state` inside return_to, since the callback arrives
    as a plain browser GET with no bearer token.
    """
    # no point bouncing someone through Steam if we can't read their library afterwards
    if not settings.steam_api_key:
        raise HTTPException(503, NO_KEY)
    state = jwt.encode({"sub": str(user.id), "purpose": "steam"}, settings.secret_key, algorithm="HS256")
    return_to = f"{settings.public_api_url}/steam/callback?state={state}"
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": settings.public_api_url,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return {"url": f"{STEAM_OPENID}?{urlencode(params)}"}


@router.get("/callback")
def steam_callback(request: Request, state: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=["HS256"])
        assert payload.get("purpose") == "steam"
        user = db.get(User, int(payload["sub"]))
        assert user is not None
    except (JWTError, AssertionError, KeyError, ValueError):
        raise HTTPException(400, "Steam sign-in link expired - try again")

    # Steam bounces back with the openid.* fields; we must re-post them with
    # mode=check_authentication so Steam confirms it really signed this response
    q = dict(request.query_params)
    q["openid.mode"] = "check_authentication"
    q.pop("state", None)
    r = httpx.post(STEAM_OPENID, data=q, timeout=10)
    if "is_valid:true" not in r.text:
        raise HTTPException(401, "Steam didn't verify the sign-in")

    claimed = request.query_params.get("openid.claimed_id", "")
    steam_id = claimed.rsplit("/", 1)[-1]
    if not steam_id.isdigit() or len(steam_id) != 17:
        raise HTTPException(400, "Couldn't read your Steam ID from the response")

    try:
        result = _run_import(db, user, steam_id)
        query = urlencode({"steam": "ok", **result})
    except HTTPException as e:
        query = urlencode({"steam": "error", "message": e.detail})
    return RedirectResponse(f"{settings.frontend_url}/library?{query}")
