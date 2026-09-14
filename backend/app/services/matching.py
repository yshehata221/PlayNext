"""
Title normalisation for matching scanner/launcher names against our catalogue.
Launchers are inconsistent: "AssassinsCreedValhalla", "Cyberpunk 2077 (GOG)",
"The Witcher® 3: Wild Hunt – Game of the Year Edition". We collapse all of
those to a comparable key and fuzz on the last step.
"""
import re
from difflib import SequenceMatcher

NOISE = re.compile(
    r"\b(game of the year|goty|definitive|complete|deluxe|ultimate|gold|premium|enhanced|remastered|legendary|"
    r"anniversary|special|standard|digital|edition|directors? cut|the game|windows|pc|x64|x86)\b",
    re.I,
)
TRADEMARKS = re.compile(r"[®™©]")
BRACKETS = re.compile(r"[\(\[].*?[\)\]]")


def split_camel(s: str) -> str:
    # "AssassinsCreedValhalla" -> "Assassins Creed Valhalla", but leave "GTA5" alone
    if " " in s or not re.search(r"[a-z][A-Z]", s):
        return s
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)", " ", s)


def normalise(title: str) -> str:
    t = split_camel(title)
    t = TRADEMARKS.sub("", t)
    t = BRACKETS.sub("", t)
    t = NOISE.sub(" ", t)
    t = re.sub(r"['’]", "", t)  # apostrophes vanish rather than split: assassin's -> assassins
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return " ".join(t.split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise(a), normalise(b)).ratio()
