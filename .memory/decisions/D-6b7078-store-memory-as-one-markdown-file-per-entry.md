---
id: D-6b7078
type: decision
title: Store memory as one Markdown file per entry
summary: One Markdown file per entry, so entries from different branches never conflict
status: accepted
created: 2026-11-02T13:05:15Z
author: claude
branch: main
tags: [storage, git]
keywords: [storage, database, jsonl, format, merge]
links: [src/mneme/store.py, src/mneme/model.py, tests/test_merge.py]
---

## Context

mneme_v0 kept one shared JSONL log with merge=union. Hosted web merges (GitHub, GitLab, Bitbucket) ignore merge drivers, so every PR touching the log conflicted, and status patches resolved as last-in-file wins, silently.

## Decision

Each entry is its own Markdown file with frontmatter under .memory/<type>s/<id>-<slug>.md. A status is one frontmatter line.

## Consequences

New entries from different branches never conflict, even in web merges; two branches changing one entry give a normal git conflict. History comes from git log -p. Agents can read and write entries by hand. Cost: many small files (see the open question on file count).
