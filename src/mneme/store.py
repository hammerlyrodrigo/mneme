"""Reading and writing entry files under `.memory/`."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from mneme.model import (
    TYPES,
    Entry,
    FormatError,
    branch_filename,
    dump_frontmatter,
    new_id,
    now_utc,
    split_document,
)
from mneme.root import MEMORY_DIRNAME

HANDOVER_DIRNAME = "handover"


class NotFound(LookupError):
    pass


class Ambiguous(LookupError):
    pass


@dataclass
class Problem:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class Loaded:
    entries: list[Entry] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)


@dataclass
class Handover:
    branch: str
    updated: str
    author: str = ""
    body: str = ""
    path: Path | None = None


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.memory_dir = root / MEMORY_DIRNAME

    def type_dir(self, entry_type: str) -> Path:
        return self.memory_dir / f"{entry_type}s"

    def entry_files(self) -> list[Path]:
        files: list[Path] = []
        for entry_type in TYPES:
            directory = self.type_dir(entry_type)
            if directory.is_dir():
                files += sorted(p for p in directory.glob("*.md") if not p.name.startswith("."))
        return files

    def load(self) -> Loaded:
        """Read every entry. Unreadable or invalid files become problems, not errors."""
        loaded = Loaded()
        for path in self.entry_files():
            try:
                entry = Entry.from_text(path.read_text(encoding="utf-8"))
            except (FormatError, UnicodeDecodeError) as exc:
                loaded.problems.append(Problem(path, str(exc)))
                continue
            expected_dir = self.type_dir(entry.type)
            if path.parent != expected_dir:
                loaded.problems.append(
                    Problem(path, f"type {entry.type!r} belongs in {expected_dir.name}/")
                )
            entry.path = path
            loaded.entries.append(entry)
        loaded.entries.sort(key=lambda e: (e.created_dt, e.id))
        return loaded

    def find(self, prefix: str, entries: list[Entry] | None = None) -> Entry:
        """Look an entry up by a case-insensitive ID prefix."""
        if entries is None:
            entries = self.load().entries
        needle = prefix.strip().lower()
        if not needle:
            raise NotFound("empty id")
        exact = [e for e in entries if e.id.lower() == needle]
        matches = exact or [e for e in entries if e.id.lower().startswith(needle)]
        if not matches:
            raise NotFound(f"no entry with id {prefix!r}")
        if len(matches) > 1:
            ids = ", ".join(sorted({e.id for e in matches}))
            raise Ambiguous(f"{prefix!r} matches more than one entry: {ids}")
        return matches[0]

    def _id_taken(self, candidate: str, known: set[str]) -> bool:
        if candidate in known:
            return True
        # Also count files that failed to parse, judged by their filename.
        return any(
            p.name == f"{candidate}.md" or p.name.startswith(f"{candidate}-")
            for p in self.entry_files()
        )

    def create(self, entry: Entry) -> Entry:
        """Assign an unused ID if the entry has none, validate it, and write it.

        Raises FormatError before touching disk if the entry is invalid, and
        FileExistsError rather than overwriting an existing entry.
        """
        known = {e.id for e in self.load().entries}
        if not entry.id:
            taken = set(known)
            while True:
                entry.id = new_id(entry.type, taken)
                if not self._id_taken(entry.id, known):
                    break
                taken.add(entry.id)
        elif self._id_taken(entry.id, known):
            raise FileExistsError(f"id {entry.id} is already used")
        entry.validate()
        path = self.type_dir(entry.type) / entry.filename()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(entry.to_text())
        entry.path = path
        return entry

    def save(self, entry: Entry) -> None:
        """Rewrite an existing entry in place, keeping its filename."""
        if entry.path is None:
            raise ValueError(f"{entry.id} was not loaded from disk; use create()")
        entry.updated = now_utc()
        entry.validate()
        atomic_write(entry.path, entry.to_text())

    # --- handovers ----------------------------------------------------------

    def handover_dir(self) -> Path:
        return self.memory_dir / HANDOVER_DIRNAME

    def handover_path(self, branch: str) -> Path:
        return self.handover_dir() / branch_filename(branch)

    def read_handover(self, path: Path) -> Handover:
        meta, body = split_document(path.read_text(encoding="utf-8"))
        branch, updated, author = meta.get("branch"), meta.get("updated", ""), meta.get("author", "")
        if not isinstance(branch, str) or not branch:
            raise FormatError("handover is missing 'branch'")
        if not isinstance(updated, str) or not isinstance(author, str):
            raise FormatError("handover 'updated' and 'author' must be single values")
        return Handover(branch=branch, updated=updated, author=author, body=body, path=path)

    def load_handover(self, branch: str) -> Handover | None:
        path = self.handover_path(branch)
        return self.read_handover(path) if path.is_file() else None

    def handover_files(self) -> list[Path]:
        directory = self.handover_dir()
        return sorted(directory.glob("*.md")) if directory.is_dir() else []

    def write_handover(self, handover: Handover) -> Path:
        meta: dict[str, str | list[str]] = {"branch": handover.branch, "updated": handover.updated}
        if handover.author:
            meta["author"] = handover.author
        body = handover.body.strip("\n")
        path = self.handover_path(handover.branch)
        atomic_write(path, dump_frontmatter(meta) + ("\n" + body + "\n" if body else ""))
        handover.path = path
        return path
