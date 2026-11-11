---
id: D-6538b2
type: decision
title: Editing one entry on two branches always conflicts
status: superseded
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [git]
links: [src/mneme/store.py, tests/test_merge.py]
---

## Context

save() stamps updated on every change.

## Decision

Keep it: two edits to the same entry deserve a human look, and git shows them as a conflict in that file. A conflicted file loads as a reported problem, not a crash.
