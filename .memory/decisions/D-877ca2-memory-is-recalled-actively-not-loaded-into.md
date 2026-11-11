---
id: D-877ca2
type: decision
title: Memory is recalled actively, not loaded into context in bulk
summary: brief is bounded; recall and show fetch the rest on demand, so context stays small
status: accepted
created: 2026-11-02T13:05:16Z
author: claude
branch: main
tags: [retrieval, agents]
keywords: [context, tokens, load, retrieval]
links: [src/mneme/brief.py, src/mneme/recall.py, src/mneme/templates/instructions.md]
---

## Context

The user does not want memory to bloat an agent's context. Files on disk cost no tokens; only what commands print does.

## Decision

brief prints a bounded view (about 20-40 lines whatever the entry count). recall returns ranked one-liners by words and/or --path (entries whose links cover a file). show is the only command that prints a full entry. Inactive entries are hidden unless --all. Agents are told not to read .memory/ directly.

## Consequences

Entries should carry --links to code and specs so recall --path can find them. search and refs from the first plan became recall.
