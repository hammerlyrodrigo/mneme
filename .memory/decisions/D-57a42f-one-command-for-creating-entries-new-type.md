---
id: D-57a42f
type: decision
title: "One command for creating entries: new <type>"
status: accepted
created: 2026-11-02T13:05:16Z
author: claude
branch: main
tags: [cli]
links: [src/mneme/cli.py]
---

## Context

Alternative was verb shortcuts (decide, learned, ask, remind).

## Decision

mneme new <type> with per-type flags or --stdin JSON. Flags win over JSON; JSON keys are validated per type and nothing is written on any error.

## Consequences

One pattern to learn; it maps to the folders and agents get it right.
