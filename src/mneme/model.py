"""Entry model and the on-disk file format.

An entry is one Markdown file with frontmatter in a documented YAML subset:

    ---
    id: D-7f3a2c
    type: decision
    title: Use one file per entry
    status: accepted
    created: 2026-11-02T14:03:11Z
    tags: [storage, git]
    ---

    ## Context
    ...

The subset: one `key: value` per line, where a value is a plain scalar, a
single- or double-quoted string, or an inline list `[a, "b, c"]`. Every value
is a string; nothing is coerced to bool or number. `#` starts a comment only
on its own line. On read, a key with no value may be followed by a block list,
one `- item` per line, the style editors and formatters write; lists are
always written inline. Anything else is a parse error, reported rather than
guessed.
"""

from __future__ import annotations

import json
import re
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TYPES = ("decision", "learning", "question", "reminder", "concept", "note")

PREFIX = {
    "decision": "D",
    "learning": "L",
    "question": "Q",
    "reminder": "R",
    "concept": "C",
    "note": "N",
}

STATUSES = {
    "decision": ("proposed", "accepted", "rejected", "deprecated", "superseded"),
    "learning": ("active", "archived", "superseded"),
    "question": ("open", "resolved", "dropped"),
    "reminder": ("pending", "done", "dropped"),
    "concept": ("active", "archived", "superseded"),
    "note": ("active", "archived", "superseded"),
}

DEFAULT_STATUS = {
    "decision": "accepted",
    "learning": "active",
    "question": "open",
    "reminder": "pending",
    "concept": "active",
    "note": "active",
}

# Hidden from `brief` and `recall` unless asked for: settled, replaced or abandoned.
INACTIVE_STATUSES = frozenset(
    {"rejected", "deprecated", "superseded", "archived", "dropped", "resolved", "done"}
)

# Body sections per type, in the order they are written. A note has a free body.
SECTIONS = {
    "decision": ("Context", "Decision", "Consequences"),
    "learning": ("Tried", "Result", "Takeaway"),
    "question": ("Question", "Answer"),
    "reminder": ("Trigger", "Action", "Note"),
    "concept": ("Definition", "Notes"),
    "note": (),
}

HANDOVER_SECTIONS = ("Summary", "Done", "Next", "Blockers")

# Known frontmatter keys, in the order they are written. Unknown keys follow.
KEY_ORDER = (
    "id", "type", "title", "status", "created", "updated",
    "author", "branch", "tags", "links", "supersedes", "resolved_by",
)
LIST_KEYS = frozenset({"tags", "links", "supersedes"})

ID_RE = re.compile(r"^[A-Z]-[0-9a-f]{6}$")
# Accepted on read so migrated entries keep their IDs: D0001, R-261102-c1d3.
LEGACY_ID_RE = re.compile(r"^[A-Z](\d{4,}|-\d{6}-[0-9a-f]{4})$")


class FormatError(ValueError):
    """A file or value that does not follow the entry format."""


# --- time -------------------------------------------------------------------


def now_utc() -> str:
    return format_ts(datetime.now(timezone.utc))


def format_ts(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> datetime:
    """Parse an ISO 8601 timestamp with `Z` or an offset into an aware UTC datetime."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise FormatError(f"bad timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise FormatError(f"timestamp without time zone: {value!r}")
    return dt.astimezone(timezone.utc)


# --- ids and names ----------------------------------------------------------


def new_id(entry_type: str, taken: set[str] | frozenset[str] = frozenset()) -> str:
    for _ in range(100):
        candidate = f"{PREFIX[entry_type]}-{secrets.token_hex(3)}"
        if candidate not in taken:
            return candidate
    raise RuntimeError("could not find a free id")  # 16M ids per type; unreachable in practice


def is_valid_id(value: str) -> bool:
    return bool(ID_RE.match(value) or LEGACY_ID_RE.match(value))


def slugify(title: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(text) > max_len:
        text = text[:max_len].rsplit("-", 1)[0] or text[:max_len]
    return text or "untitled"


def branch_filename(branch: str) -> str:
    return branch.replace("/", "--") + ".md"


# --- frontmatter ------------------------------------------------------------

_PLAIN_RE = re.compile(r"^[^\s\"'\[\]{}#&*!|>%@`,][^\n]*$")


def _needs_quotes(value: str) -> bool:
    if value == "" or value != value.strip():
        return True
    if not _PLAIN_RE.match(value):
        return True
    if ": " in value or " #" in value or value.endswith(":"):
        return True
    return value.lower() in {"true", "false", "yes", "no", "on", "off", "null", "~"}


def _dump_scalar(value: str, in_list: bool = False) -> str:
    if _needs_quotes(value) or (in_list and "," in value):
        return json.dumps(value, ensure_ascii=False)
    return value


def dump_frontmatter(meta: dict[str, str | list[str]]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            items = ", ".join(_dump_scalar(v, in_list=True) for v in value)
            lines.append(f"{key}: [{items}]")
        else:
            lines.append(f"{key}: {_dump_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_quoted(text: str, pos: int) -> tuple[str, int]:
    """Parse a quoted string starting at text[pos]; return (value, index after it)."""
    quote = text[pos]
    if quote == '"':
        decoder = json.JSONDecoder()
        try:
            value, end = decoder.raw_decode(text, pos)
        except json.JSONDecodeError as exc:
            raise FormatError(f"bad double-quoted string: {text[pos:]!r}") from exc
        if not isinstance(value, str):
            raise FormatError(f"bad double-quoted string: {text[pos:]!r}")
        return value, end
    # Single quotes: '' is an escaped quote, nothing else is special.
    out, i = [], pos + 1
    while i < len(text):
        if text[i] == "'":
            if text[i + 1 : i + 2] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        out.append(text[i])
        i += 1
    raise FormatError(f"unterminated single-quoted string: {text[pos:]!r}")


def _parse_list(text: str) -> list[str]:
    inner = text[1:-1].strip()
    items: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] in " \t":
            i += 1
            continue
        if inner[i] in "\"'":
            value, i = _parse_quoted(inner, i)
            rest = inner[i:].lstrip()
            if rest and not rest.startswith(","):
                raise FormatError(f"unexpected text after list item: {rest!r}")
            i = len(inner) - len(rest) + 1
        else:
            end = inner.find(",", i)
            end = len(inner) if end == -1 else end
            value = inner[i:end].strip()
            if not value:
                raise FormatError(f"empty list item in {text!r}")
            i = end + 1
        items.append(value)
    return items


def _parse_value(raw: str) -> str | list[str]:
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("["):
        if not text.endswith("]"):
            raise FormatError(f"unterminated list: {text!r}")
        return _parse_list(text)
    if text[0] in "\"'":
        value, end = _parse_quoted(text, 0)
        if text[end:].strip():
            raise FormatError(f"unexpected text after string: {text[end:]!r}")
        return value
    if text[0] in "{&*!|>%@`":
        raise FormatError(f"unsupported YAML syntax: {text!r}")
    return text


_BLOCK_ITEM_RE = re.compile(r"^\s*-(\s+(.*))?$")


def _parse_block_item(raw: str) -> str:
    """One `- item` of a block list: a plain scalar or a quoted string."""
    value = _parse_value(raw)
    if isinstance(value, list):
        raise FormatError(f"nested lists are not supported: {raw.strip()!r}")
    if not value:
        raise FormatError("empty list item")
    return value


def split_document(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Split a Markdown file into (frontmatter, body). Accepts CRLF and a BOM."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        raise FormatError("missing frontmatter: file must start with '---'")
    meta: dict[str, str | list[str]] = {}
    # The key whose value was empty, so `- item` lines below it form a block list.
    open_key: str | None = None
    for n, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if stripped == "---":
            body = "\n".join(lines[n:])
            return meta, body.lstrip("\n")
        if not stripped or stripped.startswith("#"):
            continue
        item = _BLOCK_ITEM_RE.match(line)
        if item and open_key is not None:
            try:
                value = _parse_block_item(item.group(2) or "")
            except FormatError as exc:
                raise FormatError(f"line {n}: {exc}") from None
            current = meta[open_key]
            meta[open_key] = (current if isinstance(current, list) else []) + [value]
            continue
        if line[0] in " \t":
            raise FormatError(f"line {n}: multi-line values are not supported; "
                              f"put the value on one line: {line!r}")
        if ":" not in line:
            raise FormatError(f"line {n}: expected 'key: value', got {line!r}")
        key, _, raw = line.partition(":")
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", key):
            raise FormatError(f"line {n}: bad key {key!r}")
        if key in meta:
            raise FormatError(f"line {n}: duplicate key {key!r}")
        try:
            meta[key] = _parse_value(raw)
        except FormatError as exc:
            raise FormatError(f"line {n}: {exc}") from None
        open_key = key if meta[key] == "" else None
    raise FormatError("unterminated frontmatter: no closing '---'")


# --- body sections ----------------------------------------------------------

_HEADING_RE = re.compile(r"^## +(.+?)\s*$")


def parse_sections(body: str) -> tuple[str, dict[str, str]]:
    """Split a body into (text before the first `## ` heading, {heading: text})."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: list[str] = preamble
    in_fence = False
    for line in body.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        match = None if in_fence else _HEADING_RE.match(line)
        if match:
            current = sections.setdefault(match.group(1), [])
            continue
        current.append(line)
    return (
        "\n".join(preamble).strip(),
        {name: "\n".join(lines).strip() for name, lines in sections.items()},
    )


def render_sections(preamble: str, sections: dict[str, str], order: tuple[str, ...] = ()) -> str:
    names = [n for n in order if n in sections] + [n for n in sections if n not in order]
    parts = [preamble] if preamble else []
    parts += [f"## {name}\n\n{sections[name]}" for name in names if sections[name]]
    return "\n\n".join(parts) + "\n" if parts else ""


# --- entries ----------------------------------------------------------------


@dataclass
class Entry:
    id: str
    type: str
    title: str
    status: str
    created: str
    updated: str = ""
    author: str = ""
    branch: str = ""
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    resolved_by: str = ""
    extra: dict[str, str | list[str]] = field(default_factory=dict)
    body: str = ""
    # Where the entry was loaded from; set by the store, never serialized.
    path: Path | None = field(default=None, compare=False, repr=False)

    @property
    def active(self) -> bool:
        return self.status not in INACTIVE_STATUSES

    @property
    def created_dt(self) -> datetime:
        return parse_ts(self.created)

    def filename(self) -> str:
        return f"{self.id}-{slugify(self.title)}.md"

    def oneline(self) -> str:
        return f"{self.id}  {self.title}  [{self.status}]"

    def sections(self) -> dict[str, str]:
        return parse_sections(self.body)[1]

    def section(self, name: str) -> str:
        return self.sections().get(name, "")

    def set_section(self, name: str, text: str) -> None:
        preamble, sections = parse_sections(self.body)
        sections[name] = text.strip()
        self.body = render_sections(preamble, sections, SECTIONS.get(self.type, ()))

    def validate(self) -> None:
        """Raise FormatError if this entry should not be written or trusted."""
        if self.type not in TYPES:
            raise FormatError(f"unknown type {self.type!r}; expected one of {', '.join(TYPES)}")
        if not is_valid_id(self.id):
            raise FormatError(f"bad id {self.id!r}")
        if not self.id.startswith(PREFIX[self.type]):
            raise FormatError(f"id {self.id!r} does not match type {self.type!r}")
        if not self.title.strip():
            raise FormatError(f"{self.id}: empty title")
        if "\n" in self.title:
            raise FormatError(f"{self.id}: title must be one line")
        if self.status not in STATUSES[self.type]:
            allowed = ", ".join(STATUSES[self.type])
            raise FormatError(f"{self.id}: bad status {self.status!r} for {self.type}; expected one of {allowed}")
        parse_ts(self.created)
        if self.updated:
            parse_ts(self.updated)
        for ref in self.supersedes:
            if not is_valid_id(ref):
                raise FormatError(f"{self.id}: bad id in supersedes: {ref!r}")

    def to_text(self) -> str:
        meta: dict[str, str | list[str]] = {}
        for key in KEY_ORDER:
            value = getattr(self, key)
            if value or key in ("id", "type", "title", "status", "created"):
                meta[key] = list(value) if key in LIST_KEYS else value
        for key, value in self.extra.items():
            if key not in meta:
                meta[key] = value
        body = self.body.strip("\n")
        return dump_frontmatter(meta) + ("\n" + body + "\n" if body else "")

    @classmethod
    def from_text(cls, text: str) -> Entry:
        meta, body = split_document(text)
        missing = [k for k in ("id", "type", "title", "status", "created") if not meta.get(k)]
        if missing:
            raise FormatError(f"missing frontmatter keys: {', '.join(missing)}")
        known: dict[str, str | list[str]] = {}
        extra: dict[str, str | list[str]] = {}
        for key, value in meta.items():
            if key in KEY_ORDER:
                if key in LIST_KEYS and isinstance(value, str):
                    value = [value] if value else []
                elif key not in LIST_KEYS and isinstance(value, list):
                    raise FormatError(f"{key} must be a single value, not a list")
                known[key] = value
            else:
                extra[key] = value
        entry = cls(**known, extra=extra, body=body)  # type: ignore[arg-type]
        entry.validate()
        return entry
