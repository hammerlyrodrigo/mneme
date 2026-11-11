"""Ranked, short retrieval: by words, by path, or both.

No index and no embeddings: entries are scored in memory. Words are lightly
stemmed (conflicts -> conflict), and a term that only prefixes a word
(auth -> authentication) counts a little less than an exact match. A match in
the title, tags or keywords counts more than one in the summary, and that
more than one in the body. Each term is weighted by how rare it is across
entries, so the distinctive word in a query decides the ranking.

Entries that match every term come first. If none does, the entries that
match some terms are returned instead, marked partial, with the terms they
miss, so the caller can rephrase rather than conclude nothing is known.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from mneme.model import Entry

TOKEN_RE = re.compile(r"\w+")

# Dropped from queries that have other words: they match everything.
STOPWORDS = frozenset(
    "a an and are as at be by did do does for from how i in is it of on or "
    "should that the this to was we what when where which who why will with".split()
)

# Points per field for an exact (stemmed) match; a prefix match scores one less.
WEIGHTS = (("title", 3), ("summary", 2), ("body", 1))
MIN_PREFIX = 3


def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def stem(word: str) -> str:
    """A light suffix stripper; the same on both sides is all that matters."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3 and not word.endswith("ss"):
            word = word[: -len(suffix)]
            break
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    return word


def query_terms(query: str) -> dict[str, str]:
    """{stemmed term: the word as typed}, in query order."""
    words = tokens(query)
    kept = [w for w in words if w not in STOPWORDS] or words
    terms: dict[str, str] = {}
    for word in kept:
        terms.setdefault(stem(word), word)
    return terms


def normalize_link(link: str) -> str | None:
    """A link as a repo-relative POSIX path, without `#anchor`; None for URLs."""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", link) or link.startswith("mailto:"):
        return None
    path = link.split("#", 1)[0].replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/") or None


def covers(link: str, path: str) -> bool:
    """True if `link` is `path`, a directory above it, or a file below it."""
    if not path:
        return True
    return link == path or path.startswith(link + "/") or link.startswith(path + "/")


def links_path(entry: Entry, path: str) -> bool:
    return any((n := normalize_link(link)) is not None and covers(n, path) for link in entry.links)


def fields(entry: Entry) -> dict[str, set[str]]:
    """Stemmed words per scored field."""
    title = [entry.title, entry.id, *entry.tags, *entry.keywords]
    return {
        "title": {stem(t) for text in title for t in tokens(text)},
        "summary": {stem(t) for t in tokens(entry.summary)},
        "body": {stem(t) for t in tokens(entry.body)},
    }


def term_points(words: dict[str, set[str]], term: str) -> int:
    """Points for one term in one entry; 0 if it appears nowhere."""
    best = 0
    for name, weight in WEIGHTS:
        if term in words[name]:
            return max(best, weight)
        if len(term) >= MIN_PREFIX and any(w.startswith(term) for w in words[name]):
            best = max(best, weight - 1 or 1)
    return best


@dataclass
class Hit:
    entry: Entry
    score: float
    missing: list[str] = field(default_factory=list)


@dataclass
class Result:
    hits: list[Hit]
    # True when no entry matched every term and these are the best partial matches.
    partial: bool = False

    @property
    def entries(self) -> list[Entry]:
        return [hit.entry for hit in self.hits]


def recall(
    entries: list[Entry],
    query: str = "",
    path: str | None = None,
    include_inactive: bool = False,
    types: tuple[str, ...] = (),
) -> Result:
    """Matching entries, best first; newer first among equals."""
    pool = [
        e for e in entries
        if (not types or e.type in types)
        and (include_inactive or e.active)
        and (path is None or links_path(e, path))
    ]
    terms = query_terms(query)
    if not terms:
        return Result(_ranked([Hit(e, 1.0) for e in pool]))

    words = {id(e): fields(e) for e in pool}
    points = {id(e): {t: term_points(words[id(e)], t) for t in terms} for e in pool}
    # Rarity is judged across all candidates, so a word every entry has counts little.
    n = len(pool)
    df = {t: sum(1 for e in pool if points[id(e)][t]) for t in terms}
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in terms}

    full, partial = [], []
    for e in pool:
        got = points[id(e)]
        score = sum(got[t] * idf[t] for t in terms)
        if not score:
            continue
        missing = [word for t, word in terms.items() if not got[t]]
        (partial if missing else full).append(Hit(e, score, missing))
    if full:
        return Result(_ranked(full))
    return Result(_ranked(partial), partial=bool(partial))


def _ranked(hits: list[Hit]) -> list[Hit]:
    """Fewest missing terms first, then best score, then active and newer."""
    return sorted(
        hits,
        key=lambda h: (-len(h.missing), h.score, h.entry.active, h.entry.created_dt),
        reverse=True,
    )
