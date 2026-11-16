<p align="center">
  <img src="mneme-logo.svg" alt="Mneme" width="96">
</p>

# Mneme

Project memory for AI-assisted development: a small, shared memory that lives
in your git repo beside the code, so people and agents can pick up the thread.
Mneme keeps decisions, learnings, questions, reminders, concepts and per-branch
handovers. It needs only the standard library and Python 3.11+.

Status: pre-release. See [HANDOVER.md](HANDOVER.md) for the plan.

[![Watch: what Mneme is, in about 7 minutes](https://img.youtube.com/vi/Pjpyk-sOQqQ/maxresdefault.jpg)](https://youtu.be/Pjpyk-sOQqQ)

▶ **[Watch the 7-minute introduction](https://youtu.be/Pjpyk-sOQqQ)**

## Why

Every project runs on things that never make it into the code: why a design
was chosen, what an experiment taught, which question is still open, where the
next person should begin. That context lives in chats, tickets and people's
heads, and it leaks. AI agents make the leak bigger, because they explore more
options and produce more findings than any prompt can carry forward. So each
new session either rediscovers what was already known or reads far more history
than the task needs.

Mneme keeps the outcome of that work, short and reviewable, and brings back
only what the current task needs.

## What it keeps

| Kind | What it preserves |
| --- | --- |
| Handover | Where to resume (one per branch, overwritten each time) |
| Learning | What an experiment or a failed approach taught |
| Decision | Why something is built the way it is |
| Concept | What a term means in this project |
| Reminder | Something decided but deferred until a trigger |
| Question | What we still don't know |
| Note | Anything else worth keeping |

What it leaves out, on purpose:

- **How to do a task.** Procedures belong in skills and project instructions.
- **Tasks and to-dos.** Those belong in your issue tracker or spec tool.
- **Transcripts.** Keep the outcome and enough reasoning to trust it later,
  not the conversation that got there.

## Quick start

```sh
uv tool install git+https://github.com/hammerlyrodrigo/mneme
mneme init --write-agents --claude
```

`init` creates `.memory/`, adds a short block to `AGENTS.md` saying when to use
Mneme, and with `--claude` writes a Claude Code skill
(`.claude/skills/mneme/SKILL.md`) that spells out how.

From then on, the agent follows a simple routine:

1. **Brief.** `mneme brief` at session start: the branch handover, pending
   reminders and recent decisions. Small and bounded.
2. **Recall.** `mneme recall --path <file>` or `mneme recall <words>` before
   changing an area. Hits come back as one-line summaries; `mneme show <id>`
   opens only the entry that matters.
3. **Record.** `mneme new <type>` for decisions, learnings and questions worth
   keeping.
4. **Hand over.** `mneme handover --summary ... --next ...` before stopping.

Nothing is automatic. Mneme does not watch conversations or force entries to
be written. The agent follows the routine because the instructions ask it to,
and people can use the same commands.

## An example

A session starts on the authentication code. Before touching it, the agent
recalls what applies:

```console
$ mneme recall --path src/auth/
L-4c1e9a  Browser storage is readable by scripts
    Anything kept in browser storage can be read by any script on the page
Q-3c8d21  Where should session tokens live?
```

The work settles that open question, and the agent records the result and
closes the question:

```sh
mneme new decision --title "Session token storage" \
  --context "Browser storage is exposed to script access" \
  --decision "Use secure, HTTP-only cookies" \
  --summary "Session tokens stay out of browser storage" \
  --links src/auth/session.py
mneme resolve Q-3c8d21 --answer "HTTP-only cookies" --decision D-7f3a2c
```

The decision is a Markdown file on the branch, so it goes into the pull request
beside the code change, and teammates review it like anything else
(`mneme changes --markdown` prints the branch's memory for the PR description).
Once merged, it belongs to the project, and the next session that touches
`src/auth/` finds it.

## How it works

- **One file per entry**, under `.memory/<type>s/`. Entries from different
  branches merge cleanly; a real disagreement shows up as an ordinary git
  conflict, settled in review. The handover is one file per branch, so give
  parallel agents their own branches or worktrees.
- **Only what the commands return enters the agent's context.** Summaries,
  keywords and ranked matches do the finding, so memory can grow while each
  session stays small.
- **No index or database.** Nothing is generated or committed besides the
  Markdown files, so nothing can drift out of sync with them.
- **Entries have a way to close.** Questions get resolved, reminders done,
  decisions superseded. Settled entries drop out of `brief` and `recall`
  (unless `--all`), and `mneme archive --inactive` moves them to
  `.memory/archive/` unchanged, without losing git history.

### What it won't do

A file can be up to date and still be wrong. Mneme can't tell whether a decision
still matches code that has changed, and it may miss two entries that
contradict each other. Keeping the meaning true stays with the team.
`mneme dream` prints a prompt that suggests what to consolidate, but it changes
nothing; someone makes the edit, and the team reviews it.

## Beside the tools you already use

| Tool | Its job |
| --- | --- |
| Specs (OpenSpec, Spec Kit, ...) | What should this change do? |
| Issue tracker | What is left to do? |
| Skills and instructions | How should the agent do the work? |
| Code and tests | What does the system do now? |
| **Mneme** | **What should future work remember?** |

Link rather than copy: point an entry at the spec or code with `--links`, and
recall it when you are back in that area.

## Command reference

```sh
mneme init --write-agents          # .memory/ + a block in AGENTS.md (--claude for a Claude Code skill)

mneme new decision --title "Use one file per entry" --context "..." --decision "..." \
  --summary "One Markdown file per entry, so branches merge" --keywords storage,database --links src/store.py
mneme new learning --title "..." --tried "..." --result "..." --takeaway "..."
mneme new question --text "Which auth provider?"
mneme new reminder --action "Bump deps" --trigger "after v1"
mneme new concept  --term "Entry" --definition "..."
mneme new note     --title "..." --body "..."
echo '{"title": "...", "tried": "..."}' | mneme new learning --stdin

mneme resolve Q-3c8d21 --answer "Keycloak" --decision D-91b0e4
mneme done R-44b2c0
mneme supersede D-7f3a2c --by D-91b0e4
mneme archive --inactive             # move settled entries to .memory/archive/
mneme handover --summary "..." --done "..." --next "..."

mneme brief                        # session start: small and bounded
mneme recall auth tokens           # ranked hits, each with a one-line gist
mneme recall --path src/auth/      # what applies to this code
mneme show D-7f Q-3c               # entries in full (ID prefixes work; --raw for the file)
mneme set D-7f3a2c --summary "..." --keywords a,b
mneme changes --markdown           # this branch's memory, for a PR description
mneme check                        # problems; exit 1 for CI
mneme dream | <agent>              # a prompt to consolidate memory; changes nothing
mneme migrate --from .memory/log/entries.jsonl --dry-run   # import a mneme v0 log
```

Every entry takes `--summary` (one line stating the outcome), `--keywords`
(search words the text doesn't use) and `--links` (the code or spec it is
about). `mneme new <type> --help` lists a type's fields.
