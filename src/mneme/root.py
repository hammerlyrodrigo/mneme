"""Finding the project root, asking git about branches, and reading config."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MEMORY_DIRNAME = ".memory"
CONFIG_NAME = "config.toml"


class RootNotFound(Exception):
    pass


class ConfigError(Exception):
    pass


def git(args: list[str], cwd: Path) -> str | None:
    """Run git and return stripped stdout, or None if git is missing or fails."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False
        )
    except (FileNotFoundError, NotADirectoryError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def find_root(start: Path | None = None) -> Path:
    """The git top level, or else the nearest ancestor holding `.memory/`."""
    start = (start or Path.cwd()).resolve()
    top = git(["rev-parse", "--show-toplevel"], start)
    if top:
        return Path(top).resolve()
    for candidate in (start, *start.parents):
        if (candidate / MEMORY_DIRNAME).is_dir():
            return candidate
    raise RootNotFound(f"no git repository or {MEMORY_DIRNAME}/ found from {start}")


def current_branch(root: Path) -> str | None:
    """The checked-out branch (also on an unborn branch), or None when detached."""
    return git(["symbolic-ref", "--quiet", "--short", "HEAD"], root) or None


@dataclass
class Config:
    main_branch: str = ""
    spec_dirs: list[str] = field(default_factory=list)
    default_author: str = ""


def load_config(root: Path) -> Config:
    path = root / MEMORY_DIRNAME / CONFIG_NAME
    if not path.is_file():
        return Config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    config = Config()
    for key, value in data.items():
        if key in ("main_branch", "default_author"):
            if not isinstance(value, str):
                raise ConfigError(f"{path}: {key} must be a string")
            setattr(config, key, value)
        elif key == "spec_dirs":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ConfigError(f"{path}: spec_dirs must be a list of strings")
            config.spec_dirs = value
        else:
            raise ConfigError(f"{path}: unknown key {key!r}")
    return config


def main_branch(root: Path, config: Config) -> str:
    """Config `main_branch`, else what `origin/HEAD` points at, else `main`."""
    if config.main_branch:
        return config.main_branch
    ref = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], root)
    if ref and "/" in ref:
        return ref.split("/", 1)[1]
    return "main"
