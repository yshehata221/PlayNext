"""
Content-based recommender.

The idea in one paragraph: every game becomes a sparse vector over a shared
vocabulary of tags (genre:RPG, theme:Open world, dev:Rockstar Games ...). A user's
"taste" vector is the weighted sum of the games they've rated, where a 10/10
pulls the taste toward that game and a 3/10 pushes it away. Candidate games are
then ranked by cosine similarity to the taste vector, blended with critic score,
and optionally filtered by how much time the user has tonight.

It's deliberately simple and explainable - every recommendation comes with the
tags that actually drove the score, so the UI can say *why*. Collaborative
filtering is the obvious next step once there are enough users to learn from.
"""
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..models import Game, LibraryEntry, Status

# how much each kind of tag matters, relative to genre
TAG_WEIGHTS = {
    "genre": 1.0,
    "theme": 0.8,
    "dev": 0.7,
    "persp": 0.5,
    "mode": 0.4,
}

# statuses tell us something even when there's no explicit rating
IMPLICIT_SIGNAL = {
    Status.completed: 0.4,
    Status.abandoned: -0.4,
}


# "mood" filters: coarse, tag-based, and deliberately generous so a small
# library still yields results. Keys are what the UI sends.
MOODS = {
    "relaxing": {"any": {"Simulator", "Puzzle", "Card & Board Game", "Casual", "Indie", "Sports", "Racing", "Non-fiction"}, "none": {"Horror", "Survival"}},
    "story": {"any": {"Role-playing (RPG)", "RPG", "Adventure", "Drama", "Mystery", "Visual Novel"}, "none": set()},
    "quick": {"max_session": 45},
    "new": {"unplayed": True},
}


def matches_mood(game: Game, mood: str | None, hours_played: float = 0.0) -> bool:
    if not mood or mood not in MOODS:
        return True
    rule = MOODS[mood]
    if "max_session" in rule:
        return game.avg_session_minutes is not None and game.avg_session_minutes <= rule["max_session"]
    if rule.get("unplayed"):
        return hours_played < 1
    tags = set(game.genres or []) | set(game.themes or [])
    return bool(tags & rule["any"]) and not (tags & rule["none"])


def game_tags(game: Game) -> list[tuple[str, str]]:
    tags = [("genre", g) for g in game.genres or []]
    tags += [("theme", t) for t in game.themes or []]
    tags += [("persp", p) for p in game.perspectives or []]
    tags += [("mode", m) for m in game.modes or []]
    if game.developer:
        tags.append(("dev", game.developer))
    return tags


def rating_weight(entry: LibraryEntry) -> float:
    """Map what we know about an entry onto [-1, 1]. 0 means 'no opinion'."""
    if entry.rating is not None:
        return (entry.rating - 5.5) / 4.5
    if entry.status in IMPLICIT_SIGNAL:
        return IMPLICIT_SIGNAL[entry.status]
    if entry.status == Status.playing and entry.hours_played >= 5:
        return 0.3  # sticking with it is a mild thumbs-up
    return 0.0


@dataclass
class Scored:
    game: Game
    score: float
    reasons: list[str] = field(default_factory=list)
    hours_remaining: float | None = None


def catalogue_fingerprint(db) -> tuple[int, int]:
    """
    Cheap "has the catalogue changed?" signal: row count plus the highest id.
    Both change on insert, which is the only thing that alters the tag matrix's
    shape. Metadata edits don't need a rebuild - an added genre shifts one row's
    weights slightly and is picked up on the next natural rebuild.
    """
    from sqlalchemy import func

    from ..models import Game as G

    return db.query(func.count(G.id), func.coalesce(func.max(G.id), 0)).one()


_cache: dict[tuple[int, int], "Recommender"] = {}


def get_recommender(db) -> "Recommender":
    """
    Shared, cached Recommender. Building the matrix is O(games x tags) and was
    happening on every recommendation, browse and friends request; for a
    catalogue of tens of thousands of games that dominated the response time.
    Only one generation is kept, since an older one is never useful.
    """
    key = catalogue_fingerprint(db)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    from ..models import Game as G

    rec = Recommender(db.query(G).all())
    _cache.clear()
    _cache[key] = rec
    return rec


class Recommender:
    def __init__(self, games: list[Game]):
        self.games = games
        vocab: dict[tuple[str, str], int] = {}
        for g in games:
            for tag in game_tags(g):
                vocab.setdefault(tag, len(vocab))
        self.vocab = vocab
        self.inv_vocab = {i: t for t, i in vocab.items()}

        # matrix: one L2-normalised row per game
        m = np.zeros((len(games), max(len(vocab), 1)), dtype=np.float32)
        for row, g in enumerate(games):
            for kind, name in game_tags(g):
                m[row, vocab[(kind, name)]] = TAG_WEIGHTS[kind]
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.matrix = m / norms
        self.index = {g.id: i for i, g in enumerate(games)}

    def taste_vector(self, entries: list[LibraryEntry]) -> np.ndarray | None:
        taste = np.zeros(self.matrix.shape[1], dtype=np.float32)
        signal = 0.0
        for e in entries:
            w = rating_weight(e)
            if w == 0 or e.game_id not in self.index:
                continue
            taste += w * self.matrix[self.index[e.game_id]]
            signal += abs(w)
        if signal == 0:
            return None
        n = np.linalg.norm(taste)
        return taste / n if n else None

    def _tag_ratings(self, entries: list[LibraryEntry]) -> dict[tuple[str, str], float]:
        """Average explicit rating per tag, used to phrase the 'why'."""
        totals: dict[tuple[str, str], list[int]] = defaultdict(list)
        for e in entries:
            if e.rating is None:
                continue
            for tag in game_tags(e.game):
                totals[tag].append(e.rating)
        return {t: sum(v) / len(v) for t, v in totals.items()}

    def recommend(
        self,
        entries: list[LibraryEntry],
        candidates: list[Game],
        hours_available: float | None = None,
        limit: int = 10,
        mood: str | None = None,
    ) -> list[Scored]:
        taste = self.taste_vector(entries)
        tag_ratings = self._tag_ratings(entries)
        hours_by_game = {e.game_id: e.hours_played for e in entries}

        results: list[Scored] = []
        for g in candidates:
            if g.id not in self.index or not matches_mood(g, mood, hours_by_game.get(g.id, 0)):
                continue
            vec = self.matrix[self.index[g.id]]

            # similarity in [-1, 1] -> [0, 1]; no taste yet means everyone starts at neutral
            sim = float(taste @ vec) if taste is not None else 0.0
            sim01 = (sim + 1) / 2
            critic01 = (g.critic_score or 70) / 100  # unknown critic score sits at "fine"

            score = 100 * (0.75 * sim01 + 0.25 * critic01)

            remaining = None
            if g.hours_main is not None:
                remaining = max(g.hours_main - hours_by_game.get(g.id, 0), 0)

            tag_reasons: list[str] = []
            if taste is not None:
                # which tags did the most work? elementwise product, take the top few
                contrib = taste * vec
                for idx in np.argsort(contrib)[::-1][:3]:
                    if contrib[idx] <= 0:
                        break
                    kind, name = self.inv_vocab[idx]
                    avg = tag_ratings.get((kind, name))
                    if kind == "dev":
                        tag_reasons.append(f"Made by {name}, whose games you rate {avg:.0f}/10" if avg else f"Made by {name}")
                    elif avg:
                        tag_reasons.append(f"You rate {name.lower()} games {avg:.1f}/10 on average")
                    else:
                        tag_reasons.append(f"Similar to games you've enjoyed ({name.lower()})")

            # context reasons go first - they're the ones that answer "why tonight?"
            context: list[str] = []
            if hours_available is not None:
                fits_session = g.avg_session_minutes is not None and g.avg_session_minutes <= hours_available * 60
                fits_finish = remaining is not None and remaining <= hours_available
                if not (fits_session or fits_finish):
                    continue
                if fits_finish:
                    context.append(f"You could finish it tonight (about {remaining:.0f}h left)")
                else:
                    context.append(f"Sessions are about {g.avg_session_minutes} minutes")

            played = hours_by_game.get(g.id, 0)
            if played > 0 and g.hours_main:
                context.append(f"You're roughly {min(100 * played / g.hours_main, 99):.0f}% of the way through")

            reasons = context + tag_reasons
            if g.critic_score and g.critic_score >= 85:
                reasons.append(f"Critics scored it {g.critic_score:.0f}")

            results.append(Scored(game=g, score=round(score, 1), reasons=reasons[:4], hours_remaining=remaining))

        results.sort(key=lambda s: s.score, reverse=True)
        return results[:limit]


def plan_night(scored: list[Scored], hours: float, max_games: int = 4) -> list[tuple[Scored, int]]:
    """
    Fill a time budget with more than one game. Greedy over the ranked list:
    each game gets a slot the length of a typical session (or what's left to
    finish it, if that's shorter), until the budget or the game count runs out.
    Returns (recommendation, minutes) pairs.
    """
    budget = int(hours * 60)
    plan: list[tuple[Scored, int]] = []
    for s in scored:
        if len(plan) >= max_games or budget < 20:
            break
        slot = s.game.avg_session_minutes or 60
        if s.hours_remaining is not None and 0 < s.hours_remaining * 60 < slot:
            slot = int(round(s.hours_remaining * 60))
        slot = min(slot, budget)
        if slot < 15:
            continue
        plan.append((s, slot))
        budget -= slot
    return plan


# ---------------------------------------------------------------- collaborative
# Content-based recommendations work from one person's ratings, which is why
# they were built first: they work on day one. With several users rating games,
# user-user collaborative filtering adds something content can't see - that
# people with your taste liked something whose tags look nothing like your
# usual picks. The two are blended rather than swapped.

MIN_OVERLAP = 3          # games in common before two users are comparable
MIN_NEIGHBOURS = 1       # neighbours needed before CF contributes anything


def _ratings_by_user(rows: list[tuple[int, int, int]]) -> dict[int, dict[int, int]]:
    out: dict[int, dict[int, int]] = {}
    for user_id, game_id, rating in rows:
        out.setdefault(user_id, {})[game_id] = rating
    return out


def user_similarity(a: dict[int, int], b: dict[int, int]) -> float | None:
    """
    Pearson correlation over the games both users rated. Pearson rather than
    cosine because it cancels out how generous each person is: someone who rates
    everything 8-10 and someone who uses the whole scale can still agree.
    """
    shared = set(a) & set(b)
    if len(shared) < MIN_OVERLAP:
        return None
    va = np.array([a[g] for g in shared], dtype=float)
    vb = np.array([b[g] for g in shared], dtype=float)
    va -= va.mean()
    vb -= vb.mean()
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(va @ vb / denom)


def collaborative_scores(
    rows: list[tuple[int, int, int]],
    user_id: int,
    exclude: set[int],
) -> dict[int, tuple[float, int]]:
    """
    Predicted 0-1 interest per game for `user_id`, from users with similar
    ratings. Returns {game_id: (score, neighbour_count)} so callers can say how
    much evidence a suggestion rests on.
    """
    by_user = _ratings_by_user(rows)
    me = by_user.pop(user_id, None)
    if not me:
        return {}

    neighbours: list[tuple[float, dict[int, int]]] = []
    for other_id, their in by_user.items():
        sim = user_similarity(me, their)
        if sim is not None and sim > 0.1:      # ignore dissimilar and opposite tastes
            neighbours.append((sim, their))
    if len(neighbours) < MIN_NEIGHBOURS:
        return {}

    weighted: dict[int, list[tuple[float, int]]] = {}
    for sim, their in neighbours:
        for game_id, rating in their.items():
            if game_id in exclude:
                continue
            weighted.setdefault(game_id, []).append((sim, rating))

    out: dict[int, tuple[float, int]] = {}
    for game_id, pairs in weighted.items():
        total_sim = sum(s for s, _ in pairs)
        if total_sim == 0:
            continue
        predicted = sum(s * r for s, r in pairs) / total_sim   # 1-10
        out[game_id] = ((predicted - 1) / 9, len(pairs))
    return out
