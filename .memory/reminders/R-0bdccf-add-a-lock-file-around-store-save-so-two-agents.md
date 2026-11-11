---
id: R-0bdccf
type: reminder
title: Add a lock file around Store.save() so two agents in one working tree can't lose a status change
summary: Deferred design review item 15; parallel agents should use separate worktrees meanwhile
status: pending
created: 2026-11-11T09:13:42Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
keywords: [concurrency, lock, race, agents]
links: [src/mneme/store.py]
---

## Trigger

First report of a lost edit from two agents sharing one checkout
