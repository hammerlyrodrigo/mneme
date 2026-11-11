---
id: D-dc7beb
type: decision
title: Frontmatter subset accepts block lists on read
status: accepted
created: 2026-11-11T08:38:58Z
author: unspecified
branch: recall-and-format
tags: [format]
keywords: [yaml, frontmatter, parser, list, editor, obsidian]
links: [src/mneme/model.py]
supersedes: [D-9b188b]
---

## Context

Editors, formatters and Obsidian write lists as 'key:' followed by '- item' lines; the strict parser rejected them and the entry dropped out of recall. Design review 2026-11-11, item 5.

## Decision

Same YAML subset as before, plus: a key with no value may be followed by '- item' lines (plain or quoted scalars) forming a list. Lists are always written inline. Multi-line scalars, nested lists and maps stay errors, with a clearer message for indented continuation lines.

## Consequences

Hand edits by common tools keep working. Still no dependency and no type coercion.
