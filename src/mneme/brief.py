"""The session-start view: small and bounded, however much memory there is."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mneme.changes import ChangesError, branch_changes
from mneme.check import leftover_handovers
from mneme.model import Entry, FormatError, parse_sections
from mneme.store import Store

CLARIFICATION_RE = re.compile(r"\[NEEDS CLARIFICATION[^\]]*\]", re.IGNORECASE)


@dataclass
class Limits:
    handover_lines: int = 30
    questions: int = 5
    reminders: int = 5
    decisions: int = 3
    markers: int = 3


def clarification_markers(root: Path, spec_dirs: list[str]) -> list[tuple[str, int, str]]:
    """(path, line number, marker) for each `[NEEDS CLARIFICATION ...]` in spec Markdown."""
    found = []
    for spec_dir in spec_dirs:
        base = root / spec_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(lines, start=1):
                for match in CLARIFICATION_RE.finditer(line):
                    found.append((path.relative_to(root).as_posix(), number, match.group(0)))
    return found


def _capped(items: list[Entry], limit: int, more_hint: str) -> list[str]:
    lines = [f"  {e.oneline()}" for e in items[:limit]]
    if len(items) > limit:
        lines.append(f"  (+{len(items) - limit} more: {more_hint})")
    return lines


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def build_brief(
    store: Store,
    branch: str | None,
    main: str,
    spec_dirs: list[str],
    limits: Limits = Limits(),
) -> str:
    loaded = store.load()
    entries = loaded.entries
    problem_count = len(loaded.problems)
    out: list[str] = []

    if branch:
        try:
            handover = store.load_handover(branch)
        except (FormatError, OSError, UnicodeDecodeError):
            handover, problem_count = None, problem_count + 1
        if handover:
            out.append(f"Handover for {branch} (updated {handover.updated}):")
            body = handover.body.strip().splitlines()
            out += [f"  {line}" if line else "" for line in body[: limits.handover_lines]]
            if len(body) > limits.handover_lines:
                out.append(f"  ... ({len(body) - limits.handover_lines} more lines in "
                           f"{handover.path.relative_to(store.root).as_posix()})")
        else:
            out.append(f"Handover for {branch}: none yet. Write one with `mneme handover` before you stop.")
    else:
        out.append("Detached HEAD: no branch handover.")

    if branch != main:
        try:
            main_handover = store.load_handover(main)
        except (FormatError, OSError, UnicodeDecodeError):
            main_handover = None
        if main_handover:
            summary = _first_line(parse_sections(main_handover.body)[1].get("Summary", main_handover.body))
            out.append(f"Main ({main}) handover: {summary}")
        if branch:
            try:
                changed = [c.entry for c in branch_changes(store, main)
                           if c.entry and c.kind in ("added", "changed")]
            except ChangesError:
                changed = []
            if changed:
                counts: dict[str, int] = {}
                for entry in changed:
                    counts[entry.type] = counts.get(entry.type, 0) + 1
                summary = ", ".join(f"{n} {t}{'s' if n > 1 else ''}" for t, n in counts.items())
                out.append(f"This branch so far: {summary} (mneme changes)")

    newest_first = sorted(entries, key=lambda e: e.created_dt, reverse=True)
    sections = [
        ("Open questions", [e for e in newest_first if e.type == "question" and e.active],
         limits.questions, "mneme list question"),
        ("Pending reminders", [e for e in newest_first if e.type == "reminder" and e.active],
         limits.reminders, "mneme list reminder"),
    ]
    for title, items, limit, hint in sections:
        if items:
            out.append("")
            out.append(f"{title} ({len(items)}):")
            out += _capped(items, limit, hint)

    decisions = [e for e in newest_first if e.type == "decision" and e.active]
    if decisions:
        out.append("")
        shown = min(limits.decisions, len(decisions))
        out.append(f"Recent decisions ({shown} of {len(decisions)}):")
        out += [f"  {e.oneline()}" for e in decisions[:shown]]

    markers = clarification_markers(store.root, spec_dirs)
    if markers:
        out.append("")
        out.append(f"Spec clarifications needed ({len(markers)}):")
        out += [f"  {path}:{line} {text}" for path, line, text in markers[: limits.markers]]
        if len(markers) > limits.markers:
            out.append(f"  (+{len(markers) - limits.markers} more)")

    problem_count += len(leftover_handovers(store, branch, main))
    if problem_count:
        out.append("")
        out.append(f"! {problem_count} problem{'s' if problem_count > 1 else ''} in .memory/: run `mneme check`")

    out.append("")
    out.append("More: `mneme recall <words>`, `mneme recall --path <file>`, `mneme show <id>`")
    return "\n".join(out) + "\n"
