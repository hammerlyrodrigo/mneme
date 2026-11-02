---
id: D-0a1f83
type: decision
title: IDs are a type letter plus 6 random hex digits, checked unique
status: accepted
created: 2026-11-02T13:05:15Z
author: claude
branch: main
tags: [ids]
links: [src/mneme/model.py, src/mneme/store.py]
---

## Context

v0 used 4 random hex characters per type per day with no collision check; a collision silently replaced the earlier entry.

## Decision

<P>-<6 hex from secrets>, checked against loaded entries and against filenames of files that fail to parse. Lookups go by case-insensitive ID prefix, so renaming a slug never breaks a reference. Legacy IDs (D0001, R-261102-c1d3) stay valid.

## Consequences

IDs say nothing about order; sort by created.
