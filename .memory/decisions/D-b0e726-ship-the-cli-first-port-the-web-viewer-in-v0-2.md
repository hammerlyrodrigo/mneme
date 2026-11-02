---
id: D-b0e726
type: decision
title: Ship the CLI first; port the web viewer in v0.2
status: accepted
created: 2026-11-02T13:05:16Z
author: claude
branch: main
tags: [scope, viewer]
links: [legacy/mneme_v0.py]
---

## Context

About 650 of v0's 2,000 lines are the serve viewer. Settled with the user 2026-11-02.

## Decision

v0.1 is the CLI plus migrate. serve is ported in v0.2, and legacy/ stays until then.

## Consequences

legacy/mneme_v0.py stays in the repo for now, as reference only.
