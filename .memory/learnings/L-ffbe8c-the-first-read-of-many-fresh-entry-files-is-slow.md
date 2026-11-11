---
id: L-ffbe8c
type: learning
title: The first read of many fresh entry files is slow on Windows
summary: "Warm: 2,000 entries load in 0.2 s and recall in 0.03 s. Cold, on Windows: 7-8 s for 2,000 files, 40 s for 10,000"
status: active
created: 2026-11-11T09:13:42Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
tags: [storage]
keywords: [performance, speed, antivirus, cache, scale]
links: [src/mneme/store.py]
---

## Tried

Design review 2026-11-11: copied this repo's entries into test sets of 2,000 and 10,000 files and timed load and recall.

## Result

Warm reads were fast. The first read of freshly written files took 6.8-8.2 s for 2,000 and 39.6 s for 10,000, most likely antivirus scanning.

## Takeaway

The in-memory scan in D-956800 holds into the low thousands of entries. The first command after a large checkout on Windows may pause; that, or more than ~2,000 entries, is the trigger for a gitignored cache.
