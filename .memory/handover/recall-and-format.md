---
branch: recall-and-format
updated: 2026-11-11T09:13:56Z
author: Rodrigo Hammerly
agent: claude-code
---

## Summary

Phase 1 of the 2026-11-11 design review (entry format and recall) is done on branch recall-and-format; ready for review and merge.

## Done

1a no updated stamp (D-101f42). 1b block-list frontmatter (D-dc7beb). 1c-1g summary/keywords + gist fallback, ranked recall with stemming/IDF/partial matches, compact multi-id show, set --summary/--keywords, author from git user + agent field (D-b91150, D-f790b9, D-d6658d). 1h short AGENTS.md block, details in skill.md and new --help (D-12aedf). 1i summaries/keywords backfilled; 'recall database' and 'recall merge conflict' now hit. Learning L-ffbe8c (cold reads on Windows); reminders R-0bdccf (save lock), R-565981 (FTS5 cache). 162 tests pass.

## Next

1. Review and merge this branch (mneme changes --markdown for the PR body).
2. Phase 2: archive-by-move to .memory/archive/<type>s/ replaces the folding compact; resolve Q-812131 with it.
3. dream: include summary and keywords in the schema (D-464a61).
4. migrate --from entries.jsonl: also write a fallback summary; legacy author kept, agent empty.
5. Tag v0.1, then R-94ea8d (migrate Demiurge).
6. Phase 3 (v0.2): brief by changed files, handover --close (prints suggested 'mneme new reminder' commands), overlap warnings, opt-in Claude Code hooks, check --stale, list across types, viewer.

## Blockers

Root HANDOVER.md is the stale pre-build plan; README still points to it. Decide whether to delete it or point README at mneme brief.
