"""What a branch added to or changed in memory, compared with a base branch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mneme.model import TYPES, Entry
from mneme.root import MEMORY_DIRNAME, git
from mneme.store import Store


class ChangesError(Exception):
    pass


@dataclass
class Change:
    kind: str  # "added", "changed", "deleted", "archived" or "restored"
    path: Path
    entry: Entry | None  # None for a deleted or unreadable file


def resolve_base(root: Path, base: str) -> str:
    for ref in (base, f"origin/{base}"):
        if git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], root) is not None:
            return ref
    raise ChangesError(f"base branch {base!r} not found (locally or on origin)")


def _split_z(output: str) -> list[str]:
    return [part for part in output.split("\0") if part]


def changed_paths(root: Path, base: str) -> dict[str, str]:
    """{repo-relative path: kind} for `.memory/`, committed since `base` plus uncommitted."""
    ref = resolve_base(root, base)
    kinds: dict[str, str] = {}
    committed = git(
        ["diff", "--name-status", "--no-renames", "-z", f"{ref}...HEAD", "--", MEMORY_DIRNAME], root
    )
    if committed is None:
        raise ChangesError(f"git diff against {ref} failed")
    parts = _split_z(committed)
    for status, path in zip(parts[::2], parts[1::2]):
        kinds[path] = {"A": "added", "D": "deleted"}.get(status[0], "changed")

    working = git(
        ["status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all", "--", MEMORY_DIRNAME],
        root,
        strip=False,
    )
    for item in _split_z(working or ""):
        code, path = item[:2], item[3:]
        before = kinds.get(path)
        if "D" in code:
            if before == "added":
                del kinds[path]
            else:
                kinds[path] = "deleted"
        elif code == "??" or "A" in code:
            kinds[path] = "added" if before != "changed" else "changed"
        elif before is None:
            kinds[path] = "changed"
    return kinds


def branch_changes(store: Store, base: str) -> list[Change]:
    """Entry files changed on this branch, in creation order (deleted ones last)."""
    kinds = changed_paths(store.root, base)
    by_path = {e.path.resolve(): e for e in store.load().entries if e.path}
    live_dirs = {store.type_dir(t).resolve() for t in TYPES}
    archive_dirs = {store.archive_dir(t).resolve() for t in TYPES}
    changes: list[Change] = []
    for rel, kind in kinds.items():
        path = (store.root / rel).resolve()
        if path.suffix != ".md" or path.parent not in live_dirs | archive_dirs:
            continue
        changes.append(Change(kind, path, None if kind == "deleted" else by_path.get(path)))
    changes = _pair_moves(changes, archive_dirs)
    changes.sort(key=lambda c: (c.entry is None, c.entry.created_dt if c.entry else 0, str(c.path)))
    return changes


def _pair_moves(changes: list[Change], archive_dirs: set[Path]) -> list[Change]:
    """A file deleted in one place and added under the same name in the other is one move."""
    deleted = {(c.path.name, c.path.parent in archive_dirs): c for c in changes if c.kind == "deleted"}
    paired: list[Change] = []
    for change in changes:
        if change.kind == "added":
            in_archive = change.path.parent in archive_dirs
            source = deleted.pop((change.path.name, not in_archive), None)
            if source is not None:
                paired.append(Change("archived" if in_archive else "restored", change.path, change.entry))
                continue
        paired.append(change)
    gone = {id(c) for c in deleted.values()}
    return [c for c in paired if c.kind != "deleted" or id(c) in gone]


# Moves into or out of the archive: counted in the PR block, not listed.
MOVES = ("archived", "restored")

HEADINGS = {
    "decision": "Decisions",
    "learning": "Learnings",
    "concept": "Concepts",
    "reminder": "Reminders",
    "note": "Notes",
}


def render_text(changes: list[Change], root: Path) -> str:
    if not changes:
        return "No memory changes on this branch."
    lines = []
    for change in changes:
        if change.entry:
            lines.append(f"{change.kind:<8} {change.entry.type:<9} {change.entry.oneline()}")
        else:
            lines.append(f"{change.kind:<8} {'?':<9} {change.path.relative_to(root.resolve()).as_posix()}")
    return "\n".join(lines)


def render_markdown(changes: list[Change]) -> str:
    """A block for a PR description: what this branch decided, learned and left open."""
    entries = [c.entry for c in changes if c.entry and c.kind not in MOVES]
    moved = [c for c in changes if c.kind in MOVES]
    if not entries and not moved:
        return ""
    lines = ["### Project memory", ""]
    for kind in MOVES:
        count = sum(1 for c in moved if c.kind == kind)
        if count:
            lines += [f"{kind.capitalize()} {count} entr{'ies' if count > 1 else 'y'}.", ""]
    for entry_type, heading in HEADINGS.items():
        group = [e for e in entries if e.type == entry_type]
        if group:
            lines.append(f"**{heading}**")
            lines += [f"- `{e.id}` {e.title}" + ("" if e.active else f" ({e.status})") for e in group]
            lines.append("")
    open_q = [e for e in entries if e.type == "question" and e.status == "open"]
    settled_q = [e for e in entries if e.type == "question" and e.status != "open"]
    if open_q:
        lines.append("**Still open**")
        lines += [f"- `{e.id}` {e.title}" for e in open_q]
        lines.append("")
    if settled_q:
        lines.append("**Questions settled**")
        lines += [f"- `{e.id}` {e.title} ({e.status})" for e in settled_q]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
