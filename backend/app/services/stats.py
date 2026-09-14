"""
Library analytics for the profile page.

Two principles here, both learned the hard way from the first version:
  1. every figure says what it was calculated from ("10/10 from 1 rated game"
     is honest; a bare "10/10" from 28 games is misleading)
  2. no number is derived from data we don't have - if nothing is rated, the
     rating stats are None rather than 0, and the UI says so
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from ..models import LibraryEntry, Status


def _now():
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """
    SQLite hands back naive datetimes even for timezone-aware columns, while
    Postgres returns aware ones - so every stored timestamp is normalised before
    it's compared against `now`.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _personality(*, genre_share: list[tuple[str, float]], completion: float, backlog_hours: float,
                 avg_rating: float | None, rated: int, total: int, unplayed_share: float,
                 avg_year: float | None, avg_hours_per_finished: float | None) -> dict:
    """
    Pick a single label for how someone plays, from strongest signal to weakest.
    Deliberately explainable: each branch names the evidence it fired on, so the
    UI can show *why* rather than asserting a personality type out of nowhere.
    """
    top_genre, top_pct = genre_share[0] if genre_share else ("", 0.0)

    if total < 5:
        return {"key": "newcomer", "title": "The New Arrival", "tagline": "Just getting started.",
                "blurb": f"Only {total} game{'s' if total != 1 else ''} tracked so far. Add a few more and your profile will sharpen up.",
                "evidence": f"{total} games tracked"}

    if completion >= 0.6:
        return {"key": "completionist", "title": "The Completionist", "tagline": "Finishes what it starts.",
                "blurb": "You see games through to the end far more often than most people do.",
                "evidence": f"{completion * 100:.0f}% of your started games are finished"}

    if avg_hours_per_finished and avg_hours_per_finished >= 40:
        return {"key": "long-haul", "title": "The Long-Haul Gamer", "tagline": "In it for the long game.",
                "blurb": "You commit to big games and sink serious hours into them rather than skipping around.",
                "evidence": f"about {avg_hours_per_finished:.0f}h in each game you finish"}

    if top_pct >= 45:
        label = {"Shooter": "Shooter Specialist", "Role-playing (RPG)": "RPG Devotee", "RPG": "RPG Devotee",
                 "Adventure": "Adventurer", "Strategy": "Tactician", "Racing": "Speed Freak",
                 "Sport": "Sports Fan", "Simulator": "Simulation Buff", "Indie": "Indie Digger",
                 "Platform": "Platformer Purist", "Puzzle": "Puzzle Solver"}.get(top_genre, f"{top_genre} Specialist")
        return {"key": "specialist", "title": f"The {label}", "tagline": "You know exactly what you like.",
                "blurb": f"{top_pct:.0f}% of your hours go into {top_genre.lower()} games. You're not here to browse.",
                "evidence": f"{top_pct:.0f}% of playtime is {top_genre.lower()}"}

    if unplayed_share >= 0.6 or backlog_hours >= 200:
        return {"key": "hoarder", "title": "The Backlog Builder", "tagline": "Collects faster than it plays.",
                "blurb": "Your library grows quicker than your playtime. There's a lot of good stuff waiting.",
                "evidence": f"{backlog_hours:.0f}h of unplayed games"}

    if avg_rating is not None and rated >= 5 and avg_rating >= 8.5:
        return {"key": "enthusiast", "title": "The Enthusiast", "tagline": "Easily delighted, and honest about it.",
                "blurb": "You rate the games you play highly, which usually means you pick well.",
                "evidence": f"{avg_rating:.1f}/10 average across {rated} rated games"}

    if avg_year and avg_year >= _now().year - 2:
        return {"key": "new-release", "title": "The New Release Hunter", "tagline": "Always on the current thing.",
                "blurb": "Your library skews recent - you play things while people are still talking about them.",
                "evidence": f"average release year {avg_year:.0f}"}

    if genre_share and top_pct < 25:
        return {"key": "variety", "title": "The Variety Gamer", "tagline": "A bit of everything.",
                "blurb": "No single genre dominates your library. You follow interesting games, not categories.",
                "evidence": f"top genre is only {top_pct:.0f}% of your playtime"}

    return {"key": "explorer", "title": "The Explorer", "tagline": "Tries things, moves on.",
            "blurb": "You sample widely and keep a healthy pile of things to get to.",
            "evidence": f"{total} games across {len(genre_share)} genres"}


def build_stats(entries: list[LibraryEntry]) -> dict:
    total_hours = sum(e.hours_played for e in entries)
    played = [e for e in entries if e.hours_played > 0]
    rated = [e for e in entries if e.rating is not None]

    by_status = defaultdict(int)
    by_platform = defaultdict(int)
    for e in entries:
        by_status[e.status] += 1
        by_platform[e.platform] += 1

    # genre table: games, hours, how you rate them, and share of total playtime
    genre_games = defaultdict(int)
    genre_hours = defaultdict(float)
    genre_ratings = defaultdict(list)
    for e in entries:
        for g in e.game.genres or []:
            genre_games[g] += 1
            genre_hours[g] += e.hours_played
            if e.rating is not None:
                genre_ratings[g].append(e.rating)

    hours_total = sum(genre_hours.values()) or 1
    games_total = len(entries) or 1
    by_genre = sorted(
        (
            {
                "genre": g,
                "games": genre_games[g],
                "hours": round(genre_hours[g], 1),
                "hours_share": round(100 * genre_hours[g] / hours_total, 1),
                "games_share": round(100 * genre_games[g] / games_total, 1),
                "avg_rating": round(sum(genre_ratings[g]) / len(genre_ratings[g]), 1) if genre_ratings[g] else None,
            }
            for g in genre_games
        ),
        # rank by hours, but fall back to game count so a fresh library isn't all zeros
        key=lambda r: (r["hours"], r["games"]),
        reverse=True,
    )

    # the "your backlog would take N years" figure
    backlog_hours = 0.0
    unplayed = 0
    for e in entries:
        if e.status in (Status.backlog, Status.playing):
            if e.game.hours_main:
                backlog_hours += max(e.game.hours_main - e.hours_played, 0)
            if e.hours_played < 1:
                unplayed += 1

    # pace: hours on anything touched in the last 90 days, per week, capped because
    # Steam gives lifetime hours and a recently-played old game would overstate it
    cutoff = _now() - timedelta(days=90)
    recent = [e for e in entries if (lp := _aware(e.last_played)) and lp >= cutoff]
    weekly = min(sum(e.hours_played for e in recent) / (90 / 7), 60) if recent else 5.0
    years = round(backlog_hours / (weekly * 52), 1) if weekly > 0 else None
    months = round(backlog_hours / (weekly * 4.33), 1) if weekly > 0 else None

    started = [e for e in entries if e.status in (Status.completed, Status.abandoned) or e.hours_played >= 1]
    completed = by_status[Status.completed]
    completion_rate = round(completed / len(started), 2) if started else 0.0

    finished_hours = [e.hours_played for e in entries if e.status == Status.completed and e.hours_played > 0]
    avg_hours_per_finished = sum(finished_hours) / len(finished_hours) if finished_hours else None

    years_known = [e.game.release_year for e in entries if e.game.release_year]
    avg_year = sum(years_known) / len(years_known) if years_known else None

    month_ago = _now() - timedelta(days=30)
    added_recently = sum(1 for e in entries if (a := _aware(e.added_at)) and a >= month_ago)
    most_played = sorted(entries, key=lambda e: e.hours_played, reverse=True)[:6]
    avg_rating = round(sum(e.rating for e in rated) / len(rated), 1) if rated else None

    return {
        "total_games": len(entries),
        "total_hours": round(total_hours, 1),
        "played_games": len(played),
        "rated_games": len(rated),
        "added_last_30_days": added_recently,
        "by_status": [{"status": s, "count": by_status[s]} for s in Status],
        "by_platform": dict(by_platform),
        "by_genre": by_genre,
        "backlog_hours": round(backlog_hours, 1),
        "backlog_games": unplayed,
        "backlog_years_at_current_pace": years,
        "backlog_months_at_current_pace": months,
        "weekly_hours_pace": round(weekly, 1),
        "average_rating": avg_rating,
        "completion_rate": completion_rate,
        "completed_games": completed,
        "started_games": len(started),
        "avg_hours_per_finished": round(avg_hours_per_finished, 1) if avg_hours_per_finished else None,
        "most_played": most_played,
        "personality": _personality(
            genre_share=[(r["genre"], r["hours_share"] if total_hours > 0 else r["games_share"]) for r in by_genre],
            completion=completion_rate, backlog_hours=backlog_hours, avg_rating=avg_rating,
            rated=len(rated), total=len(entries),
            unplayed_share=unplayed / games_total,
            avg_year=avg_year, avg_hours_per_finished=avg_hours_per_finished,
        ),
    }
