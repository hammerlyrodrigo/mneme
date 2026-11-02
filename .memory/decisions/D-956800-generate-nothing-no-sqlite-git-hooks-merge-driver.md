---
id: D-956800
type: decision
title: Generate nothing; no SQLite, git hooks, merge driver or .gitignore management
status: accepted
created: 2026-11-02T13:05:15Z
author: claude
branch: main
tags: [storage]
links: [src/mneme/store.py]
---

## Context

v0's generated views were gitignored yet tracked (dirty trees, stale handover on clones), and its SQLite index had to be kept in sync.

## Decision

Only entry files are committed. brief, recall and list read all entries into memory on demand. init never installs hooks or edits .gitignore.

## Consequences

Nothing goes stale. An in-memory scan is fast enough for thousands of small files; a disposable, gitignored cache can be added later if that changes.
