"""Report problems in `.memory/`. Never changes anything."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from mneme.model import Entry, branch_filename
from mneme.recall import normalize_link
from mneme.store import Problem, Store

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")


def heading_slug(text: str) -> str:
    """GitHub's anchor for a heading: lowercase, punctuation dropped, spaces to dashes."""
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def anchor_exists(path: Path, anchor: str) -> bool:
    """True if `anchor` names a heading in `path`, or appears in it as a term (`#fr-001`)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    wanted = anchor.lower()
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match and heading_slug(match.group(1)) == wanted:
            return True
    return re.search(rf"(?<![\w-]){re.escape(wanted)}(?![\w-])", text.lower()) is not None


def leftover_handovers(store: Store, branch: str | None, main: str) -> list[Path]:
    """On the main branch, another branch's handover means that branch was merged."""
    if branch != main:
        return []
    own = branch_filename(main)
    return [p for p in store.handover_files() if p.name != own]


def check_links(entry: Entry, root: Path) -> list[str]:
    messages = []
    for link in entry.links:
        target = normalize_link(link)
        if target is None:
            continue
        path = root / target
        if not path.exists():
            messages.append(f"{entry.id}: link target not found: {link}")
        elif "#" in link and path.is_file():
            anchor = link.split("#", 1)[1]
            if anchor and not anchor_exists(path, anchor):
                messages.append(f"{entry.id}: anchor not found: {link}")
    return messages


def check(store: Store, branch: str | None, main: str) -> tuple[list[Problem], int]:
    """Return (problems, number of entries checked)."""
    loaded = store.load()
    problems = list(loaded.problems)
    entries = loaded.entries
    ids = {e.id for e in entries}

    for entry_id, count in Counter(e.id for e in entries).items():
        if count > 1:
            for entry in entries:
                if entry.id == entry_id and entry.path:
                    problems.append(Problem(entry.path, f"duplicate id {entry_id} ({count} files)"))

    for entry in entries:
        assert entry.path is not None
        name = entry.path.name
        if not (name == f"{entry.id}.md" or name.startswith(f"{entry.id}-")):
            problems.append(Problem(entry.path, f"filename does not start with id {entry.id}"))
        for ref in entry.supersedes:
            if ref not in ids:
                problems.append(Problem(entry.path, f"{entry.id}: supersedes unknown entry {ref}"))
        if entry.resolved_by and entry.resolved_by not in ids:
            problems.append(Problem(entry.path, f"{entry.id}: resolved_by unknown entry {entry.resolved_by}"))
        if store.is_archived(entry):
            # Archived entries are history; the code they linked to may be long gone.
            if entry.active:
                problems.append(Problem(entry.path, f"{entry.id} is {entry.status} but archived; "
                                                    f"run `mneme archive --restore {entry.id}`"))
            continue
        problems += [Problem(entry.path, m) for m in check_links(entry, store.root)]

    for path in store.handover_files():
        try:
            store.read_handover(path)
        except Exception as exc:  # noqa: BLE001 - any unreadable handover is a problem to report
            problems.append(Problem(path, f"unreadable handover: {exc}"))
    for path in leftover_handovers(store, branch, main):
        problems.append(
            Problem(path, f"handover from a merged branch; fold what matters into {branch_filename(main)} "
                          "or new entries, then delete it")
        )
    return problems, len(entries)
