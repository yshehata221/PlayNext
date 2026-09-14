from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import Status


# ---- auth ----
USERNAME_RULE = r"^[a-zA-Z0-9_]{3,20}$"


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=80)
    username: str = Field(pattern=USERNAME_RULE, description="3-20 letters, numbers or underscores")
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    display_name: str
    username: str | None
    steam_id: str | None
    email_verified: bool


class VerifyEmail(BaseModel):
    token: str


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- games ----
class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # rows written before a list column existed come back as NULL; treat that as empty
    @field_validator("genres", "themes", "perspectives", "modes", "platforms", "screenshots", "videos", mode="before")
    @classmethod
    def _null_is_empty(cls, v):
        return v or []

    id: int
    title: str
    slug: str
    steam_appid: int | None
    developer: str | None
    release_year: int | None
    genres: list[str]
    themes: list[str]
    perspectives: list[str]
    modes: list[str]
    platforms: list[str] = []
    requirements: dict | None = None
    hours_main: float | None
    hours_complete: float | None
    avg_session_minutes: int | None
    critic_score: float | None
    cover_url: str | None
    hero_url: str | None = None
    screenshots: list[str] = []
    videos: list[dict] = []
    summary: str | None


class GameCreate(BaseModel):
    """Manual add, for games we can't find via IGDB."""
    title: str = Field(min_length=1, max_length=255)
    developer: str | None = None
    release_year: int | None = None
    genres: list[str] = []
    themes: list[str] = []
    perspectives: list[str] = []
    modes: list[str] = []
    hours_main: float | None = None
    hours_complete: float | None = None
    avg_session_minutes: int | None = None
    critic_score: float | None = None
    cover_url: str | None = None
    summary: str | None = None


# ---- library ----
class EntryCreate(BaseModel):
    game_id: int
    status: Status = Status.backlog
    platform: str = "steam"


class EntryUpdate(BaseModel):
    status: Status | None = None
    platform: str | None = None
    rating: int | None = Field(default=None, ge=1, le=10)
    review: str | None = None
    hours_played: float | None = Field(default=None, ge=0)
    last_played: datetime | None = None


class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: Status
    platform: str
    rating: int | None
    review: str | None
    hours_played: float
    last_played: datetime | None
    added_at: datetime
    updated_at: datetime
    game: GameOut


# ---- browse / wishlist ----
class BrowseItem(BaseModel):
    game: GameOut
    in_library: bool
    status: Status | None = None
    entry_id: int | None = None
    match: float | None = None       # taste score, when we can compute one
    reasons: list[str] = []
    discount_percent: int | None = None
    price: str | None = None


class BrowsePage(BaseModel):
    items: list[BrowseItem]
    total: int
    has_more: bool
    genres: list[str] = []       # genre options for the filter bar
    platforms: list[dict] = []   # platform options: [{value, label}], empty without IGDB
    source: str = "steam"    # "igdb" = every platform; "steam" = Steam catalogue only


class WishlistAdd(BaseModel):
    game_id: int
    note: str | None = None


# ---- recommendations ----
class Recommendation(BaseModel):
    game: GameOut
    score: float  # 0-100
    reasons: list[str]
    in_library: bool
    status: Status | None = None
    hours_remaining: float | None = None


class PlanItem(Recommendation):
    minutes: int


# ---- steam ----
class SteamImportRequest(BaseModel):
    steam_id: str = Field(min_length=17, max_length=17, pattern=r"^\d{17}$")


class SteamImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int


# ---- stats ----
class StatusCount(BaseModel):
    status: Status
    count: int


class GenreStat(BaseModel):
    genre: str
    games: int
    hours: float
    hours_share: float
    games_share: float
    avg_rating: float | None


class Personality(BaseModel):
    key: str
    title: str
    tagline: str
    blurb: str
    evidence: str


class Stats(BaseModel):
    total_games: int
    total_hours: float
    played_games: int
    rated_games: int
    added_last_30_days: int
    by_status: list[StatusCount]
    by_platform: dict[str, int]
    by_genre: list[GenreStat]
    backlog_hours: float
    backlog_games: int
    backlog_years_at_current_pace: float | None
    backlog_months_at_current_pace: float | None
    weekly_hours_pace: float
    average_rating: float | None
    completion_rate: float      # completed / games actually started
    completed_games: int
    started_games: int
    avg_hours_per_finished: float | None
    most_played: list[EntryOut]
    personality: Personality


# ---- bulk import (local scanner) ----
class ScannedGame(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    platform: str = "other"
    steam_appid: int | None = None
    install_path: str | None = None
    cover_data: str | None = Field(default=None, max_length=600_000)  # base64, from the launcher's local assets
    cover_mime: str | None = None
    store_id: str | None = Field(default=None, pattern=r"^[0-9A-Za-z]{12}$")  # Microsoft Store product id


class BulkImportRequest(BaseModel):
    games: list[ScannedGame] = Field(max_length=5000)
    lookup_missing: bool = True  # ask the Steam store about titles we can't match locally


class BulkImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    unmatched: list[str]  # titles we created as bare entries with no metadata


# ---- friends ----
class FriendUser(BaseModel):
    """A person, as seen by someone else - no email, no account details."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str | None
    display_name: str


class FriendOut(BaseModel):
    friendship_id: int
    user: FriendUser
    state: str
    direction: str          # "incoming" | "outgoing" | "mutual"
    games: int              # size of their library
    shared_games: int       # games you both own
    compatibility: float | None = None   # 0-100 taste overlap, when both have ratings


class FriendSearchResult(BaseModel):
    user: FriendUser
    relationship: str       # "none" | "pending_in" | "pending_out" | "friends" | "self"


class FriendRequest(BaseModel):
    username: str = Field(pattern=USERNAME_RULE)


class CoopPick(BaseModel):
    game: GameOut
    score: float
    reasons: list[str]
    plays_together: bool | None = None   # None when the game's modes aren't known yet
    your_rating: int | None
    their_rating: int | None
    your_hours: float
    their_hours: float
    minutes: int | None = None
