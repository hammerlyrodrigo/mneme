---
id: D-101f42
type: decision
title: Saving an entry writes no updated stamp
status: accepted
created: 2026-11-11T08:38:58Z
author: unspecified
branch: recall-and-format
tags: [git, format]
keywords: [timestamp, merge, conflict, identical, edit]
links: [src/mneme/store.py, tests/test_merge.py]
supersedes: [D-6538b2]
---

## Context

save() stamped updated on every change, so two branches making the same edit (both marking one reminder done) conflicted though they agreed. Design review 2026-11-11, item 4.

## Decision

save() no longer sets updated; git log records when a file changed. An existing updated value is still read, validated and kept.

## Consequences

Identical edits on two branches merge cleanly. Different edits to one entry still conflict in that one file, which still deserves a human look. Entries no longer show their last-change time without git.
