---
id: L-ad78c2
type: learning
title: Use real throwaway git repos to test merge behaviour
status: active
created: 2026-11-02T13:05:18Z
author: claude
branch: main
tags: [testing, git]
keywords: [test, git, mock, merge, ci]
links: [tests/test_merge.py, tests/conftest.py]
---

## Tried

Testing the storage model's merge claims.

## Result

tests/test_merge.py builds real repos: entries added on two branches merge cleanly; conflicting status edits conflict; the conflicted file loads as a problem.

## Takeaway

Keep merge behaviour tested against real git, not mocks; it runs fine on all three CI platforms.
