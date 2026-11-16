import io
import itertools
import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import run_git
from mneme import __version__
from mneme.cli import main
from mneme.init import BLOCK_END, BLOCK_START, GITATTRIBUTES_LINE
from mneme.model import format_ts
from mneme.store import Store


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """Each timestamp one second after the last, so order never depends on runner speed."""
    ticks = itertools.count()
    start = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)

    def fake_now() -> str:
        return format_ts(start + timedelta(seconds=next(ticks)))

    monkeypatch.setattr("mneme.cli.now_utc", fake_now)


@pytest.fixture
def mem(repo, monkeypatch):
    """A repo with `mneme init` done, as the working directory."""
    monkeypatch.chdir(repo)
    for var in ("MNEME_AUTHOR", "MNEME_AGENT", "CLAUDECODE"):
        monkeypatch.delenv(var, raising=False)
    assert main(["init"]) == 0
    return repo


def run(capsys, *argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(stdin.encode("utf-8"))))
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def created_id(output: str) -> str:
    return output.split()[1]


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "usage: mneme" in capsys.readouterr().out


def test_commands_need_init(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    code, _, err = run(capsys, "brief")
    assert code == 1
    assert "mneme init" in err


# --- new --------------------------------------------------------------------


def test_new_decision_writes_sections(mem, capsys):
    code, out, _ = run(capsys, "new", "decision", "--title", "Use files",
                       "--context", "JSONL conflicted", "--decision", "One file each",
                       "--tags", "storage,git", "--links", "src/store.py", "--author", "ana")
    assert code == 0
    entry = Store(mem).find(created_id(out))
    assert (entry.status, entry.author, entry.branch) == ("accepted", "ana", "main")
    assert entry.tags == ["storage", "git"]
    assert entry.links == ["src/store.py"]
    assert entry.section("Context") == "JSONL conflicted"
    assert entry.section("Decision") == "One file each"
    assert "Consequences" not in entry.sections()


@pytest.mark.parametrize(
    "argv, title, section, text",
    [
        (["question", "--text", "Which IdP?"], "Which IdP?", "Question", None),
        (["question", "--text", "Which IdP?\nAuth0 or Keycloak.", "--title", "IdP"],
         "IdP", "Question", "Which IdP?\nAuth0 or Keycloak."),
        (["reminder", "--action", "Bump deps", "--trigger", "after v1"], "Bump deps", "Trigger", "after v1"),
        (["concept", "--term", "Entry", "--definition", "One file"], "Entry", "Definition", "One file"),
        (["learning", "--title", "Mocks", "--takeaway", "Use real git"], "Mocks", "Takeaway", "Use real git"),
    ],
)
def test_new_each_type(mem, capsys, argv, title, section, text):
    code, out, _ = run(capsys, "new", *argv)
    assert code == 0
    entry = Store(mem).find(created_id(out))
    assert entry.title == title
    assert entry.section(section) == (text or "")


def test_new_note_has_free_body(mem, capsys):
    _, out, _ = run(capsys, "new", "note", "--title", "Misc", "--body", "Just text.")
    entry = Store(mem).find(created_id(out))
    assert entry.body == "Just text.\n"


def test_new_requires_title_field(mem, capsys):
    code, _, err = run(capsys, "new", "reminder", "--trigger", "later")
    assert code == 1
    assert "--action is required" in err
    assert Store(mem).entry_files() == []


def test_author_from_env_then_config_then_git(mem, capsys, monkeypatch):
    _, out, _ = run(capsys, "new", "note", "--title", "a")
    assert Store(mem).find(created_id(out)).author == "Test"
    (mem / ".memory" / "config.toml").write_text('default_author = "cfg"\n', encoding="utf-8")
    _, out, _ = run(capsys, "new", "note", "--title", "b")
    assert Store(mem).find(created_id(out)).author == "cfg"
    monkeypatch.setenv("MNEME_AUTHOR", "env")
    _, out, _ = run(capsys, "new", "note", "--title", "c")
    assert Store(mem).find(created_id(out)).author == "env"


def test_agent_from_flag_env_or_detection(mem, capsys, monkeypatch):
    _, out, _ = run(capsys, "new", "note", "--title", "a")
    assert Store(mem).find(created_id(out)).agent == ""
    monkeypatch.setenv("CLAUDECODE", "1")
    _, out, _ = run(capsys, "new", "note", "--title", "b")
    assert Store(mem).find(created_id(out)).agent == "claude-code"
    monkeypatch.setenv("MNEME_AGENT", "codex")
    _, out, _ = run(capsys, "new", "note", "--title", "c")
    assert Store(mem).find(created_id(out)).agent == "codex"
    _, out, _ = run(capsys, "new", "note", "--title", "d", "--agent", "aider")
    assert Store(mem).find(created_id(out)).agent == "aider"
    run(capsys, "handover", "--summary", "x")
    assert Store(mem).load_handover("main").agent == "codex"


def test_new_summary_and_keywords(mem, capsys, monkeypatch):
    code, out, _ = run(capsys, "new", "decision", "--title", "Use files", "--summary", "One file per entry",
                       "--keywords", "database,sqlite", "--keywords", "index")
    assert code == 0
    entry = Store(mem).find(created_id(out))
    assert (entry.summary, entry.keywords) == ("One file per entry", ["database", "sqlite", "index"])
    payload = {"term": "Entry", "summary": "A file", "keywords": ["unit"]}
    _, out, _ = run(capsys, "new", "concept", "--stdin", stdin=json.dumps(payload), monkeypatch=monkeypatch)
    entry = Store(mem).find(created_id(out))
    assert (entry.summary, entry.keywords) == ("A file", ["unit"])


def test_new_warns_about_long_sections(mem, capsys):
    code, _, err = run(capsys, "new", "decision", "--title", "Long", "--context", "x" * 700)
    assert code == 0
    assert "Context is 700 characters" in err
    _, _, err = run(capsys, "new", "decision", "--title", "Short", "--context", "x" * 100)
    assert err == ""


def test_new_stdin(mem, capsys, monkeypatch):
    payload = {"title": "Mocking git", "tried": "Mocks", "takeaway": "Real repos",
               "tags": ["testing"], "links": "tests/"}
    code, out, _ = run(capsys, "new", "learning", "--stdin", stdin=json.dumps(payload),
                       monkeypatch=monkeypatch)
    assert code == 0
    entry = Store(mem).find(created_id(out))
    assert (entry.tags, entry.links) == (["testing"], ["tests/"])
    assert entry.section("Takeaway") == "Real repos"


@pytest.mark.parametrize(
    "payload, message",
    [
        ("not json", "invalid JSON"),
        ("[1]", "JSON object"),
        ('{"title": "x", "colour": "red"}', "unknown field"),
        ('{"title": 3}', "must be a string"),
        ('{"title": "x", "tags": [1]}', "list of strings"),
        ('{"title": "x", "status": "bogus"}', "bad status"),
        ('{"title": "two\\nlines"}', "one line"),
    ],
)
def test_new_stdin_is_validated_before_writing(mem, capsys, monkeypatch, payload, message):
    code, _, err = run(capsys, "new", "decision", "--stdin", stdin=payload, monkeypatch=monkeypatch)
    assert code == 1
    assert message in err
    assert Store(mem).entry_files() == []


def test_new_supersedes(mem, capsys):
    _, out, _ = run(capsys, "new", "decision", "--title", "Old")
    old = created_id(out)
    code, out, _ = run(capsys, "new", "decision", "--title", "New", "--supersedes", old[:5])
    assert code == 0
    store = Store(mem)
    assert store.find(old).status == "superseded"
    assert store.find(created_id(out)).supersedes == [old]


def test_new_supersedes_unknown_or_other_type_refused(mem, capsys):
    _, out, _ = run(capsys, "new", "note", "--title", "A note")
    note = created_id(out)
    assert run(capsys, "new", "decision", "--title", "x", "--supersedes", "D-000000")[0] == 1
    code, _, err = run(capsys, "new", "decision", "--title", "x", "--supersedes", note)
    assert code == 1 and "can only supersede a decision" in err
    assert len(Store(mem).entry_files()) == 1


# --- lifecycle --------------------------------------------------------------


def test_resolve_question(mem, capsys):
    _, out, _ = run(capsys, "new", "question", "--text", "Which IdP?")
    q = created_id(out)
    _, out, _ = run(capsys, "new", "decision", "--title", "Use Keycloak")
    d = created_id(out)
    code, out, _ = run(capsys, "resolve", q, "--answer", "Keycloak.", "--decision", d)
    assert code == 0
    entry = Store(mem).find(q)
    assert (entry.status, entry.resolved_by, entry.section("Answer")) == ("resolved", d, "Keycloak.")


def test_resolve_unknown_id_fails(mem, capsys):
    code, _, err = run(capsys, "resolve", "Q0099", "--answer", "x")
    assert code == 1
    assert "no entry" in err


def test_resolve_only_questions(mem, capsys):
    _, out, _ = run(capsys, "new", "note", "--title", "n")
    assert run(capsys, "resolve", created_id(out), "--answer", "x")[0] == 1


def test_done_and_set(mem, capsys):
    _, out, _ = run(capsys, "new", "reminder", "--action", "Bump deps")
    r = created_id(out)
    assert run(capsys, "done", r, "--note", "Bumped")[0] == 0
    assert Store(mem).find(r).section("Note") == "Bumped"
    assert run(capsys, "set", r, "--status", "pending")[0] == 0
    code, _, err = run(capsys, "set", r, "--status", "accepted")
    assert code == 1 and "pending, done, dropped" in err


def test_supersede_command_and_show(mem, capsys):
    _, out, _ = run(capsys, "new", "concept", "--term", "Entry", "--definition", "v1")
    old = created_id(out)
    _, out, _ = run(capsys, "new", "concept", "--term", "Entry", "--definition", "v2")
    new = created_id(out)
    assert run(capsys, "supersede", old, "--by", new)[0] == 0
    code, out, _ = run(capsys, "show", old, "--raw")
    assert code == 0
    assert f"# superseded by {new}" in out
    assert "status: superseded" in out
    _, out, _ = run(capsys, "show", old)
    assert out == f"# {old}  Entry  [superseded]\nSuperseded by: {new}\n\n## Definition\n\nv1\n"


def test_show_several_ids_compact(mem, capsys):
    _, out, _ = run(capsys, "new", "decision", "--title", "Use files", "--summary", "One file each",
                    "--decision", "Files.", "--links", "src/a.py", "--tags", "storage")
    a = created_id(out)
    _, out, _ = run(capsys, "new", "note", "--title", "A note", "--body", "Text.")
    b = created_id(out)
    code, out, _ = run(capsys, "show", a, b)
    assert code == 0
    assert out == (f"# {a}  Use files  [accepted]\nSummary: One file each\nLinks: src/a.py\n\n"
                   f"## Decision\n\nFiles.\n\n# {b}  A note  [active]\n\nText.\n")


def test_show_prints_nothing_if_any_id_is_unknown(mem, capsys):
    _, out, _ = run(capsys, "new", "note", "--title", "A note")
    code, out, err = run(capsys, "show", created_id(out), "N-000000")
    assert code == 1 and out == "" and "no entry" in err


def test_set_summary_and_keywords(mem, capsys):
    _, out, _ = run(capsys, "new", "decision", "--title", "Use files")
    d = created_id(out)
    code, out, _ = run(capsys, "set", d, "--summary", "One file each", "--keywords", "db,storage")
    assert code == 0 and "summary, keywords" in out
    entry = Store(mem).find(d)
    assert (entry.summary, entry.keywords, entry.status) == ("One file each", ["db", "storage"], "accepted")
    assert run(capsys, "set", d)[0] == 1


# --- archive ----------------------------------------------------------------


def test_archive_moves_inactive_entries_and_keeps_them_findable(mem, capsys):
    _, out, _ = run(capsys, "new", "decision", "--title", "Old cache plan")
    old = created_id(out)
    _, out, _ = run(capsys, "new", "decision", "--title", "New cache plan", "--supersedes", old)
    new = created_id(out)
    _, out, _ = run(capsys, "new", "reminder", "--action", "Done thing")
    run(capsys, "done", created_id(out))

    code, _, err = run(capsys, "archive", new)
    assert code == 1 and "only settled or replaced" in err
    code, out, _ = run(capsys, "archive", "--inactive")
    assert code == 0 and out.count("Archived") == 2
    archived = mem / ".memory" / "archive" / "decisions"
    assert [p.name.split("-old")[0] for p in archived.iterdir()] == [old]
    assert run(capsys, "archive", "--inactive")[1] == "Nothing to archive.\n"

    _, out, _ = run(capsys, "recall", "cache")
    assert new in out and old not in out
    _, out, _ = run(capsys, "recall", "cache", "--all")
    assert old in out
    assert run(capsys, "show", old)[0] == 0
    assert run(capsys, "check")[0] == 0

    code, out, _ = run(capsys, "archive", "--restore", old)
    assert code == 0 and (mem / ".memory" / "decisions").joinpath(Store(mem).find(old).path.name).exists()


def test_archived_entry_made_active_is_flagged(mem, capsys):
    _, out, _ = run(capsys, "new", "question", "--text", "Dropped?")
    q = created_id(out)
    run(capsys, "set", q, "--status", "dropped")
    run(capsys, "archive", q)
    _, _, err = run(capsys, "set", q, "--status", "open")
    assert "archive --restore" in err
    code, out, _ = run(capsys, "check")
    assert code == 1 and "is open but archived" in out


def test_archive_link_rot_is_not_a_problem(mem, capsys):
    _, out, _ = run(capsys, "new", "note", "--title", "Old", "--links", "src/gone.py")
    n = created_id(out)
    run(capsys, "set", n, "--status", "archived")
    assert run(capsys, "check")[0] == 1
    run(capsys, "archive", n)
    assert run(capsys, "check")[0] == 0


def test_changes_reports_archive_moves(mem, capsys):
    _, out, _ = run(capsys, "new", "reminder", "--action", "Old chore")
    r = created_id(out)
    run(capsys, "done", r)
    run_git(mem, "add", "-A")
    run_git(mem, "commit", "-q", "-m", "base")
    run_git(mem, "checkout", "-q", "-b", "feature/x")
    run(capsys, "archive", r)
    _, out, _ = run(capsys, "changes")
    assert out.startswith("archived reminder") and "deleted" not in out
    _, out, _ = run(capsys, "changes", "--markdown")
    assert out == "### Project memory\n\nArchived 1 entry.\n"
    run_git(mem, "add", "-A")
    run_git(mem, "commit", "-q", "-m", "archive")
    _, out, _ = run(capsys, "changes")
    assert out.startswith("archived reminder")


def test_dream_prints_real_commands_and_changes_nothing(mem, capsys):
    run(capsys, "new", "decision", "--title", "Use files", "--tags", "storage", "--links", "src/a.py")
    run(capsys, "new", "learning", "--title", "Mocks hid conflicts", "--tags", "testing")
    before = sorted(p.read_bytes() for p in Store(mem).entry_files())
    code, out, _ = run(capsys, "dream")
    assert code == 0
    assert "mneme new decision --title ... --context ... --decision ... --consequences ..." in out
    assert "mneme new concept --term ... --definition ... --notes ..." in out
    assert "Use files" in out and "Mocks hid conflicts" in out
    _, out, _ = run(capsys, "dream", "--tag", "storage")
    assert "Use files" in out and "Mocks hid conflicts" not in out
    _, out, _ = run(capsys, "dream", "--path", "src/a.py")
    assert "Use files" in out and "Mocks hid conflicts" not in out
    assert sorted(p.read_bytes() for p in Store(mem).entry_files()) == before


# --- handover and brief -----------------------------------------------------


def test_handover_on_slash_branch(mem, capsys):
    run_git(mem, "checkout", "-q", "-b", "feature/auth")
    code, out, _ = run(capsys, "handover", "--summary", "Half done", "--next", "Logout")
    assert code == 0
    assert ".memory/handover/feature--auth.md" in out
    handover = Store(mem).load_handover("feature/auth")
    assert "## Next\n\nLogout" in handover.body
    assert "Blockers" not in handover.body


def test_brief_is_bounded(mem, capsys):
    for i in range(30):
        run(capsys, "new", "question", "--text", f"Question {i}?")
        run(capsys, "new", "decision", "--title", f"Decision {i}")
    run(capsys, "handover", "--summary", "Line\n" * 100)
    code, out, _ = run(capsys, "brief")
    assert code == 0
    assert len(out.splitlines()) <= 50
    assert "Open questions (30):" in out
    assert "(+25 more: mneme list question)" in out
    assert "Recent decisions (3 of 30):" in out
    assert "Decision 29" in out and "Decision 0 " not in out
    assert "more lines in .memory/handover/main.md" in out


def test_brief_hides_settled_and_shows_branch_and_markers(mem, capsys):
    _, out, _ = run(capsys, "new", "question", "--text", "Settled?")
    run(capsys, "resolve", created_id(out), "--answer", "yes")
    run(capsys, "handover", "--summary", "Main is fine")
    (mem / "specs").mkdir()
    (mem / "specs" / "spec.md").write_text("- FR-1 [NEEDS CLARIFICATION: which IdP?]\n", encoding="utf-8")
    run_git(mem, "add", "-A")
    run_git(mem, "commit", "-q", "-m", "memory")
    run_git(mem, "checkout", "-q", "-b", "feature/x")
    run(capsys, "new", "learning", "--title", "Found out")
    _, out, _ = run(capsys, "brief")
    assert "Settled?" not in out
    assert "Handover for feature/x: none yet" in out
    assert "Main (main) handover: Main is fine" in out
    assert "This branch so far: 1 learning" in out
    assert "specs/spec.md:1 [NEEDS CLARIFICATION: which IdP?]" in out


def test_brief_reports_problems(mem, capsys):
    bad = mem / ".memory" / "decisions" / "D-ffffff-bad.md"
    bad.parent.mkdir()
    bad.write_text("garbage", encoding="utf-8")
    _, out, _ = run(capsys, "brief")
    assert "! 1 problem in .memory/: run `mneme check`" in out


# --- recall, list -----------------------------------------------------------


def test_recall_ranks_and_filters(mem, capsys):
    run(capsys, "new", "decision", "--title", "Session tokens", "--context", "about auth")
    run(capsys, "new", "decision", "--title", "Authentication via OIDC")
    run(capsys, "new", "note", "--title", "Unrelated")
    _, out, _ = run(capsys, "new", "question", "--text", "Auth for admins?")
    run(capsys, "resolve", created_id(out), "--answer", "same")
    _, out, _ = run(capsys, "recall", "auth")
    lines = out.splitlines()
    assert "Authentication via OIDC" in lines[0]
    assert "Session tokens" in lines[1]
    assert len(lines) == 2
    _, out, _ = run(capsys, "recall", "auth", "--all")
    assert "Auth for admins?" in out
    _, out, _ = run(capsys, "recall", "auth", "--type", "question")
    assert "Nothing found" in out


def test_recall_stems_and_uses_keywords(mem, capsys):
    run(capsys, "new", "decision", "--title", "Editing one entry on two branches conflicts")
    run(capsys, "new", "decision", "--title", "Generate nothing", "--keywords", "database",
        "--decision", "No SQLite index.")
    _, out, _ = run(capsys, "recall", "conflict")
    assert "conflicts" in out
    _, out, _ = run(capsys, "recall", "databases")
    assert out.splitlines() == [out.splitlines()[0], "    No SQLite index."]
    assert "Generate nothing" in out


def test_recall_partial_matches_are_labelled(mem, capsys):
    run(capsys, "new", "decision", "--title", "Merging handovers", "--summary", "Each branch has one")
    run(capsys, "new", "note", "--title", "Unrelated")
    _, out, _ = run(capsys, "recall", "merge", "conflict")
    lines = out.splitlines()
    assert lines[0] == "No entry has every word. Closest partial matches:"
    assert "Merging handovers  (no: conflict)" in lines[1]
    assert lines[2] == "    Each branch has one"
    assert len(lines) == 3


def test_recall_ignores_stopwords_and_hides_default_status(mem, capsys):
    run(capsys, "new", "question", "--text", "Which identity provider?")
    _, out, _ = run(capsys, "recall", "what", "is", "the", "identity", "provider")
    assert out.splitlines()[0].endswith("Which identity provider?")


def test_recall_by_path(mem, capsys, monkeypatch):
    run(capsys, "new", "decision", "--title", "Dir level", "--links", "src/auth/")
    run(capsys, "new", "decision", "--title", "File level", "--links", "src/auth/session.py#L10")
    run(capsys, "new", "decision", "--title", "Elsewhere", "--links", "src/db.py,https://x.org/a")
    _, out, _ = run(capsys, "recall", "--path", "src/auth/session.py")
    assert "Dir level" in out and "File level" in out and "Elsewhere" not in out
    _, out, _ = run(capsys, "recall", "--path", "src/auth")
    assert "File level" in out
    (mem / "src" / "auth").mkdir(parents=True)
    monkeypatch.chdir(mem / "src" / "auth")
    _, out, _ = run(capsys, "recall", "--path", "session.py", "file")
    assert len(out.splitlines()) == 1 and "File level" in out


def test_recall_needs_input(mem, capsys):
    assert run(capsys, "recall")[0] == 1


def test_recall_limit(mem, capsys):
    for i in range(5):
        run(capsys, "new", "note", "--title", f"cache note {i}")
    _, out, _ = run(capsys, "recall", "cache", "--limit", "2")
    assert len(out.splitlines()) == 3
    assert "(+3 more" in out


def test_list(mem, capsys):
    run(capsys, "new", "reminder", "--action", "first")
    _, out, _ = run(capsys, "new", "reminder", "--action", "second")
    run(capsys, "done", created_id(out))
    _, out, _ = run(capsys, "list", "reminder")
    assert "first" in out and "second" not in out
    _, out, _ = run(capsys, "list", "reminder", "--status", "done")
    assert "second" in out and "first" not in out
    _, out, _ = run(capsys, "list", "reminder", "--all")
    assert out.index("second") < out.index("first")


# --- changes ----------------------------------------------------------------


def test_changes(mem, capsys):
    _, out, _ = run(capsys, "new", "question", "--text", "Base question?")
    base_q = created_id(out)
    run_git(mem, "add", "-A")
    run_git(mem, "commit", "-q", "-m", "base")
    code, _, err = run(capsys, "changes")
    assert code == 1 and "--base" in err

    run_git(mem, "checkout", "-q", "-b", "feature/x")
    run(capsys, "new", "decision", "--title", "Committed decision")
    run_git(mem, "add", "-A")
    run_git(mem, "commit", "-q", "-m", "x")
    run(capsys, "new", "learning", "--title", "Uncommitted learning")
    run(capsys, "new", "question", "--text", "Still open?")
    run(capsys, "resolve", base_q, "--answer", "Yes")

    code, out, _ = run(capsys, "changes")
    assert code == 0
    assert "added    decision  " in out and "Committed decision" in out
    assert "Uncommitted learning" in out
    assert "changed  question" in out and "Base question?" in out

    _, out, _ = run(capsys, "changes", "--markdown")
    assert out.startswith("### Project memory")
    assert "**Decisions**\n- `D-" in out
    assert "**Still open**" in out and "Still open?" in out
    assert "**Questions settled**" in out and "Base question? (resolved)" in out


def test_changes_unknown_base(mem, capsys):
    run_git(mem, "checkout", "-q", "-b", "feature/x")
    code, _, err = run(capsys, "changes", "--base", "nope")
    assert code == 1 and "not found" in err


# --- check ------------------------------------------------------------------


def test_check_clean(mem, capsys):
    run(capsys, "new", "decision", "--title", "x")
    code, out, _ = run(capsys, "check")
    assert code == 0 and "OK: 1 entries" in out


def test_check_reports_problems(mem, capsys):
    (mem / "specs").mkdir()
    (mem / "specs" / "spec.md").write_text("# Spec\n\n## Login flow\n\n- **FR-002**: x\n", encoding="utf-8")
    run(capsys, "new", "decision", "--title", "Good links",
        "--links", "specs/spec.md#login-flow,specs/spec.md#fr-002,https://example.com/#x,specs/")
    run(capsys, "new", "decision", "--title", "Bad links",
        "--links", "specs/missing.md,specs/spec.md#nope")
    store = Store(mem)
    entries = store.load().entries
    bad = next(e for e in entries if e.title == "Bad links")
    bad.supersedes = ["D-000000"]
    store.save(bad)
    (mem / ".memory" / "decisions" / "D-ffffff-broken.md").write_text("garbage", encoding="utf-8")
    copy = mem / ".memory" / "decisions" / "renamed.md"
    copy.write_text(bad.path.read_text(encoding="utf-8"), encoding="utf-8")
    (mem / ".memory" / "handover").mkdir()
    (mem / ".memory" / "handover" / "feature--old.md").write_text(
        "---\nbranch: feature/old\nupdated: 2026-11-02T10:00:00Z\n---\n", encoding="utf-8")

    code, out, _ = run(capsys, "check")
    assert code == 1
    assert "link target not found: specs/missing.md" in out
    assert "anchor not found: specs/spec.md#nope" in out
    assert "Good links" not in out and "login-flow" not in out and "fr-002" not in out
    assert "supersedes unknown entry D-000000" in out
    assert "D-ffffff-broken.md: missing frontmatter" in out
    assert f"duplicate id {bad.id}" in out
    assert "renamed.md: filename does not start with id" in out
    assert "feature--old.md: handover from a merged branch" in out


def test_check_ignores_other_handovers_off_main(mem, capsys):
    run_git(mem, "checkout", "-q", "-b", "feature/x")
    run(capsys, "handover", "--summary", "x", "--branch", "feature/y")
    assert run(capsys, "check")[0] == 0


# --- init -------------------------------------------------------------------


def test_init_creates_config_once(mem, capsys):
    config = mem / ".memory" / "config.toml"
    assert config.is_file()
    config.write_text('main_branch = "trunk"\n', encoding="utf-8")
    _, out, _ = run(capsys, "init")
    assert "already set up" in out
    assert config.read_text(encoding="utf-8") == 'main_branch = "trunk"\n'


def test_init_outside_git(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert (tmp_path / ".memory" / "config.toml").is_file()


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_write_agents_keeps_surrounding_text_and_is_idempotent(mem, capsys, newline):
    agents = mem / "AGENTS.md"
    before, after = f"# Project{newline}{newline}Intro.{newline}", f"{newline}## Later{newline}Kept.{newline}"
    agents.write_bytes(before.encode())
    assert run(capsys, "init", "--write-agents")[0] == 0
    text = agents.read_bytes().decode()
    assert text.startswith(before)
    assert text.count(BLOCK_START) == 1
    # Text added after the block survives a refresh.
    agents.write_bytes((text + after).encode())
    once = agents.read_bytes()
    _, out, _ = run(capsys, "init", "--write-agents")
    assert "already up to date" in out
    assert agents.read_bytes() == once
    assert once.decode().endswith(after)
    if newline == "\r\n":
        assert b"\n" not in once.replace(b"\r\n", b"")

    # An outdated block is replaced in place.
    stale = once.decode()
    start, end = stale.index(BLOCK_START), stale.index(BLOCK_END) + len(BLOCK_END)
    agents.write_bytes((stale[:start] + f"{BLOCK_START}{newline}old{newline}{BLOCK_END}" + stale[end:]).encode())
    _, out, _ = run(capsys, "init", "--write-agents")
    assert "updated AGENTS.md" in out
    assert agents.read_bytes() == once


def test_write_agents_refuses_half_block(mem, capsys):
    (mem / "AGENTS.md").write_text(f"x\n{BLOCK_START}\nno end\n", encoding="utf-8")
    code, _, err = run(capsys, "init", "--write-agents")
    assert code == 1 and "fix it by hand" in err


def test_agents_block_stays_small_and_skill_has_details(mem, capsys):
    run(capsys, "init", "--write-agents", "--claude")
    block = (mem / "AGENTS.md").read_text(encoding="utf-8")
    # The block loads in every session; details belong in the skill and --help.
    assert len(block.splitlines()) <= 14
    skill = (mem / ".claude" / "skills" / "mneme" / "SKILL.md").read_text(encoding="utf-8")
    assert "--keywords" in skill and "mneme new decision --title" in skill


def test_claude_skill_not_overwritten_without_force(mem, capsys):
    run(capsys, "init", "--claude")
    skill = mem / ".claude" / "skills" / "mneme" / "SKILL.md"
    assert skill.read_text(encoding="utf-8").startswith("---\nname: mneme\n")
    skill.write_text("mine", encoding="utf-8")
    _, out, _ = run(capsys, "init", "--claude")
    assert "kept existing" in out and skill.read_text(encoding="utf-8") == "mine"
    run(capsys, "init", "--claude", "--force")
    assert skill.read_text(encoding="utf-8") != "mine"


def test_hide_in_diffs_is_idempotent(mem, capsys):
    attrs = mem / ".gitattributes"
    attrs.write_text("* text=auto", encoding="utf-8")
    run(capsys, "init", "--hide-in-diffs")
    run(capsys, "init", "--hide-in-diffs")
    assert attrs.read_text(encoding="utf-8") == f"* text=auto\n{GITATTRIBUTES_LINE}\n"
