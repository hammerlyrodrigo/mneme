"""`mneme init`: create `.memory/`, and optionally agent instructions."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from mneme.root import CONFIG_NAME, MEMORY_DIRNAME

BLOCK_START = "<!-- mneme:start -->"
BLOCK_END = "<!-- mneme:end -->"
GITATTRIBUTES_LINE = f"{MEMORY_DIRNAME}/** linguist-generated=true"
SKILL_PATH = Path(".claude") / "skills" / "mneme" / "SKILL.md"
SKILL_FRONTMATTER = (
    "---\n"
    "name: mneme\n"
    "description: Project memory for this repo. Use at session start (mneme brief), before\n"
    "  changing code (mneme recall --path), when making a decision, learning something,\n"
    "  leaving a question open or deferring work, and before ending a session (mneme handover).\n"
    "---\n\n"
)


def template(name: str) -> str:
    return files("mneme").joinpath("templates", name).read_text(encoding="utf-8")


def _read(path: Path) -> str:
    # newline="" keeps the file's own line endings when we write it back.
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def init_memory(root: Path) -> list[str]:
    actions = []
    memory_dir = root / MEMORY_DIRNAME
    if not memory_dir.is_dir():
        memory_dir.mkdir(parents=True)
        actions.append(f"created {MEMORY_DIRNAME}/")
    config = memory_dir / CONFIG_NAME
    if not config.exists():
        _write(config, template("config.toml"))
        actions.append(f"created {MEMORY_DIRNAME}/{CONFIG_NAME}")
    return actions


def agents_block(newline: str = "\n") -> str:
    body = f"{BLOCK_START}\n## Project memory (Mneme)\n\n{template('instructions.md').rstrip()}\n{BLOCK_END}"
    return body.replace("\n", newline)


def write_agents(root: Path) -> str:
    """Add or refresh the marked block in AGENTS.md, keeping all text around it."""
    path = root / "AGENTS.md"
    if not path.exists():
        _write(path, agents_block() + "\n")
        return "created AGENTS.md"
    text = _read(path)
    newline = "\r\n" if "\r\n" in text else "\n"
    block = agents_block(newline)
    start, end = text.find(BLOCK_START), text.find(BLOCK_END)
    if start != -1 and end > start:
        updated = text[:start] + block + text[end + len(BLOCK_END):]
    elif start != -1 or end != -1:
        raise ValueError(f"{path}: found only one of {BLOCK_START} / {BLOCK_END}; fix it by hand")
    else:
        sep = "" if text.endswith(newline * 2) else (newline if text.endswith(newline) else newline * 2)
        updated = text + sep + block + newline
    if updated == text:
        return "AGENTS.md already up to date"
    _write(path, updated)
    return "updated AGENTS.md"


def write_claude_skill(root: Path, force: bool = False) -> str:
    path = root / SKILL_PATH
    content = SKILL_FRONTMATTER + "# Project memory (Mneme)\n\n" + template("skill.md")
    if path.exists():
        if _read(path) == content:
            return f"{SKILL_PATH.as_posix()} already up to date"
        if not force:
            return f"kept existing {SKILL_PATH.as_posix()} (it differs; use --force to replace it)"
    _write(path, content)
    return f"wrote {SKILL_PATH.as_posix()}"


def hide_in_diffs(root: Path) -> str:
    path = root / ".gitattributes"
    text = _read(path) if path.exists() else ""
    if any(line.strip() == GITATTRIBUTES_LINE for line in text.splitlines()):
        return ".gitattributes already hides .memory/ in diffs"
    newline = "\r\n" if "\r\n" in text else "\n"
    sep = "" if not text or text.endswith(("\n", "\r")) else newline
    _write(path, text + sep + GITATTRIBUTES_LINE + newline)
    return "added .memory/ to .gitattributes as linguist-generated (collapsed in GitHub diffs)"
