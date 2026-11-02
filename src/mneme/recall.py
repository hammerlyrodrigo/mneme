"""Ranked, short retrieval: by words, by path, or both.

No index and no embeddings: entries are scored in memory. A term in the
title or tags counts more than one in the body, and a term that only
prefixes a title word (auth -> authentication) counts a little less than an
exact match. Every term must match somewhere.
"""

from __future__ import annotations

import re

from mneme.model import Entry

TOKEN_RE = re.compile(r"\w+")


def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


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


def score(entry: Entry, terms: list[str]) -> int:
    """0 if any term is missing from the entry; higher is a better match."""
    title = set(tokens(entry.title)) | {entry.id.lower()}
    tags = {t for tag in entry.tags for t in tokens(tag)}
    body = set(tokens(entry.body))
    total = 0
    for term in terms:
        if term in title or term in tags:
            total += 3
        elif any(word.startswith(term) for word in title | tags):
            total += 2
        elif term in body or any(word.startswith(term) for word in body):
            total += 1
        else:
            return 0
    return total


def recall(
    entries: list[Entry],
    query: str = "",
    path: str | None = None,
    include_inactive: bool = False,
    types: tuple[str, ...] = (),
) -> list[Entry]:
    """Matching entries, best first; newer first among equals."""
    terms = tokens(query)
    ranked: list[tuple[int, Entry]] = []
    for entry in entries:
        if types and entry.type not in types:
            continue
        if not include_inactive and not entry.active:
            continue
        if path is not None and not links_path(entry, path):
            continue
        points = score(entry, terms) if terms else 1
        if points:
            ranked.append((points, entry))
    ranked.sort(key=lambda pair: (pair[0], pair[1].active, pair[1].created_dt), reverse=True)
    return [entry for _, entry in ranked]
