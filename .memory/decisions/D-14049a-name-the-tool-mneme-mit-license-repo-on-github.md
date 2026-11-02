---
id: D-14049a
type: decision
title: Name the tool Mneme; MIT license; repo on GitHub
status: accepted
created: 2026-11-02T13:05:16Z
author: claude
branch: main
tags: [packaging]
links: [pyproject.toml, LICENSE]
---

## Context

mneme on PyPI is taken by an abandoned 2014 package.

## Decision

Folder, import package and command are all mneme. MIT license. The repo is github.com/hammerlyrodrigo/mneme. v0.1 installs from git; if PyPI is ever needed, publish under another distribution name such as mneme-cli.
