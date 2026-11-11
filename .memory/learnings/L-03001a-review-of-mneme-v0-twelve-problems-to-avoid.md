---
id: L-03001a
type: learning
title: "Review of mneme_v0: twelve problems to avoid"
status: active
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [legacy]
keywords: [legacy, v0, problems, lessons]
links: [legacy/mneme_v0.py]
---

## Tried

mneme_v0 (Demiurge scripts/memory.py at d8d3cb8): a JSONL log with merge=union, a SQLite index and generated Markdown views.

## Result

1 web merges ignore merge drivers; 2 status patches were last-in-file wins; 3 patches to unknown IDs were dropped silently; 4 IDs collided silently; 5 --stdin skipped validation and one bad entry broke every command; 6 current_branch() ran per entry on load (1.4s for 69 entries) and mislabelled old entries; 7 generated views were gitignored but tracked; 8 gc depended on local branches and dropped #anchor links; 9 dream clustering was inverted; 10 timestamps sorted as strings across offsets; 11 init rewrote AGENTS.md and installed hooks; 12 hard-coded root, branch names and Demiurge text.

## Takeaway

Each one is designed out in v0.1: see the decisions tagged storage, ids, format, handover and cli. Port entry types, flags, --stdin and the viewer; never its storage.
