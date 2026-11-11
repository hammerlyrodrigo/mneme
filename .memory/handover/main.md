---
branch: main
updated: 2026-11-11T11:45:38Z
author: Rodrigo Hammerly
agent: claude-code
---

## Summary

Design review (2026-11-11) phase 1 merged in PR #1: recall finds different wording and prints a gist per hit; entries have summary/keywords/agent; show is compact; AGENTS.md block is 6 lines. Next is phase 2, then v0.1.

## Done

PR #1: D-101f42, D-dc7beb, D-b91150, D-f790b9, D-d6658d, D-12aedf; learning L-ffbe8c; reminders R-0bdccf, R-565981, R-bacfd4. Earlier: core CLI (init, new, set, resolve, done, supersede, handover, brief, recall, list, show, changes, check).

## Next

1. Archive by moving inactive entries to .memory/archive/<type>s/ unchanged (replaces the folding compact); show and recall --all still find them. Resolve Q-812131 with it.
2. dream: print a consolidation prompt with the real schema, including summary and keywords (D-464a61).
3. migrate --from <entries.jsonl>: test on a COPY of ../demiurge/.memory/log/entries.jsonl. Counts and final states must match load_entries() in legacy/mneme_v0.py. Keep legacy IDs and authors, fold patches in, convert timestamps to UTC, record no branch. Map consolidated/obsolete/stale to superseded/archived. Summary can be left to the gist fallback.
4. Tag v0.1, then R-94ea8d (migrate Demiurge).
5. v0.2: brief by changed files and new-on-main count; handover --close (prints suggested 'mneme new reminder' commands); overlap warnings in changes/check plus R-bacfd4; opt-in Claude Code hooks; check --stale; list across types; viewer (D-b0e726), then R-586ca1.

## Blockers

Root HANDOVER.md is the stale pre-build plan and README links to it: delete it or point README at mneme brief.
