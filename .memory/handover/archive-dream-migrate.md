---
branch: archive-dream-migrate
updated: 2026-11-11T13:27:00Z
author: Rodrigo Hammerly
agent: claude-code
---

## Summary

Phase 2 code done on archive-dream-migrate: archive (replaces compact), dream, migrate. Ready for PR. v0.1 tag waits on that merge and on a dry run against Demiurge's real log.

## Done

archive: moves inactive entries to .memory/archive/<type>s/ unchanged; this repo's 4 inactive entries archived; Q-812131 resolved (D-099eb1). dream: prompt with real commands, overlap groups by IDF-weighted words (D-f74897). migrate: replays v0 log, all-or-nothing, re-runnable (D-f6c55b). 184 tests pass.

## Next

1. Merge this branch's PR.
2. On a machine with Demiurge: copy .memory/log/entries.jsonl, run 'mneme migrate --from <copy> --dry-run' in a scratch repo, compare counts with v0's load_entries() there.
3. Tag v0.1, then R-94ea8d (migrate Demiurge).
4. v0.2: brief by changed files and new-on-main count; handover --close (prints suggested 'mneme new reminder' commands); overlap warnings in changes/check plus R-bacfd4 (also: an entry edited and archived on one branch shows only as archived); opt-in Claude Code hooks; check --stale; list across types; viewer (D-b0e726), then R-586ca1.
5. Revisit dream's 0.3 overlap threshold after a dream on Demiurge.

## Blockers

Demiurge is not on this machine, so migrate is verified only on a fixture shaped like v0's writers. Root HANDOVER.md is still the stale pre-build plan that README links to.
