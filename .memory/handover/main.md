---
branch: main
updated: 2026-11-02T13:05:27Z
author: claude
---

## Summary

Core CLI built and dogfooded: this repo's plan now lives in .memory/ (16 decisions, 4 learnings, 1 question, 3 reminders, 3 concepts, 2 notes). Run mneme here with 'uv run mneme' (or uv tool install -e .).

## Done

Storage core (model, store, root) and commands init, new, set, resolve, done, supersede, handover, brief, recall, list, show, changes, check. 122 tests; CI green on Windows, macOS, Linux x Python 3.11-3.14.

## Next

1. compact (main only; inactive entries -> .memory/archive/<type>s.md; show and recall --all still find them) - see Q-812131.
2. dream: print a consolidation prompt with the real schema (D-464a61).
3. migrate --from <entries.jsonl>: test on a COPY of ../demiurge/.memory/log/entries.jsonl. Counts and final states must match load_entries() in legacy/mneme_v0.py. Keep legacy IDs, fold patches in, convert timestamps to UTC, record no branch. Map consolidated/obsolete/stale to superseded/archived.
4. Tag v0.1, then R-94ea8d (migrate Demiurge). Viewer in v0.2 (D-b0e726), then R-586ca1.
