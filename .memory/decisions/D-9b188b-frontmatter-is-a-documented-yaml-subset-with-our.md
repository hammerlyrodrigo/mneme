---
id: D-9b188b
type: decision
title: Frontmatter is a documented YAML subset with our own parser
status: accepted
created: 2026-11-02T13:05:15Z
author: claude
branch: main
tags: [format]
links: [src/mneme/model.py]
---

## Context

Choice between a YAML subset (familiar, MADR/log4brains-friendly, rendered by GitHub) and TOML frontmatter (free via tomllib). Settled with the user 2026-11-02.

## Decision

--- delimited; one key: value per line; plain scalars, quoted strings and inline [a, b] lists. Every value is a string; nothing is coerced. Anything else is a reported error. Unknown keys survive a round trip. Type-specific fields are ## sections in the body.

## Consequences

No dependency. Hand edits that use richer YAML are rejected, not guessed.
