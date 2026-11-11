---
id: N-bd8b54
type: note
title: "This machine: OneDrive, CRLF, Python 3.10 on PATH"
summary: Repo under OneDrive with core.autocrlf on; use uv's Python, not the 3.10 on PATH
status: active
created: 2026-11-02T13:05:19Z
author: claude
branch: main
tags: [environment]
keywords: [windows, environment, line, endings, python]
---

The repo is under OneDrive: watch for 'conflicted copy' files inside .git. Git has core.autocrlf on; the repo's .gitattributes keeps LF and the parser accepts CRLF. python on PATH is 3.10; use uv run (3.12 pinned) or .venv. gh is not logged in; pushing works over SSH. CI failures are readable without login through the check-runs annotations API.
