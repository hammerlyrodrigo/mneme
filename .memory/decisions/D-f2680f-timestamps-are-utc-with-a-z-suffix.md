---
id: D-f2680f
type: decision
title: Timestamps are UTC with a Z suffix
status: accepted
created: 2026-11-02T13:05:17Z
author: claude
branch: main
tags: [format]
links: [src/mneme/model.py]
---

## Context

v0 wrote local offsets and sorted them as strings, so ordering was wrong across time zones.

## Decision

Write YYYY-MM-DDTHH:MM:SSZ; parse any offset and sort as datetimes.

## Consequences

One-second resolution: entries created in the same second have no defined order.
