---
id: D-42cdb6
type: decision
title: One handover file per branch, overwritten each time
summary: Each branch overwrites its own .memory/handover/<branch>.md; git keeps the history
status: accepted
created: 2026-11-02T13:05:15Z
author: claude
branch: main
tags: [handover]
keywords: [session, checkpoint, overwrite]
links: [src/mneme/store.py, src/mneme/check.py]
---

## Context

A shared handover is either stale or conflicting when several branches are active.

## Decision

.memory/handover/<branch>.md with / turned into --; git keeps the history. On the main branch, another branch's handover file means that branch was merged and its content should be folded in; check reports it.

## Consequences

The merged-branch check gives the same answer on every machine, unlike v0's gc, which judged by local branches.
