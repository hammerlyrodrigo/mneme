---
id: N-d15d6f
type: note
title: "Prior art reviewed: Beads, git-bug, adr-tools, log4brains, MADR, changesets, Cline"
status: active
created: 2026-11-02T13:05:19Z
author: claude
branch: main
tags: [research]
---

Beads (Go; JSONL + SQLite + hash IDs + its own merge driver; tasks with dependencies; Python only via beads-mcp), git-bug, adr-tools / log4brains / MADR, changesets / towncrier (the one-file-per-entry pattern) and Cline Memory Bank. None combines decisions, learnings, questions, reminders and per-branch handover in a stdlib-only tool, so building Mneme is justified. No need to redo this review.
