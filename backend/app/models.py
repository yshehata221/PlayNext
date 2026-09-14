"""
Three tables is all the MVP needs:
  users          - who's logged in
  games          - one row per game, shared by everyone (metadata from IGDB/Steam/seed)
  library_entries - the join between a user and a game: status, rating, hours, etc.

Genres/themes are stored as JSON lists rather than proper many-to-many tables.
That's a deliberate shortcut: the recommender only ever needs them as a bag of
tags, and it keeps the schema readable. Easy to normalise later if needed.
"""
from datetime import datetime, timezone
import enum

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Status(str, enum.Enum):
    backlog = "backlog"
    playing = "playing"
    completed = "completed"
    abandoned = "abandoned"
    wishlist = "wishlist"


def now():
    return datetime.now(timezone.utc)


class FriendState(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # lowercase handle people share to add each other; unique across the app
    username: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    entries: Mapped[list["LibraryEntry"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    igdb_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    steam_appid: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    developer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    themes: Mapped[list[str]] = mapped_column(JSON, default=list)
    perspectives: Mapped[list[str]] = mapped_column(JSON, default=list)  # first person, third person, isometric...
    modes: Mapped[list[str]] = mapped_column(JSON, default=list)         # single player, co-op, multiplayer

    # HowLongToBeat-style figures, in hours. Nullable because we won't always have them.
    hours_main: Mapped[float | None] = mapped_column(Float, nullable=True)
    hours_complete: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_session_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # every platform the game is released on, e.g. ["PC (Microsoft Windows)", "Nintendo Switch"]
    platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    # PC system requirements, scraped from the Steam store: {"minimum": "...", "recommended": "..."}
    requirements: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    critic_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # wide "hero" art for the game page backdrop, and a few screenshots
    hero_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    screenshots: Mapped[list[str]] = mapped_column(JSON, default=list)
    # trailers: [{"kind": "mp4"|"youtube", "src": url or youtube id, "title": str, "thumb": url|None}]
    videos: Mapped[list[dict]] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    entries: Mapped[list["LibraryEntry"]] = relationship(back_populates="game")


class LibraryEntry(Base):
    __tablename__ = "library_entries"
    __table_args__ = (UniqueConstraint("user_id", "game_id", name="uq_user_game"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)

    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.backlog)
    platform: Mapped[str] = mapped_column(String(32), default="steam")  # steam, playstation, xbox, switch, epic, gog, other
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-10
    review: Mapped[str | None] = mapped_column(Text, nullable=True)
    hours_played: Mapped[float] = mapped_column(Float, default=0.0)
    last_played: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    user: Mapped["User"] = relationship(back_populates="entries")
    game: Mapped["Game"] = relationship(back_populates="entries")


class Friendship(Base):
    """
    One row per relationship, not two. `requester` sent it, `addressee` accepts
    or declines; once accepted the pair is symmetric, so every query has to check
    both columns. A pair constraint in each direction stops duplicates.
    """
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    state: Mapped[FriendState] = mapped_column(Enum(FriendState), default=FriendState.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    requester: Mapped["User"] = relationship(foreign_keys=[requester_id])
    addressee: Mapped["User"] = relationship(foreign_keys=[addressee_id])


class TokenPurpose(str, enum.Enum):
    verify_email = "verify_email"
    reset_password = "reset_password"


class EmailToken(Base):
    """
    One-shot tokens for email verification and password resets.

    Only a hash of the token is stored, the same reasoning as passwords: a
    database leak then yields nothing usable. They expire, and `used_at` makes
    them single-use so a reset link in an inbox can't be replayed.
    """
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[TokenPurpose] = mapped_column(Enum(TokenPurpose))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    user: Mapped["User"] = relationship()
