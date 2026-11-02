# Handover

_Written 2026-11-02 by claude, at the end of the session in `../demiurge` that
produced this project's plan. Nothing is built yet. Once `mneme handover`
exists, move this content to `.memory/handover/main.md` and delete this file;
that's the first real use of the tool on itself._

## What Mneme is

A small, dependency-free CLI that gives a git repo **project memory that lives
beside the code**, for AI-assisted or agent-driven development, including
spec-driven development (SDD). It records what spec tools like Spec Kit,
OpenSpec, Kiro or BMAD don't keep across features and sessions:

| Type | Meaning |
|---|---|
| decision | A non-obvious choice and why, ADR/MADR-style, with `supersedes` chains |
| learning | Something tried, what happened, the takeaway; failed approaches especially |
| question | Deliberately left undecided |
| reminder | Already decided, but deferred until some trigger |
| concept | A term's current definition (glossary), with version history in git |
| note | Anything else worth keeping |
| handover | Per-branch checkpoint so the next session (human or agent) starts cheaply |

**Out of scope:** tasks/kanban (the spec tool's `tasks.md`, or Beads), specs
themselves, vector search, LLM consolidation that changes entries on its own,
configurable entry types or plugins.

## Where it came from

[legacy/mneme_v0.py](legacy/mneme_v0.py) is an unchanged copy of
`../demiurge/scripts/memory.py` at Demiurge commit `d8d3cb8`, renamed. It's a
reference to port from, not a starting point to edit:

- Its internal text still says "Demiurge" and `scripts/memory.py`.
- Running it from here would create `.memory/` in this repo, because it finds
  the root from the script's own location.

About 2,000 lines, of which about 650 are inline HTML for a viewer. It stores
entries in `.memory/log/entries.jsonl` (append-only creates + "patch" lines
folded on load), keeps a SQLite index in `.memory/index.db`, generates
Markdown views, and relies on `merge=union`. Reuse the entry types, CLI flags,
`--stdin` JSON input and the `serve` viewer. Don't reuse its storage layer.
Delete `legacy/` once the viewer is ported and `migrate` is verified.

Problems found in review, all of which the new design must avoid:

1. A single shared JSONL + `merge=union`: GitHub, GitLab and Bitbucket web
   merges ignore merge drivers, so every PR touching the log shows a conflict.
2. Status patches resolve as last-in-file wins, so a real disagreement
   between two branches is decided arbitrarily and silently.
3. Patches to unknown IDs are silently dropped (`resolve Q0099` says "Resolved").
4. IDs are 4 random hex characters per type per day, with no collision
   check; on a collision the later entry silently replaces the earlier one.
   (The docstring wrongly calls them deterministic.)
5. `--stdin` skips validation and the entry is appended before rendering, so
   one bad entry crashes every later command.
6. `current_branch()` is called once per entry on load (`setdefault` evaluates
   it eagerly), which took 1.4s for 69 entries, and it labels old entries with
   whatever branch is checked out.
7. Generated views are in `.gitignore` but still tracked: dirty trees after
   checkout, a stale `handover.md` on fresh clones, inconsistent decision files.
8. `gc` depends on the machine: it judges branches dead by *local* branches,
   marks links with `#anchor` as stale, and stale entries drop out of search.
9. `dream` clustering is inverted (subset entries start new clusters), and
   the prompt references a schema that doesn't exist.
10. Timestamps use local UTC offsets but are sorted as strings, so ordering
    is wrong across time zones.
11. `init` rewrites AGENTS.md and **drops everything after the managed
    block**, and installs git hooks into the host repo.
12. Hard-coded `ROOT = script/..`, `main`/`master`, and Demiurge-specific text.

## Settled design

- **One Markdown file per entry, with frontmatter**, under `.memory/<type>s/`,
  for example `.memory/decisions/D-7f3a2c-use-sqlite-saves.md`:
  - New entries from different branches never conflict, even in GitHub's web merge.
  - A status is just a frontmatter line, so git does a normal 3-way merge
    and a real disagreement shows up as a conflict.
  - Entry history comes from `git log -p <file>`.
  - Agents that can't run the CLI can still read and write entries by hand.
- **IDs:** `<P>-<6 hex from secrets>`, checked unique at creation. Filename
  is `<id>-<slug>.md`, and lookups go by ID prefix so renaming a slug doesn't
  break links.
- **Handover:** one file per branch, `.memory/handover/<branch>.md` (with `/`
  turned into `--`), overwritten each time; git keeps the history. On the main
  branch, any other branch's handover file means that branch was merged and
  the file should be folded in. That check gives the same answer on every
  machine.
- **Nothing is generated or committed besides entries.** `mneme brief` prints
  the session-start view on demand: this branch's handover, the main
  branch's handover, open questions (plus spec clarification markers such as
  `[NEEDS CLARIFICATION: …]`), pending reminders and recent decisions.
- **No SQLite, git hooks, merge driver or `.gitignore` management.** Search
  is an in-memory scan, which is enough for thousands of small files.
- **`check`** reports problems and never changes entries; it exits non-zero
  for CI or pre-commit. It checks frontmatter, unique IDs, valid statuses,
  `supersedes` and `links` targets (stripping `#anchor`, then verifying the
  heading exists), and leftover handovers from merged branches.
- **`init`** only creates `.memory/` and `config.toml`. `--write-agents` adds
  a marked block to AGENTS.md and must keep the text around it.
  `--claude` writes a Claude Code skill.
- **Root discovery:** `git rev-parse --show-toplevel`, otherwise walk up to
  the nearest `.memory/`. The tool is installed once (`uv tool install`), not
  copied into each repo.
- **Config** in `.memory/config.toml`: `main_branch` (fallback `origin/HEAD`),
  `spec_dirs`, `default_author`. The entry types are fixed and not configurable.
- **Timestamps** in UTC, written with a `Z` suffix.
- **SDD support:**
  - `links` can point at spec sections (`specs/003-auth/spec.md#fr-2`).
  - `mneme refs <path>` lists every entry that points at a spec.
  - `brief` picks up clarification markers in `spec_dirs`.
  - Agent rule: a decision made inside a feature's plan becomes a `decision`
    entry when it outlives the feature.
- **`dream`** only prints a consolidation prompt (schema included). Acting on
  it means new entries with `supersedes:`, reviewed in a PR.

### Planned layout

```
pyproject.toml          # no dependencies, console script `mneme`
src/mneme/
  __init__.py  cli.py  root.py  model.py  store.py
  brief.py  check.py  search.py  migrate.py
  viewer/server.py  viewer/index.html   # ported from legacy/mneme_v0.py's `serve`
  templates/            # entry templates, AGENTS.md snippet, Claude skill
tests/
legacy/mneme_v0.py      # reference only; delete after porting
README.md  LICENSE  CHANGELOG.md
.github/workflows/ci.yml   # Windows, macOS, Linux × supported Pythons
```

### Commands

`init [--write-agents] [--claude]` · `new <type>` (flags or `--stdin` JSON) ·
`set <id> --status` · `resolve <id> --answer [--decision]` · `done <id>` ·
`supersede <old> --by <new>` · `handover --summary --done --next [--blockers]`
· `brief` · `search` · `list <type> [--status]` · `show <id>` · `refs <path>` ·
`check` · `migrate --from <entries.jsonl>` · `serve [--open]` · `dream`

## Decisions made

- Name: **Mneme**. Folder, import package and command are all `mneme`.
  `mneme` on PyPI is taken (an abandoned 2014 package), so publish under
  another distribution name such as `mneme-cli` if PyPI is ever needed.
  v0.1 installs from git.
- It's a separate repo in this folder, a sibling of `../demiurge`.
- The storage model above (one file per entry, nothing generated).
- Settled with the user on 2026-11-02:
  - **Python 3.11+**, using `tomllib` for `config.toml`. Python 3.12.10 and
    3.11.14 (via uv) are installed on this machine; `python` on PATH is still 3.10.
  - **Frontmatter is a documented YAML subset** between `---` lines: plain
    scalars and inline `[a, b]` lists only, with our own small parser.
  - **No viewer in v0.1.** Ship the CLI and `migrate` first, port `serve` in
    v0.2, and keep `legacy/` until then.
  - **MIT license, with a GitHub repo.** Running `gh` needs `gh auth login`
    first, and we still have to confirm public or private before creating it.
- Git on this machine has `core.autocrlf` on. The repo uses `.gitattributes`
  to keep LF, and the parser must accept CRLF entry files.

## Next steps

1. ~~Settle the open decisions~~ (done).
2. ~~`git init -b main`, the baseline commit and the scaffold~~ (done).
   Still to do: create the GitHub repo. That needs `gh auth login` and a
   public or private choice from the user.
3. ~~`model.py`, `store.py`, `root.py` with tests~~ (done; 76 tests pass on
   3.11 and 3.12). Choices made while building them:
   - Frontmatter keys in write order: `id type title status created updated
     author branch tags links supersedes resolved_by`. Unknown keys are kept
     on round-trip. Every value is a string; nothing is coerced.
   - Type-specific fields are `## Section`s in the body (see `SECTIONS` in
     `model.py`). A note has a free body.
   - `superseded_by` is never stored. Derive it from the newer entry's
     `supersedes`, so a supersede writes the new file and flips the old one's
     status, and nothing else.
   - Statuses per type are in `model.STATUSES`. Legacy `consolidated`,
     `obsolete` and `stale` become `superseded` or `archived` in `migrate`.
   - `save()` stamps `updated`, so editing the same entry on two branches
     always conflicts on that line. That's intended: two edits to one entry
     deserve a human look.
   - The handover file has frontmatter `branch`, `updated` and `author`, and a
     body with `HANDOVER_SECTIONS`. It is not an `Entry` and has no ID.
   - A conflicted entry file (git conflict markers) loads as a problem, not a crash.
4. Build the commands (`cli.py`), then `check`, `brief`, `refs`. Test that
   `init --write-agents` is idempotent and keeps the rest of AGENTS.md.
   Author resolution: `--author`, then `MNEME_AUTHOR`, then config
   `default_author`, then `unspecified`.
5. Build `migrate` and test it against a **copy** of
   `../demiurge/.memory/log/entries.jsonl`:
   - counts and final states must match `load_entries()` in
     `legacy/mneme_v0.py`;
   - keep legacy IDs (`D0001`), fold patches in, convert timestamps to UTC,
     and record no branch rather than a guessed one.
6. Port the viewer if it's wanted in v0.1, then delete `legacy/`.
7. Tag v0.1, then migrate Demiurge (in a Demiurge session; Demiurge has
   reminder `R-261102-c1d3` and decision `D-261102-d927` for this):
   - `uv tool install -e ../mneme` and `mneme migrate`, then compare counts;
   - remove `scripts/memory.py`, the JSONL, the generated views, the
     `.gitattributes` line and the git hook lines;
   - update AGENTS.md, CLAUDE.md and the memory skill;
   - log a decision that supersedes D0001.

## Notes

- This folder is under OneDrive like Demiurge. Fine without SQLite, but watch
  for OneDrive "conflicted copy" files appearing inside `.git`.
- Prior art reviewed, so the reasoning doesn't need redoing:
  - Beads (Go; JSONL + SQLite + hash IDs + its own merge driver; tasks with
    dependencies; Python only through the `beads-mcp` wrapper);
  - git-bug;
  - adr-tools / log4brains / MADR;
  - changesets / towncrier, the one-file-per-entry pattern;
  - Cline Memory Bank.

  None of these combines decisions, learnings, questions, reminders and
  per-branch handover in a stdlib-only tool, so building this is justified.
  Don't let it grow into a task tracker.
