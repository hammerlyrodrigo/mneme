# Mneme

Project memory that lives in a git repo beside the code: decisions,
learnings, questions, reminders, concepts and per-branch handovers. Built for
AI-assisted and spec-driven development. Standard library only, Python 3.11+.

Status: pre-release. See [HANDOVER.md](HANDOVER.md) for the plan.

## Install

```sh
uv tool install git+https://github.com/hammerlyrodrigo/mneme
```

## Use

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

Each entry is a small Markdown file under `.memory/<type>s/`, so entries from
different branches merge without conflicts, and a real disagreement shows up
as an ordinary git conflict. Nothing else is generated or committed.
