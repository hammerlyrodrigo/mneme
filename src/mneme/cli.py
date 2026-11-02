"""Project memory that lives in a git repo beside the code."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from mneme import __version__
from mneme.brief import build_brief
from mneme.changes import ChangesError, branch_changes, render_markdown, render_text
from mneme.check import check
from mneme.init import hide_in_diffs, init_memory, write_agents, write_claude_skill
from mneme.model import (
    DEFAULT_STATUS,
    HANDOVER_SECTIONS,
    SECTIONS,
    STATUSES,
    TYPES,
    Entry,
    FormatError,
    now_utc,
    render_sections,
)
from mneme.recall import recall
from mneme.root import (
    ConfigError,
    RootNotFound,
    current_branch,
    find_root,
    load_config,
    main_branch,
)
from mneme.store import Ambiguous, Handover, NotFound, Store


class UsageError(Exception):
    pass


ERRORS = (UsageError, FormatError, ConfigError, RootNotFound, NotFound, Ambiguous,
          FileExistsError, ChangesError, ValueError)


# --- per-type fields --------------------------------------------------------

# For each type: (field, section it is written to, help). The title comes from
# TITLE_FIELD; when that field is also a section it is kept only if it says
# more than the title does.
FIELDS: dict[str, list[tuple[str, str, str]]] = {
    "decision": [
        ("title", "", "short name of the decision"),
        ("context", "Context", "the situation and forces at play"),
        ("decision", "Decision", "what was decided"),
        ("consequences", "Consequences", "what follows, good and bad"),
    ],
    "learning": [
        ("title", "", "short name of the learning"),
        ("tried", "Tried", "what was tried"),
        ("result", "Result", "what happened"),
        ("takeaway", "Takeaway", "what to do differently"),
    ],
    "question": [
        ("text", "Question", "the question"),
        ("title", "", "short title (default: first line of --text)"),
    ],
    "reminder": [
        ("action", "Action", "what to do when the trigger happens"),
        ("trigger", "Trigger", "the condition or milestone to watch for"),
        ("title", "", "short title (default: first line of --action)"),
    ],
    "concept": [
        ("term", "", "the term being defined"),
        ("definition", "Definition", "its current meaning in this project"),
        ("notes", "Notes", "usage notes, examples, what it is not"),
    ],
    "note": [
        ("title", "", "short title"),
        ("body", "", "free text"),
    ],
}
TITLE_FIELD = {"decision": "title", "learning": "title", "question": "text",
               "reminder": "action", "concept": "term", "note": "title"}
SUPERSEDABLE = ("decision", "learning", "concept", "note")
LIST_FIELDS = ("tags", "links", "supersedes")


def split_list(values: list[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    return [item.strip() for value in values for item in value.split(",") if item.strip()]


def first_line(text: str, limit: int = 100) -> str:
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return line if len(line) <= limit else line[: limit - 3].rstrip() + "..."


# --- context ----------------------------------------------------------------


@dataclass
class Context:
    cwd: Path

    @cached_property
    def root(self) -> Path:
        return find_root(self.cwd)

    @cached_property
    def store(self) -> Store:
        store = Store(self.root)
        if not store.memory_dir.is_dir():
            raise UsageError(f"no .memory/ in {self.root}; run `mneme init` first")
        return store

    @cached_property
    def config(self):
        return load_config(self.root)

    @cached_property
    def branch(self) -> str | None:
        return current_branch(self.root)

    @cached_property
    def main(self) -> str:
        return main_branch(self.root, self.config)

    def author(self, given: str | None) -> str:
        return given or os.environ.get("MNEME_AUTHOR") or self.config.default_author or "unspecified"

    def rel(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(path)

    def repo_path(self, given: str) -> str:
        """A user-supplied path as a repo-relative POSIX path."""
        absolute = (self.cwd / given).resolve()
        try:
            rel = absolute.relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return given.replace("\\", "/").strip("/")
        return "" if rel == "." else rel


def out(text: str = "") -> None:
    print(text)


# --- commands: writing ------------------------------------------------------


def cmd_init(ctx: Context, args) -> int:
    try:
        root = ctx.root
    except RootNotFound:
        root = ctx.cwd
    actions = init_memory(root)
    if args.write_agents:
        actions.append(write_agents(root))
    if args.claude:
        actions.append(write_claude_skill(root, force=args.force))
    if args.hide_in_diffs:
        actions.append(hide_in_diffs(root))
    for action in actions or [f"{root / '.memory'} already set up"]:
        out(action)
    return 0


def read_stdin_fields(entry_type: str) -> dict[str, object]:
    raw = sys.stdin.buffer.read().decode("utf-8-sig")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"--stdin: invalid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise UsageError("--stdin: expected a JSON object")
    allowed = {name for name, _, _ in FIELDS[entry_type]} | {"tags", "links", "author"}
    if entry_type in SUPERSEDABLE:
        allowed.add("supersedes")
    if entry_type == "decision":
        allowed.add("status")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise UsageError(f"--stdin: unknown field(s) for {entry_type}: {', '.join(unknown)}; "
                         f"allowed: {', '.join(sorted(allowed))}")
    for key, value in data.items():
        if key in LIST_FIELDS:
            if not (isinstance(value, str) or
                    (isinstance(value, list) and all(isinstance(v, str) for v in value))):
                raise UsageError(f"--stdin: {key} must be a string or a list of strings")
        elif not isinstance(value, str):
            raise UsageError(f"--stdin: {key} must be a string")
    return data


def cmd_new(ctx: Context, args) -> int:
    entry_type = args.entry_type
    values: dict[str, object] = {}
    if args.stdin:
        values.update(read_stdin_fields(entry_type))
    for name in [n for n, _, _ in FIELDS[entry_type]] + ["tags", "links", "supersedes", "status", "author"]:
        given = getattr(args, name, None)
        if given not in (None, []):
            values[name] = given  # flags win over --stdin

    title_field = TITLE_FIELD[entry_type]
    title_source = str(values.get(title_field) or "").strip()
    title = str(values.get("title") or "").strip() or first_line(title_source)
    if not title:
        raise UsageError(f"new {entry_type}: --{title_field} is required")

    supersedes = split_list(values.get("supersedes"))  # type: ignore[arg-type]
    store = ctx.store
    entries = store.load().entries
    replaced = []
    for ref in supersedes:
        old = store.find(ref, entries)
        if old.type != entry_type:
            raise UsageError(f"{old.id} is a {old.type}; a {entry_type} can only supersede a {entry_type}")
        replaced.append(old)

    preamble = ""
    sections: dict[str, str] = {}
    for name, section, _ in FIELDS[entry_type]:
        text = str(values.get(name) or "").strip()
        if not text:
            continue
        if entry_type == "note" and name == "body":
            preamble = text
        elif section and not (name == title_field and text == title):
            sections[section] = text

    entry = Entry(
        id="",
        type=entry_type,
        title=title,
        status=str(values.get("status") or DEFAULT_STATUS[entry_type]),
        created=now_utc(),
        author=ctx.author(values.get("author")),  # type: ignore[arg-type]
        branch=ctx.branch or "",
        tags=split_list(values.get("tags")),  # type: ignore[arg-type]
        links=[link.replace("\\", "/") for link in split_list(values.get("links"))],  # type: ignore[arg-type]
        supersedes=[old.id for old in replaced],
        body=render_sections(preamble, sections, SECTIONS[entry_type]),
    )
    store.create(entry)
    out(f"Created {entry.id}  {ctx.rel(entry.path)}")
    for old in replaced:
        old.status = "superseded"
        store.save(old)
        out(f"Marked {old.id} superseded")
    return 0


def cmd_set(ctx: Context, args) -> int:
    entry = ctx.store.find(args.id)
    if args.status not in STATUSES[entry.type]:
        raise UsageError(f"{entry.id}: status must be one of {', '.join(STATUSES[entry.type])}")
    entry.status = args.status
    ctx.store.save(entry)
    out(f"{entry.id} is now {entry.status}")
    return 0


def cmd_resolve(ctx: Context, args) -> int:
    store = ctx.store
    entries = store.load().entries
    entry = store.find(args.id, entries)
    if entry.type != "question":
        raise UsageError(f"{entry.id} is a {entry.type}; only questions are resolved")
    if args.decision:
        entry.resolved_by = store.find(args.decision, entries).id
    entry.status = "resolved"
    entry.set_section("Answer", args.answer)
    store.save(entry)
    out(f"Resolved {entry.id}" + (f" by {entry.resolved_by}" if entry.resolved_by else ""))
    return 0


def cmd_done(ctx: Context, args) -> int:
    entry = ctx.store.find(args.id)
    if entry.type != "reminder":
        raise UsageError(f"{entry.id} is a {entry.type}; only reminders are done")
    entry.status = "done"
    if args.note:
        entry.set_section("Note", args.note)
    ctx.store.save(entry)
    out(f"Marked {entry.id} done")
    return 0


def cmd_supersede(ctx: Context, args) -> int:
    store = ctx.store
    entries = store.load().entries
    old, new = store.find(args.old, entries), store.find(args.by, entries)
    if old.id == new.id:
        raise UsageError("an entry cannot supersede itself")
    if old.type != new.type:
        raise UsageError(f"{new.id} is a {new.type} and {old.id} is a {old.type}; types must match")
    if old.type not in SUPERSEDABLE:
        raise UsageError(f"a {old.type} cannot be superseded")
    if old.id not in new.supersedes:
        new.supersedes.append(old.id)
        store.save(new)
    old.status = "superseded"
    store.save(old)
    out(f"{old.id} superseded by {new.id}")
    return 0


def cmd_handover(ctx: Context, args) -> int:
    branch = args.branch or ctx.branch
    if not branch:
        raise UsageError("HEAD is detached; pass --branch")
    sections = {"Summary": args.summary, "Done": args.done or "", "Next": args.next or "",
                "Blockers": args.blockers or ""}
    handover = Handover(
        branch=branch,
        updated=now_utc(),
        author=ctx.author(args.author),
        body=render_sections("", {k: v.strip() for k, v in sections.items()}, HANDOVER_SECTIONS),
    )
    path = ctx.store.write_handover(handover)
    out(f"Wrote handover for {branch}  {ctx.rel(path)}")
    return 0


# --- commands: reading ------------------------------------------------------


def cmd_brief(ctx: Context, args) -> int:
    sys.stdout.write(build_brief(ctx.store, ctx.branch, ctx.main, ctx.config.spec_dirs))
    return 0


def cmd_recall(ctx: Context, args) -> int:
    query = " ".join(args.query)
    path = ctx.repo_path(args.path) if args.path is not None else None
    if not query and path is None:
        raise UsageError("recall needs words to search for, --path, or both")
    entries = ctx.store.load().entries
    found = recall(entries, query, path, include_inactive=args.all, types=tuple(args.type or ()))
    if not found:
        out("Nothing found." + ("" if args.all else " (--all includes settled and superseded entries)"))
        return 0
    for entry in found[: args.limit]:
        out(f"{entry.type:<9} {entry.oneline()}")
    if len(found) > args.limit:
        out(f"(+{len(found) - args.limit} more; --limit to see them)")
    return 0


def cmd_list(ctx: Context, args) -> int:
    entries = [e for e in ctx.store.load().entries if e.type == args.entry_type]
    if args.status:
        entries = [e for e in entries if e.status == args.status]
    elif not args.all:
        entries = [e for e in entries if e.active]
    entries.reverse()
    for entry in entries[: args.limit] if args.limit else entries:
        out(f"{entry.created[:10]}  {entry.oneline()}")
    return 0


def cmd_show(ctx: Context, args) -> int:
    store = ctx.store
    entries = store.load().entries
    entry = store.find(args.id, entries)
    newer = [e.id for e in entries if entry.id in e.supersedes]
    out(f"# {ctx.rel(entry.path)}")
    if newer:
        out(f"# superseded by {', '.join(newer)}")
    sys.stdout.write(entry.to_text())
    return 0


def cmd_changes(ctx: Context, args) -> int:
    base = args.base or ctx.main
    if not args.base and ctx.branch == base:
        raise UsageError(f"on {base} already; pass --base <branch> to compare against")
    changes = branch_changes(ctx.store, base)
    if args.markdown:
        sys.stdout.write(render_markdown(changes))
    else:
        out(render_text(changes, ctx.root))
    return 0


def cmd_check(ctx: Context, args) -> int:
    problems, count = check(ctx.store, ctx.branch, ctx.main)
    for problem in problems:
        out(f"{ctx.rel(problem.path)}: {problem.message}")
    if problems:
        out(f"{len(problems)} problem{'s' if len(problems) > 1 else ''} in {count} entries")
        return 1
    out(f"OK: {count} entries, no problems")
    return 0


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mneme", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mneme {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def command(name: str, func, help: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help, description=help)
        p.set_defaults(func=func)
        return p

    p = command("init", cmd_init, "create .memory/ and config.toml")
    p.add_argument("--write-agents", action="store_true", help="add or refresh the Mneme block in AGENTS.md")
    p.add_argument("--claude", action="store_true", help="write a Claude Code skill to .claude/skills/mneme/")
    p.add_argument("--hide-in-diffs", action="store_true",
                   help="mark .memory/ as linguist-generated so GitHub collapses it in PR diffs")
    p.add_argument("--force", action="store_true", help="replace an existing, edited Claude skill")

    p = command("new", cmd_new, "record a new entry")
    types = p.add_subparsers(dest="entry_type", metavar="<type>", required=True)
    for entry_type in TYPES:
        t = types.add_parser(entry_type, help=f"record a {entry_type}")
        for name, _, help_text in FIELDS[entry_type]:
            t.add_argument(f"--{name}", help=help_text)
        if entry_type == "decision":
            t.add_argument("--status", choices=["proposed", "accepted"], help="default: accepted")
        if entry_type in SUPERSEDABLE:
            t.add_argument("--supersedes", action="append", metavar="ID[,ID]",
                           help="entries this one replaces; they are marked superseded")
        t.add_argument("--tags", action="append", metavar="TAG[,TAG]")
        t.add_argument("--links", action="append", metavar="PATH[,PATH]",
                       help="code or spec paths this entry is about (file, dir/, spec.md#anchor)")
        t.add_argument("--author", help="who recorded it (default: MNEME_AUTHOR or config)")
        t.add_argument("--stdin", action="store_true", help="read the same fields as a JSON object")

    p = command("set", cmd_set, "change an entry's status")
    p.add_argument("id")
    p.add_argument("--status", required=True)

    p = command("resolve", cmd_resolve, "answer an open question")
    p.add_argument("id")
    p.add_argument("--answer", required=True)
    p.add_argument("--decision", metavar="ID", help="the decision that settled it")

    p = command("done", cmd_done, "mark a reminder done")
    p.add_argument("id")
    p.add_argument("--note")

    p = command("supersede", cmd_supersede, "mark an entry as replaced by a newer one")
    p.add_argument("old")
    p.add_argument("--by", required=True, metavar="ID")

    p = command("handover", cmd_handover, "write this branch's handover (overwrites the last one)")
    p.add_argument("--summary", required=True)
    p.add_argument("--done")
    p.add_argument("--next")
    p.add_argument("--blockers")
    p.add_argument("--branch", help="default: the current branch")
    p.add_argument("--author")

    command("brief", cmd_brief, "the session-start view: handover, open loops, recent decisions")

    p = command("recall", cmd_recall, "find entries by words, by path, or both; best first")
    p.add_argument("query", nargs="*")
    p.add_argument("--path", help="entries linked to this file or directory")
    p.add_argument("--type", action="append", choices=TYPES)
    p.add_argument("--all", action="store_true", help="include settled and superseded entries")
    p.add_argument("--limit", type=int, default=8)

    p = command("list", cmd_list, "list entries of one type, newest first")
    p.add_argument("entry_type", choices=TYPES)
    p.add_argument("--status")
    p.add_argument("--all", action="store_true", help="include settled and superseded entries")
    p.add_argument("--limit", type=int)

    p = command("show", cmd_show, "print one entry in full")
    p.add_argument("id", help="an id or unique id prefix")

    p = command("changes", cmd_changes, "entries added or changed on this branch")
    p.add_argument("--base", help="branch to compare against (default: the main branch)")
    p.add_argument("--markdown", action="store_true", help="print a block for a PR description")

    command("check", cmd_check, "report problems in .memory/; exit 1 if any")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        return args.func(Context(Path.cwd()), args)
    except ERRORS as exc:
        print(f"mneme: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
