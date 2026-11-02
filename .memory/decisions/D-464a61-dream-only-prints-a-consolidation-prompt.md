---
id: D-464a61
type: decision
title: dream only prints a consolidation prompt
status: accepted
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [scope]
---

## Context

v0's dream clustering was inverted and its prompt referenced a schema that didn't exist.

## Decision

dream prints a prompt that includes the real schema. Acting on it means new entries with supersedes, reviewed in a PR. Nothing changes entries automatically.
