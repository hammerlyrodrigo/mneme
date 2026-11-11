---
id: R-565981
type: reminder
title: Add a gitignored SQLite FTS5 cache, rebuilt from the files when their modification times change;...
summary: Deferred design review item 16; files stay the source of truth (D-956800)
status: pending
created: 2026-11-11T09:13:42Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
keywords: [database, index, search, performance, sqlite]
links: [src/mneme/recall.py, src/mneme/store.py]
---

## Trigger

Memory passes ~2,000 entries, or the cold-read pause on Windows becomes a complaint

## Action

Add a gitignored SQLite FTS5 cache, rebuilt from the files when their modification times change; never committed
