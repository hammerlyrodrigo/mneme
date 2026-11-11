---
id: D-12aedf
type: decision
title: The AGENTS.md block is short; details live in the skill and --help
summary: Six bullets load every session; flags, type guidance and loop-closing commands load only when needed
status: accepted
created: 2026-11-11T09:12:52Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
tags: [agents, context]
keywords: [instructions, tokens, prompt]
links: [src/mneme/templates/instructions.md, src/mneme/templates/skill.md]
---

## Context

The 25-line instruction block (~1.5 KB, ~400 tokens) loaded in every session whether used or not. Design review 2026-11-11, item 7.

## Decision

templates/instructions.md (the AGENTS.md block) says: brief at start, recall before changes, record with mneme new, handover at the end. templates/skill.md (the Claude Code skill) holds the full guidance. mneme new --help describes each type.

## Consequences

Agents without the skill rely on --help for flags. Keep the block from growing back; a test caps it.
