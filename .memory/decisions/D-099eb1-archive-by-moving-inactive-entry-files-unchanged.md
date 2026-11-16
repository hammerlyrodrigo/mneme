---
id: D-099eb1
type: decision
title: Archive by moving inactive entry files, unchanged, to .memory/archive/
summary: mneme archive moves settled entries to .memory/archive/<type>s/ byte for byte; show and --all still find them; git follows the rename
status: accepted
created: 2026-11-11T13:19:34Z
author: Rodrigo Hammerly
agent: claude-code
branch: archive-dream-migrate
tags: [storage, archive]
keywords: [compact, cleanup, clutter, files, scale, forget]
links: [src/mneme/store.py, src/mneme/cli.py, src/mneme/changes.py, tests/test_merge.py]
---

## Context

Q-812131: hundreds of files in .memory/ may put developers off. The planned compact folded inactive entries into one file per type, which needed a second parser, broke per-file history, and conflicted with any branch still editing a folded entry. Design review 2026-11-11, item 13.

## Decision

mneme archive <id>... or --inactive moves inactive entries to .memory/archive/<type>s/ unchanged; --restore moves them back. Only inactive entries can be archived. Archived entries load like any other, so show, recall --all and list --all find them. check skips link checks for archived entries and flags an active one. changes reports a move as archived/restored, and the PR block counts moves instead of listing them. Runs on any branch; it travels in the PR like other memory changes.

## Consequences

The live folders hold only what matters now. One format, one parser, per-file history kept. An edit on a branch merges into the archived file through git's rename detection; disagreeing edits still conflict, in that one file.
