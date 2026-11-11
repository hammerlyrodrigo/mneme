---
id: D-04f13c
type: decision
title: A branch's memory is part of its PR
summary: mneme changes lists the branch's entries; --markdown prints them for the PR description
status: accepted
created: 2026-11-02T13:05:16Z
author: claude
branch: main
tags: [git, review]
keywords: [pull, request, review, diff]
links: [src/mneme/changes.py, src/mneme/init.py]
---

## Context

Per-entry files put a branch's decisions and learnings in its PR diff. The user saw that as valuable context for reviewers, not just noise.

## Decision

mneme changes lists entries added or changed since the main branch, committed or not; --markdown prints a block for the PR description. brief on a feature branch says what the branch has recorded so far. Collapsing .memory/ in GitHub diffs (init --hide-in-diffs, linguist-generated) is opt-in, not the default.
