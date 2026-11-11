"""Project memory that lives in a git repo beside the code."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
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
from mneme.dream import DREAM_TYPES, build_dream
from mneme.migrate import MigrateError, plan_migration
from mneme.recall import links_path, recall
from mneme.root import (
    ConfigError,
    RootNotFound,
    current_branch,
    find_root,
    git,
    load_config,
    main_branch,
)
from mneme.store import Ambiguous, Handover, NotFound, Store


class UsageError(Exception):
    pass


ERRORS = (UsageError, FormatError, ConfigError, RootNotFound, NotFound, Ambiguous,
          FileExistsError, ChangesError, MigrateError, ValueError)


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
TYPE_HELP = {
    "decision": "a non-obvious choice and why",
    "learning": "something tried and what it taught, especially a failed approach",
    "question": "something deliberately left open",
    "reminder": "something decided but deferred until a trigger",
    "concept": "what a project term means",
    "note": "anything else worth keeping",
}
TITLE_FIELD = {"decision": "title", "learning": "title", "question": "text",
               "reminder": "action", "concept": "term", "note": "title"}
SUPERSEDABLE = ("decision", "learning", "concept", "note")
LIST_FIELDS = ("tags", "keywords", "links", "supersedes")
# Fields every type takes, besides its own.
COMMON_FIELDS = ("summary", "tags", "keywords", "links", "author", "agent")
# Longer sections still work, but short ones recall and read better.
SECTION_SOFT_LIMIT = 600
# Characters of an entry's gist printed under a recall hit.
GIST_WIDTH = 140
# Environment variables that tell which agent is running, checked after MNEME_AGENT.
AGENT_ENV = (("CLAUDECODE", "claude-code"),)


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
        return (given or os.environ.get("MNEME_AUTHOR") or self.config.default_author
                or self.git_user or "unspecified")

    @cached_property
    def git_user(self) -> str:
        try:
            return git(["config", "user.name"], self.root) or ""
        except RootNotFound:
            return ""

    def agent(self, given: str | None) -> str:
        if given or os.environ.get("MNEME_AGENT"):
            return given or os.environ["MNEME_AGENT"]
        return next((name for var, name in AGENT_ENV if os.environ.get(var)), "")

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


def warn(text: str) -> None:
    print(f"mneme: note: {text}", file=sys.stderr)


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
    allowed = {name for name, _, _ in FIELDS[entry_type]} | set(COMMON_FIELDS)
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
    for name in [n for n, _, _ in FIELDS[entry_type]] + [*COMMON_FIELDS, "supersedes", "status"]:
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
        summary=str(values.get("summary") or "").strip(),
        author=ctx.author(values.get("author")),  # type: ignore[arg-type]
        agent=ctx.agent(values.get("agent")),  # type: ignore[arg-type]
        branch=ctx.branch or "",
        tags=split_list(values.get("tags")),  # type: ignore[arg-type]
        keywords=split_list(values.get("keywords")),  # type: ignore[arg-type]
        links=[link.replace("\\", "/") for link in split_list(values.get("links"))],  # type: ignore[arg-type]
        supersedes=[old.id for old in replaced],
        body=render_sections(preamble, sections, SECTIONS[entry_type]),
    )
    store.create(entry)
    out(f"Created {entry.id}  {ctx.rel(entry.path)}")
    for name, text in [("body", preamble), *sections.items()]:
        if len(text) > SECTION_SOFT_LIMIT:
            warn(f"{name} is {len(text)} characters; short entries recall better "
                 f"(aim for under {SECTION_SOFT_LIMIT})")
    for old in replaced:
        old.status = "superseded"
        store.save(old)
        out(f"Marked {old.id} superseded")
    return 0


def cmd_set(ctx: Context, args) -> int:
    if args.status is None and args.summary is None and args.keywords is None:
        raise UsageError("set needs --status, --summary or --keywords")
    entry = ctx.store.find(args.id)
    changed = []
    if args.status is not None:
        if args.status not in STATUSES[entry.type]:
            raise UsageError(f"{entry.id}: status must be one of {', '.join(STATUSES[entry.type])}")
        entry.status = args.status
        changed.append(f"status {entry.status}")
    if args.summary is not None:
        entry.summary = args.summary.strip()
        changed.append("summary")
    if args.keywords is not None:
        entry.keywords = split_list(args.keywords)
        changed.append("keywords")
    ctx.store.save(entry)
    out(f"{entry.id}: set {', '.join(changed)}")
    if entry.active and ctx.store.is_archived(entry):
        warn(f"{entry.id} is archived; run `mneme archive --restore {entry.id}` to bring it back")
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


def cmd_archive(ctx: Context, args) -> int:
    store = ctx.store
    entries = store.load().entries
    if args.inactive and (args.ids or args.restore):
        raise UsageError("--inactive archives every inactive entry; don't combine it with ids or --restore")
    if args.inactive:
        chosen = [e for e in entries if not e.active and not store.is_archived(e)]
    elif args.ids:
        chosen = [store.find(ref, entries) for ref in args.ids]
    else:
        raise UsageError("archive needs ids or --inactive")
    # Check every entry before moving any, so a bad id moves nothing.
    for entry in chosen:
        if args.restore and not store.is_archived(entry):
            raise UsageError(f"{entry.id} is not archived")
        if not args.restore:
            if store.is_archived(entry):
                raise UsageError(f"{entry.id} is already archived")
            if entry.active:
                raise UsageError(f"{entry.id} is {entry.status}; only settled or replaced entries are archived")
    for entry in chosen:
        path = store.move(entry, archived=not args.restore)
        out(f"{'Restored' if args.restore else 'Archived'} {entry.id}  {ctx.rel(path)}")
    if not chosen:
        out("Nothing to archive.")
    return 0


def cmd_migrate(ctx: Context, args) -> int:
    store = ctx.store
    plan = plan_migration(Path(args.from_path))
    for note in plan.notes:
        out(f"note: {note}")
    if plan.problems:
        for problem in plan.problems:
            out(f"problem: {problem}")
        out(f"Nothing written: {len(plan.problems)} record(s) can't be migrated.")
        return 1

    known = {e.id for e in store.load().entries}
    new = [e for e in plan.entries if e.id not in known]
    if len(new) < len(plan.entries):
        out(f"note: {len(plan.entries) - len(new)} entries already exist here and are skipped")
    counts = Counter((e.type, e.status) for e in new)
    verb = "Would migrate" if args.dry_run else "Migrated"
    out(f"{verb} {len(new)} entries:")
    for (entry_type, status), n in sorted(counts.items()):
        out(f"  {n:>4} {entry_type} {status}")

    handover_note = ""
    if plan.handover:
        plan.handover.branch = ctx.main
        if store.load_handover(ctx.main):
            handover_note = f"kept the existing {ctx.main} handover; the log's newest one was not imported"
        else:
            handover_note = f"newest handover becomes the {ctx.main} handover"
        if plan.handovers_dropped:
            handover_note += f" ({plan.handovers_dropped} older ones are left in the log's git history)"
        out(f"note: {handover_note}")
    if args.dry_run:
        return 0

    for entry in new:
        store.create(entry, known)
        known.add(entry.id)
    if plan.handover and not store.load_handover(ctx.main):
        store.write_handover(plan.handover)
    out("Run `mneme check`, then commit .memory/ and remove the old log in the same commit.")
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
        agent=ctx.agent(args.agent),
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
    result = recall(entries, query, path, include_inactive=args.all, types=tuple(args.type or ()))
    hits = result.hits
    if not hits:
        out("Nothing found. Try other words" + ("." if args.all else ", or --all for settled entries."))
        return 0
    if result.partial:
        out("No entry has every word. Closest partial matches:")
    for hit in hits[: args.limit]:
        entry = hit.entry
        line = f"{entry.id}  {entry.title}"
        if entry.status != DEFAULT_STATUS[entry.type]:
            line += f"  [{entry.status}]"
        if hit.missing:
            line += f"  (no: {', '.join(hit.missing)})"
        out(line)
        if gist := entry.gist():
            out(f"    {first_line(gist, GIST_WIDTH)}")
    if len(hits) > args.limit:
        out(f"(+{len(hits) - args.limit} more; --limit to see them)")
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
    # Look every id up first, so a typo prints nothing rather than half the answer.
    found = [store.find(ref, entries) for ref in args.ids]
    for n, entry in enumerate(found):
        newer = [e.id for e in entries if entry.id in e.supersedes]
        if n:
            out()
        if args.raw:
            out(f"# {ctx.rel(entry.path)}")
            if newer:
                out(f"# superseded by {', '.join(newer)}")
            sys.stdout.write(entry.to_text())
            continue
        out(f"# {entry.oneline()}")
        for label, value in (("Summary", entry.summary), ("Links", ", ".join(entry.links)),
                             ("Supersedes", ", ".join(entry.supersedes)),
                             ("Superseded by", ", ".join(newer)), ("Resolved by", entry.resolved_by)):
            if value:
                out(f"{label}: {value}")
        body = entry.body.strip("\n")
        if body:
            out()
            out(body)
    return 0


def usage_lines() -> list[str]:
    """The commands `dream` may tell an agent to run, with their real flags."""
    lines = []
    for entry_type in DREAM_TYPES:
        flags = " ".join(f"--{name} ..." for name, _, _ in FIELDS[entry_type])
        lines.append(f"mneme new {entry_type} {flags} --summary ... --keywords A,B "
                     f"--tags A,B --links PATH,PATH --supersedes ID,ID")
    lines += [
        "mneme set <id> [--status STATUS] [--summary ...] [--keywords A,B]",
        "mneme supersede <old-id> --by <new-id>",
        "mneme archive <id> [<id>...]",
        "mneme show <id> [<id>...]",
    ]
    return lines


def cmd_dream(ctx: Context, args) -> int:
    entries = ctx.store.load().entries
    if args.tag:
        tag = args.tag.lower()
        entries = [e for e in entries if tag in {t.lower() for t in [*e.tags, *e.keywords]}]
    if args.path is not None:
        path = ctx.repo_path(args.path)
        entries = [e for e in entries if links_path(e, path)]
    sys.stdout.write(build_dream(entries, usage_lines(), args.limit))
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
    p.epilog = ("Give every entry --summary (one line stating the outcome), --keywords (search words "
                "the text doesn't use) and --links (the code or spec it is about). "
                "`mneme new <type> --help` lists a type's fields.")
    types = p.add_subparsers(dest="entry_type", metavar="<type>", required=True)
    for entry_type in TYPES:
        t = types.add_parser(entry_type, help=TYPE_HELP[entry_type],
                             description=f"Record a {entry_type}: {TYPE_HELP[entry_type]}.")
        for name, _, help_text in FIELDS[entry_type]:
            t.add_argument(f"--{name}", help=help_text)
        if entry_type == "decision":
            t.add_argument("--status", choices=["proposed", "accepted"], help="default: accepted")
        if entry_type in SUPERSEDABLE:
            t.add_argument("--supersedes", action="append", metavar="ID[,ID]",
                           help="entries this one replaces; they are marked superseded")
        t.add_argument("--summary", help="one line stating the outcome; recall prints it")
        t.add_argument("--tags", action="append", metavar="TAG[,TAG]")
        t.add_argument("--keywords", action="append", metavar="WORD[,WORD]",
                       help="extra search words, such as synonyms the text doesn't use")
        t.add_argument("--links", action="append", metavar="PATH[,PATH]",
                       help="code or spec paths this entry is about (file, dir/, spec.md#anchor)")
        t.add_argument("--author", help="who recorded it (default: MNEME_AUTHOR, config, git user.name)")
        t.add_argument("--agent", help="the agent recording it for the author (default: MNEME_AGENT or detected)")
        t.add_argument("--stdin", action="store_true", help="read the same fields as a JSON object")

    p = command("set", cmd_set, "change an entry's status, summary or keywords")
    p.add_argument("id")
    p.add_argument("--status")
    p.add_argument("--summary", help="replace the one-line summary")
    p.add_argument("--keywords", action="append", metavar="WORD[,WORD]", help="replace the keywords")

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

    p = command("archive", cmd_archive,
                "move settled or replaced entries to .memory/archive/; show and --all still find them")
    p.add_argument("ids", nargs="*", metavar="id")
    p.add_argument("--inactive", action="store_true", help="archive every inactive entry")
    p.add_argument("--restore", action="store_true", help="move archived entries back")

    p = command("handover", cmd_handover, "write this branch's handover (overwrites the last one)")
    p.add_argument("--summary", required=True)
    p.add_argument("--done")
    p.add_argument("--next")
    p.add_argument("--blockers")
    p.add_argument("--branch", help="default: the current branch")
    p.add_argument("--author")
    p.add_argument("--agent")

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

    p = command("show", cmd_show, "print entries: title, status, links and body")
    p.add_argument("ids", nargs="+", metavar="id", help="ids or unique id prefixes")
    p.add_argument("--raw", action="store_true", help="print the whole file, with all frontmatter")

    p = command("migrate", cmd_migrate, "import a mneme v0 log (.memory/log/entries.jsonl)")
    p.add_argument("--from", dest="from_path", required=True, metavar="ENTRIES_JSONL")
    p.add_argument("--dry-run", action="store_true", help="report what would be written; write nothing")

    p = command("dream", cmd_dream,
                "print a prompt asking an agent to consolidate memory; changes nothing itself")
    p.add_argument("--tag", help="only entries with this tag or keyword")
    p.add_argument("--path", help="only entries linked to this file or directory")
    p.add_argument("--limit", type=int, default=80, help="newest entries to include (0: all)")

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
