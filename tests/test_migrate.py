"""migrate, against a log shaped exactly like mneme v0's writers produce."""

import json

import pytest

from mneme.cli import main
from mneme.migrate import MigrateError, fold, plan_migration
from mneme.store import Store


def create(id, type, title, fields, created="2026-10-01T09:00:00+01:00", **kw):
    record = {"op": "create", "id": id, "type": type, "created_at": created, "updated_at": created,
              "title": title, "status": kw.pop("status", None), "tags": kw.pop("tags", []),
              "links": kw.pop("links", []), "author": kw.pop("author", "ana"), "branch": "main",
              "consolidates": kw.pop("consolidates", []), "supersedes": kw.pop("supersedes", None),
              "fields": fields}
    record.update(kw)
    return record


def patch(target, when="2026-10-02T10:00:00+01:00", **fields):
    return {"op": "patch", "target_id": target, "updated_at": when, "author": "ana",
            "branch": "feature/x", "patch": fields}


LOG = [
    create("D-261001-aaaa", "decision", "Use JSONL", {"context": "c", "decision": "One log", "consequences": ""},
           status="accepted", tags=["storage"], links=["scripts/memory.py", "Q-261001-cccc"]),
    create("D-261002-bbbb", "decision", "Use files", {"context": "", "decision": "One file each",
                                                      "consequences": "x"},
           created="2026-10-02T09:00:00-03:00", status="accepted", supersedes="D-261001-aaaa"),
    patch("D-261001-aaaa", status="superseded", superseded_by="D-261002-bbbb"),
    create("Q-261001-cccc", "question", "Which store?", {"question": "Which store?"}, status="open"),
    patch("Q-261001-cccc", status="resolved", fields={"answer": "Files.", "resolved_by": "D-261002-bbbb"}),
    create("L0001", "learning", "Mocks lie", {"tried": "mocks", "result": "missed", "takeaway": "use git"},
           status="active"),
    create("L0002", "learning", "Real git works", {"tried": "", "result": "", "takeaway": "use git"},
           status="active", consolidates=["L0001"]),
    patch("L0001", status="consolidated", consolidated_into="L0002"),
    create("L0003", "learning", "Old learning", {"takeaway": "gone"}, status="active"),
    patch("L0003", status="stale"),
    create("D0009", "decision", "Old decision", {"decision": "gone"}, status="accepted"),
    patch("D0009", status="obsolete", reason="code removed"),
    create("R-261001-dddd", "reminder", "Bump deps", {"trigger": "after v1", "action": "Bump deps"},
           status="pending"),
    patch("R-261001-dddd", status="done", fields={"note": "Bumped."}),
    create("C-261001-eeee", "concept", "Entry", {"term": "Entry", "definition": "A record", "notes": ""},
           status="active"),
    create("N-261001-ffff", "note", "Scratch", {"body": "Free text."}, status="active"),
    patch("X-999999-zzzz", status="done"),
    create("H-261001-0001", "handover", "Session handover",
           {"summary": "Old", "done": "", "next": "", "blockers": ""}, status="active"),
    create("H-261003-0002", "handover", "Session handover",
           {"summary": "Newest", "done": "Stuff", "next": "1. More", "blockers": ""},
           created="2026-10-03T09:00:00+00:00", status="active"),
]


def write_log(tmp_path, records=LOG):
    path = tmp_path / "entries.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n\n", encoding="utf-8")
    return path


def test_fold_replays_patches_like_v0(tmp_path):
    records, notes = fold(write_log(tmp_path).read_text(encoding="utf-8").splitlines())
    by_id = {r["id"]: r for r in records}
    assert len(records) == 12
    assert by_id["Q-261001-cccc"]["status"] == "resolved"
    assert by_id["Q-261001-cccc"]["fields"] == {"question": "Which store?", "answer": "Files.",
                                                "resolved_by": "D-261002-bbbb"}
    assert by_id["Q-261001-cccc"]["updated_at"] == "2026-10-02T10:00:00+01:00"
    assert any("X-999999-zzzz" in n for n in notes)


def test_fold_last_create_wins_and_is_reported():
    lines = [json.dumps(create("N0001", "note", "First", {})), json.dumps(create("N0001", "note", "Second", {}))]
    records, notes = fold(lines)
    assert [r["title"] for r in records] == ["Second"]
    assert any("more than once" in n and "N0001" in n for n in notes)


@pytest.mark.parametrize("line", ["not json", "[1]", '{"op": "rename"}', '{"op": "create"}'])
def test_fold_rejects_bad_lines(line):
    with pytest.raises(MigrateError, match="line 1"):
        fold([line])


def test_plan_maps_entries(tmp_path):
    plan = plan_migration(write_log(tmp_path))
    assert plan.problems == []
    by_id = {e.id: e for e in plan.entries}
    assert len(by_id) == 10

    old, new = by_id["D-261001-aaaa"], by_id["D-261002-bbbb"]
    assert (old.status, new.supersedes) == ("superseded", ["D-261001-aaaa"])
    assert old.created == "2026-10-01T08:00:00Z" and new.created == "2026-10-02T12:00:00Z"
    assert old.updated == "2026-10-02T09:00:00Z" and new.updated == ""
    assert (old.links, old.extra["related"]) == (["scripts/memory.py"], ["Q-261001-cccc"])
    assert "superseded_by" not in old.extra
    assert (old.author, old.branch, old.agent, old.tags) == ("ana", "", "", ["storage"])
    assert old.section("Decision") == "One log" and "Consequences" not in old.sections()

    q = by_id["Q-261001-cccc"]
    assert (q.status, q.resolved_by, q.section("Answer")) == ("resolved", "D-261002-bbbb", "Files.")
    assert "Question" not in q.sections()

    assert by_id["L0001"].status == "superseded"
    assert by_id["L0002"].supersedes == ["L0001"]
    assert by_id["L0003"].status == "archived"
    assert (by_id["D0009"].status, by_id["D0009"].extra["reason"]) == ("deprecated", "code removed")

    r = by_id["R-261001-dddd"]
    assert (r.status, r.section("Trigger"), r.section("Note")) == ("done", "after v1", "Bumped.")
    assert "Action" not in r.sections()
    assert by_id["C-261001-eeee"].section("Definition") == "A record"
    assert by_id["N-261001-ffff"].body == "Free text.\n"

    assert plan.handover.body.startswith("## Summary\n\nNewest")
    assert plan.handovers_dropped == 1
    assert any("1 decision obsolete -> deprecated" in n and "1 learning stale -> archived" in n
               for n in plan.notes)


def test_plan_reports_unmappable_records(tmp_path):
    bad = [create("Q0001", "question", "Q?", {}, status="weird"),
           create("Z0001", "goal", "A goal", {}),
           create("N0001", "note", "Bad time", {}, created="yesterday")]
    plan = plan_migration(write_log(tmp_path, bad))
    assert len(plan.problems) == 3 and plan.entries == []


def test_supersedes_pointing_outside_the_log_is_kept_as_a_note(tmp_path):
    plan = plan_migration(write_log(tmp_path, [create("D0001", "decision", "x", {}, supersedes="D0000")]))
    entry = plan.entries[0]
    assert (entry.supersedes, entry.extra["supersedes_missing"]) == ([], ["D0000"])


def test_cli_migrate_dry_run_then_write_then_rerun(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    main(["init"])
    log = write_log(repo)
    capsys.readouterr()

    assert main(["migrate", "--from", str(log), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Would migrate 10 entries:" in out and "   1 decision deprecated" in out
    assert Store(repo).entry_files() == []

    assert main(["migrate", "--from", str(log)]) == 0
    store = Store(repo)
    assert len(store.load().entries) == 10
    assert store.load().problems == []
    assert "Newest" in store.load_handover("main").body
    assert main(["check"]) == 1  # scripts/memory.py is not in this repo
    assert "scripts/memory.py" in capsys.readouterr().out

    assert main(["migrate", "--from", str(log)]) == 0
    out = capsys.readouterr().out
    assert "10 entries already exist" in out and "Migrated 0 entries" in out
    assert "kept the existing main handover" in out


def test_cli_migrate_writes_nothing_on_a_problem(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    main(["init"])
    log = write_log(repo, LOG + [create("Q0001", "question", "Q?", {}, status="weird")])
    assert main(["migrate", "--from", str(log)]) == 1
    assert "Nothing written" in capsys.readouterr().out
    assert Store(repo).entry_files() == []
