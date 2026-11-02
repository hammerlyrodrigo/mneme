---
id: L-58e8a8
type: learning
title: Stripping git output broke porcelain parsing
status: active
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [git, bug]
links: [src/mneme/root.py, src/mneme/changes.py]
---

## Tried

root.git() stripped stdout for every command, including git status --porcelain -z.

## Result

The leading space of the first ' M' status code was removed, so an uncommitted modified entry was missed by mneme changes. A test caught it.

## Takeaway

Call git(..., strip=False) whenever leading whitespace is data.
