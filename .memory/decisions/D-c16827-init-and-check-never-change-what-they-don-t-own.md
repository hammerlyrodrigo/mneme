---
id: D-c16827
type: decision
title: init and check never change what they don't own
summary: init writes only .memory/, config and opt-in marked blocks; check only reports and exits 1 for CI
status: accepted
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [cli]
keywords: [setup, agents, skill, ci, safety]
links: [src/mneme/init.py, src/mneme/check.py]
---

## Context

v0's init rewrote AGENTS.md, dropped everything after its block, and installed git hooks; its gc changed entries.

## Decision

init creates .memory/ and config.toml only. --write-agents adds or refreshes a marked block and keeps the surrounding text and line endings. --claude won't overwrite an edited skill without --force. check only reports, and exits 1 for CI.
