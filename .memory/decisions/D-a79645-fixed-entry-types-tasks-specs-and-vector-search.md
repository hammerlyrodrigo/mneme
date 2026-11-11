---
id: D-a79645
type: decision
title: Fixed entry types; tasks, specs and vector search are out of scope
status: accepted
created: 2026-11-02T13:05:16Z
author: claude
branch: main
tags: [scope]
keywords: [scope, types, embeddings, semantic, tasks, specs]
links: [src/mneme/model.py]
---

## Context

Spec tools (Spec Kit, OpenSpec, Kiro, BMAD) and task trackers (Beads) already cover specs and tasks; none keep decisions, learnings, questions, reminders and per-branch handover across features and sessions.

## Decision

Types are decision, learning, question, reminder, concept and note, plus handover. They are not configurable and there are no plugins. No tasks, no specs, no vector search, no LLM consolidation that changes entries on its own.

## Consequences

Don't let Mneme grow into a task tracker.
