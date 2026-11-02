import subprocess
from pathlib import Path

import pytest

from mneme.model import Entry
from mneme.store import Store


def run_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=check
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway git repo on `main` with one commit and a local identity."""
    root = tmp_path / "repo"
    root.mkdir()
    run_git(root, "init", "-q", "-b", "main")
    run_git(root, "config", "user.name", "Test")
    run_git(root, "config", "user.email", "test@example.com")
    run_git(root, "config", "core.autocrlf", "false")
    run_git(root, "commit", "-q", "--allow-empty", "-m", "root")
    return root


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path)


def make(entry_type: str = "decision", title: str = "Use files", **kw) -> Entry:
    defaults = {"decision": "accepted", "question": "open", "reminder": "pending"}
    kw.setdefault("status", defaults.get(entry_type, "active"))
    kw.setdefault("created", "2026-11-02T10:00:00Z")
    return Entry(id=kw.pop("id", ""), type=entry_type, title=title, **kw)
