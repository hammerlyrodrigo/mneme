---
id: D-d6658d
type: decision
title: Author defaults to the git user; agent is recorded separately
summary: "author: --author, MNEME_AUTHOR, config default_author, git user.name; agent: --agent, MNEME_AGENT, then detected (CLAUDECODE)"
status: accepted
created: 2026-11-11T09:11:00Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
tags: [provenance]
keywords: [who, identity]
links: [src/mneme/cli.py]
---

## Context

author was free text and every entry here said 'claude', so a team could not tell a colleague's decision from an agent's guess. Design review 2026-11-11, item 12.

## Decision

author is the person responsible, falling back to git config user.name. A separate agent field names the tool that wrote it on their behalf, for entries and handovers. Detection only covers env vars we know are set (CLAUDECODE); other agents set MNEME_AGENT.

## Consequences

Provenance survives merges, unlike branch. Agents should no longer pass --author with their own name.
