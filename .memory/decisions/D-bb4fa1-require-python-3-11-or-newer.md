---
id: D-bb4fa1
type: decision
title: Require Python 3.11 or newer
status: accepted
created: 2026-11-02T13:05:15Z
author: claude
branch: main
tags: [packaging]
keywords: [version, tomllib, compatibility]
links: [pyproject.toml, .github/workflows/ci.yml]
---

## Context

3.11 brings tomllib for config.toml; 3.10 reached end of life in October 2026. Settled with the user 2026-11-02.

## Decision

requires-python >= 3.11; CI tests 3.11 to 3.14 on Windows, macOS and Linux.

## Consequences

On this machine python on PATH is 3.10; use uv (the repo pins 3.12).
