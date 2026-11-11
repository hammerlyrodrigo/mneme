"""`mneme migrate`: import a mneme v0 log (`.memory/log/entries.jsonl`).

v0 kept one JSON record per line: `create` records, and `patch` records that
change an earlier entry. Replaying them in order, exactly as v0's
`load_entries()` did, gives each entry's final state; that state is written as
one entry file. Legacy IDs and authors are kept, timestamps become UTC, and no
branch is recorded, because v0 guessed it at load time.

Differences from v0 are reported, never silent: patches to unknown IDs and
repeated creates (both ignored or overwritten by v0 too), statuses v0 had but
this format doesn't, and links that name entries rather than files.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from mneme.model import (
    HANDOVER_SECTIONS,
    SECTIONS,
    STATUSES,
    Entry,
    FormatError,
    format_ts,
    is_valid_id,
    parse_ts,
    render_sections,
)
from mneme.store import Handover

# v0 statuses that no longer exist, by what they meant.
RETIRED = {"consolidated": "superseded", "obsolete": "archived", "stale": "archived"}
# Where a type has no `archived` or `superseded` status, the nearest one it has.
NEAREST = {
    ("decision", "archived"): "deprecated",
    ("question", "archived"): "dropped",
    ("reminder", "archived"): "dropped",
    ("question", "superseded"): "dropped",
    ("reminder", "superseded"): "dropped",
}
# v0 field names that are not simply the section name in lower case.
FIELD_SECTION = {"answer": "Answer", "note": "Note", "notes": "Notes"}
# Top-level v0 keys that are folded into the entry or dropped.
CONSUMED = {
    "op", "id", "type", "title", "status", "created_at", "updated_at", "author", "branch",
    "tags", "links", "fields", "supersedes", "consolidates", "superseded_by", "consolidated_into",
}


KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


class MigrateError(Exception):
    pass


@dataclass
class Plan:
    entries: list[Entry] = field(default_factory=list)
    handover: Handover | None = None
    handovers_dropped: int = 0
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def fold(lines: list[str]) -> tuple[list[dict], list[str]]:
    """v0's `load_entries()`: the final state of every entry, plus what was dropped."""
    by_id: dict[str, dict] = {}
    notes: list[str] = []
    unknown, repeated = Counter(), Counter()
    for number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MigrateError(f"line {number}: invalid JSON: {exc}") from None
        if not isinstance(record, dict):
            raise MigrateError(f"line {number}: expected a JSON object")
        op = record.get("op", "create")
        if op == "create":
            if "id" not in record:
                raise MigrateError(f"line {number}: create record without an id")
            if record["id"] in by_id:
                repeated[record["id"]] += 1
            rec = dict(record)
            rec.setdefault("tags", [])
            rec.setdefault("links", [])
            rec.setdefault("fields", {})
            rec.setdefault("consolidates", [])
            by_id[rec["id"]] = rec
        elif op == "patch":
            target = by_id.get(record.get("target_id"))
            if target is None:
                unknown[record.get("target_id")] += 1
                continue
            if "updated_at" in record:
                target["updated_at"] = record["updated_at"]
            for key, value in (record.get("patch") or {}).items():
                if key == "fields":
                    if isinstance(value, dict):
                        target.setdefault("fields", {}).update(value)
                    continue
                target[key] = value
        else:
            raise MigrateError(f"line {number}: unknown op {op!r}")
    if unknown:
        notes.append(f"ignored {sum(unknown.values())} patch(es) to unknown ids, as v0 did: "
                     + ", ".join(sorted(str(k) for k in unknown)))
    if repeated:
        notes.append(f"{len(repeated)} id(s) were created more than once; the last create wins, as in v0: "
                     + ", ".join(sorted(repeated)))
    return list(by_id.values()), notes


def utc(value: object, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise FormatError(f"missing {what}")
    return format_ts(parse_ts(value))


def as_list(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    raise FormatError(f"expected a list, got {value!r}")


def map_status(entry_type: str, status: object) -> str:
    if status in (None, ""):
        status = {"decision": "accepted", "question": "open", "reminder": "pending"}.get(entry_type, "active")
    status = RETIRED.get(str(status), str(status))
    status = NEAREST.get((entry_type, status), status)
    if status not in STATUSES[entry_type]:
        raise FormatError(f"status {status!r} has no equivalent for a {entry_type}")
    return status


def to_entry(rec: dict) -> Entry:
    entry_type = rec.get("type")
    if entry_type not in SECTIONS:
        raise FormatError(f"unknown type {entry_type!r}")
    fields = {k: v for k, v in (rec.get("fields") or {}).items() if v not in (None, "")}
    title = str(rec.get("title") or fields.get("term") or fields.get("text") or "").strip()
    title = title.splitlines()[0] if title else "Untitled"

    preamble = ""
    sections: dict[str, str] = {}
    extra: dict[str, str | list[str]] = {}
    resolved_by = str(fields.pop("resolved_by", "") or "")
    fields.pop("term", None)
    for name, value in fields.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        text = text.strip()
        if entry_type == "note" and name == "body":
            preamble = text
            continue
        section = FIELD_SECTION.get(name, name.replace("_", " ").capitalize())
        # A question's text and a reminder's action are usually the title itself.
        if text == title and section in ("Question", "Action"):
            continue
        sections[section] = text

    links, related = [], []
    for link in as_list(rec.get("links")):
        (related if is_valid_id(link) else links).append(link.replace("\\", "/"))
    if related:
        extra["related"] = related
    for key, value in rec.items():
        if key in CONSUMED or value in (None, "", []):
            continue
        if not KEY_RE.match(key):
            raise FormatError(f"field {key!r} cannot be a frontmatter key")
        if isinstance(value, list):
            extra[key] = as_list(value)
        else:
            extra[key] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    entry = Entry(
        id=str(rec["id"]),
        type=entry_type,
        title=title,
        status=map_status(entry_type, rec.get("status")),
        created=utc(rec.get("created_at"), "created_at"),
        updated=utc(rec["updated_at"], "updated_at") if rec.get("updated_at") else "",
        author=str(rec.get("author") or ""),
        tags=as_list(rec.get("tags")),
        links=links,
        supersedes=as_list(rec.get("supersedes")) + as_list(rec.get("consolidates")),
        resolved_by=resolved_by,
        extra=extra,
        body=render_sections(preamble, sections, SECTIONS[entry_type]),
    )
    if entry.updated == entry.created:
        entry.updated = ""
    return entry


def link_replacements(records: list[dict], entries: dict[str, Entry], plan: Plan) -> None:
    """Point `superseded_by` and `consolidated_into` patches at the newer entry's `supersedes`."""
    for rec in records:
        old = entries.get(str(rec.get("id")))
        if old is None:
            continue
        for key in ("superseded_by", "consolidated_into"):
            newer_id = rec.get(key)
            if not newer_id:
                continue
            newer = entries.get(str(newer_id))
            if newer is not None and newer.type == old.type:
                if old.id not in newer.supersedes:
                    newer.supersedes.append(old.id)
            else:
                old.extra[key] = str(newer_id)
                if newer is None:
                    plan.notes.append(f"{old.id}: {key} {newer_id} is not in the log; kept as a note")
    known = set(entries)
    for entry in entries.values():
        missing = [ref for ref in entry.supersedes if ref not in known]
        if missing:
            entry.supersedes = [ref for ref in entry.supersedes if ref in known]
            entry.extra["supersedes_missing"] = missing
            plan.notes.append(f"{entry.id}: supersedes unknown {', '.join(missing)}; kept as a note")


def plan_migration(path: Path) -> Plan:
    plan = Plan()
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise MigrateError(f"{path}: {exc}") from None
    records, plan.notes = fold(lines)

    handovers = [r for r in records if r.get("type") == "handover"]
    others = [r for r in records if r.get("type") != "handover"]
    if handovers:
        newest = max(handovers, key=lambda r: parse_ts(str(r.get("created_at"))))
        fields = newest.get("fields") or {}
        body = {name: str(fields.get(name.lower()) or "").strip() for name in HANDOVER_SECTIONS}
        plan.handover = Handover(
            branch="", updated=utc(newest.get("created_at"), "created_at"),
            author=str(newest.get("author") or ""),
            body=render_sections("", body, HANDOVER_SECTIONS),
        )
        plan.handovers_dropped = len(handovers) - 1

    entries: dict[str, Entry] = {}
    for rec in others:
        try:
            entry = to_entry(rec)
            entry.validate()
        except (FormatError, KeyError) as exc:
            plan.problems.append(f"{rec.get('id', '?')}: {exc}")
            continue
        entries[entry.id] = entry
    link_replacements(others, entries, plan)
    for entry in entries.values():
        try:
            entry.validate()
        except FormatError as exc:
            plan.problems.append(str(exc))
    plan.entries = sorted(entries.values(), key=lambda e: (e.created_dt, e.id))
    mapped = Counter(
        (e.type, str(r.get("status")), e.status)
        for r in others if (e := entries.get(str(r.get("id")))) and r.get("status") not in (None, "", e.status)
    )
    if mapped:
        plan.notes.append("mapped statuses: " + ", ".join(
            f"{n} {t} {old} -> {new}" for (t, old, new), n in sorted(mapped.items())))
    return plan
