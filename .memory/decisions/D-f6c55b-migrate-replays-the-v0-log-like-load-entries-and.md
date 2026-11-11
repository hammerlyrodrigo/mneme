---
id: D-f6c55b
type: decision
title: migrate replays the v0 log like load_entries() and writes all or nothing
summary: mneme migrate --from entries.jsonl folds v0 creates and patches, keeps legacy ids and authors, maps retired statuses per type, reports every difference
status: accepted
created: 2026-11-11T13:26:49Z
author: Rodrigo Hammerly
agent: claude-code
branch: archive-dream-migrate
tags: [migrate]
keywords: [import, legacy, v0, jsonl, demiurge]
links: [src/mneme/migrate.py, tests/test_migrate.py]
---

## Context

Plan for v0.1: import Demiurge's v0 log so its counts and final states match v0's load_entries(). v0 dropped patches to unknown ids and let a repeated create overwrite silently, had statuses this format lacks, and allowed entry ids in links.

## Decision

Fold creates and patches in order exactly as v0 did. Timestamps to UTC; no branch; legacy id and author kept; agent and summary empty (the gist fallback covers it). consolidated -> superseded; obsolete/stale -> archived, or the type's nearest (decision deprecated, question/reminder dropped). superseded_by/consolidated_into become supersedes on the newer entry when types match, else extra frontmatter. Entry-id links move to related. Unknown v0 keys survive as extra frontmatter. The newest handover becomes the main handover unless one exists. Any invalid record means nothing is written; ids already present are skipped, so it can be re-run. --dry-run reports only.

## Consequences

Tested on a fixture shaped like v0's writers, not yet on Demiurge's real log, which is not on this machine. Run it with --dry-run on a copy of that log before R-94ea8d.
