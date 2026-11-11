---
id: L-2402d4
type: learning
title: Same-second timestamps made a test flaky on fast CI runners
status: active
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [testing, ci]
keywords: [flaky, test, clock, ci, timestamp]
links: [tests/test_cli.py]
---

## Tried

test_brief_is_bounded created 60 entries in a loop and expected the newest three.

## Result

Passed locally and on Windows CI, failed on macOS and on Linux with Python 3.13 and 3.14: many entries shared a second and ties have no order.

## Takeaway

CLI tests use a fake clock (the clock fixture in tests/test_cli.py). Don't assert order between entries created in the same second.
