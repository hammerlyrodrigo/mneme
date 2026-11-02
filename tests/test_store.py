import pytest

from conftest import make
from mneme.model import FormatError
from mneme.store import Ambiguous, Handover, NotFound


def test_create_and_load(store):
    entry = store.create(make(title="Use one file per entry", tags=["storage"]))
    assert entry.id.startswith("D-")
    assert entry.path == store.memory_dir / "decisions" / f"{entry.id}-use-one-file-per-entry.md"
    loaded = store.load()
    assert loaded.problems == []
    assert loaded.entries == [entry]


def test_files_are_written_with_lf(store):
    entry = store.create(make(body="## Context\n\nWhy.\n"))
    assert b"\r\n" not in entry.path.read_bytes()


def test_invalid_entry_is_not_written(store):
    with pytest.raises(FormatError):
        store.create(make(status="open"))
    assert store.entry_files() == []


def test_explicit_id_collision_refused(store):
    store.create(make(id="D-abcdef"))
    with pytest.raises(FileExistsError):
        store.create(make(id="D-abcdef", title="Other"))


def test_generated_id_skips_ids_of_corrupt_files(store, monkeypatch):
    bad = store.type_dir("decision") / "D-aaaaaa-broken.md"
    bad.parent.mkdir(parents=True)
    bad.write_text("not an entry", encoding="utf-8")
    values = iter(["aaaaaa", "bbbbbb"])
    monkeypatch.setattr("mneme.model.secrets.token_hex", lambda n: next(values))
    assert store.create(make()).id == "D-bbbbbb"


def test_corrupt_file_is_reported_not_fatal(store):
    good = store.create(make())
    bad = store.type_dir("decision") / "D-ffffff-bad.md"
    bad.write_text("---\nid: D-ffffff\n---\n", encoding="utf-8")
    loaded = store.load()
    assert loaded.entries == [good]
    assert len(loaded.problems) == 1
    assert loaded.problems[0].path == bad
    assert "missing frontmatter keys" in loaded.problems[0].message


def test_entry_in_wrong_directory_is_reported(store):
    entry = store.create(make())
    moved = store.type_dir("note") / entry.path.name
    moved.parent.mkdir(parents=True)
    entry.path.rename(moved)
    loaded = store.load()
    assert [e.id for e in loaded.entries] == [entry.id]
    assert "belongs in decisions/" in loaded.problems[0].message


def test_load_sorts_by_utc_time(store):
    late = store.create(make(title="late", created="2026-11-02T06:00:00Z"))
    early = store.create(make(title="early", created="2026-11-02T10:00:00+05:00"))
    assert [e.id for e in store.load().entries] == [early.id, late.id]


def test_find_by_prefix(store):
    a = store.create(make(id="D-abc123"))
    b = store.create(make(id="D-abd456", title="Other"))
    assert store.find("d-abc").id == a.id
    assert store.find("D-abd456").id == b.id
    with pytest.raises(Ambiguous, match="D-abc123, D-abd456"):
        store.find("D-ab")
    with pytest.raises(NotFound):
        store.find("Q0099")


def test_find_exact_beats_prefix(store):
    store.create(make(id="D0001"))
    store.create(make(id="D00010", title="Other"))
    assert store.find("D0001").id == "D0001"
    assert store.find("D00010").id == "D00010"


def test_save_keeps_filename_and_sets_updated(store):
    entry = store.create(make(entry_type="question", title="Why?"))
    path = entry.path
    entry.title = "Why, really?"
    entry.status = "resolved"
    entry.set_section("Answer", "Because.")
    store.save(entry)
    assert entry.path == path
    again = store.find(entry.id)
    assert again.status == "resolved"
    assert again.updated.endswith("Z")
    assert again.section("Answer") == "Because."


def test_save_refuses_invalid_and_leaves_file(store):
    entry = store.create(make())
    before = entry.path.read_text(encoding="utf-8")
    entry.status = "bogus"
    with pytest.raises(FormatError):
        store.save(entry)
    assert entry.path.read_text(encoding="utf-8") == before


def test_handover_per_branch(store):
    path = store.write_handover(
        Handover(branch="feature/auth", updated="2026-11-02T10:00:00Z", author="ana",
                 body="## Summary\n\nHalf done.\n")
    )
    assert path.name == "feature--auth.md"
    handover = store.load_handover("feature/auth")
    assert handover.branch == "feature/auth"
    assert handover.author == "ana"
    assert "Half done." in handover.body
    assert store.load_handover("main") is None
    store.write_handover(Handover(branch="feature/auth", updated="2026-11-03T10:00:00Z"))
    assert store.load_handover("feature/auth").body == ""
    assert store.handover_files() == [path]
