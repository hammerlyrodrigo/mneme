"""The storage model's promise, checked against real git merges."""

from conftest import make, run_git
from mneme.store import Store


def commit_all(repo, message):
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", message)


def test_new_entries_on_two_branches_merge_cleanly(repo):
    store = Store(repo)
    store.create(make(title="Base decision"))
    commit_all(repo, "base")

    run_git(repo, "checkout", "-q", "-b", "feature/a")
    store.create(make(title="From branch a"))
    store.create(make(entry_type="question", title="Open on a"))
    commit_all(repo, "a")

    run_git(repo, "checkout", "-q", "main")
    store.create(make(title="From main"))
    store.create(make(entry_type="learning", title="Learned on main"))
    commit_all(repo, "main")

    result = run_git(repo, "merge", "--no-edit", "feature/a", check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    loaded = store.load()
    assert loaded.problems == []
    assert sorted(e.title for e in loaded.entries) == [
        "Base decision", "From branch a", "From main", "Learned on main", "Open on a",
    ]


def test_conflicting_status_changes_conflict(repo):
    store = Store(repo)
    question = store.create(make(entry_type="question", title="Which database?"))
    commit_all(repo, "base")

    run_git(repo, "checkout", "-q", "-b", "feature/a")
    entry = store.find(question.id)
    entry.status = "resolved"
    store.save(entry)
    commit_all(repo, "resolve on a")

    run_git(repo, "checkout", "-q", "main")
    entry = store.find(question.id)
    entry.status = "dropped"
    store.save(entry)
    commit_all(repo, "drop on main")

    result = run_git(repo, "merge", "--no-edit", "feature/a", check=False)
    assert result.returncode != 0
    assert "CONFLICT" in result.stdout
    # The conflicted file is reported as a problem rather than crashing the load.
    assert [p.path.name for p in store.load().problems] == [question.path.name]


def test_identical_edits_on_two_branches_merge_cleanly(repo):
    store = Store(repo)
    reminder = store.create(make(entry_type="reminder", title="Bump deps after v1"))
    commit_all(repo, "base")

    for branch in ("feature/a", "feature/b"):
        run_git(repo, "checkout", "-q", "-b", branch, "main")
        entry = store.find(reminder.id)
        entry.status = "done"
        entry.set_section("Note", "Bumped.")
        store.save(entry)
        commit_all(repo, f"done on {branch}")

    run_git(repo, "checkout", "-q", "main")
    for branch in ("feature/a", "feature/b"):
        result = run_git(repo, "merge", "--no-edit", branch, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    assert store.find(reminder.id).status == "done"


def test_archiving_on_main_merges_with_an_edit_on_a_branch(repo):
    store = Store(repo)
    question = store.create(make(entry_type="question", title="Which database?"))
    commit_all(repo, "base")

    run_git(repo, "checkout", "-q", "-b", "feature/a")
    entry = store.find(question.id)
    entry.set_section("Answer", "SQLite.")
    entry.status = "resolved"
    store.save(entry)
    commit_all(repo, "resolve on a")

    run_git(repo, "checkout", "-q", "main")
    entry = store.find(question.id)
    entry.status = "dropped"
    store.save(entry)
    commit_all(repo, "drop on main")
    store.move(store.find(question.id), archived=True)
    commit_all(repo, "archive on main")

    # The status edits still disagree, but in the archived file, not in a second copy.
    result = run_git(repo, "merge", "--no-edit", "feature/a", check=False)
    assert f"Merge conflict in .memory/archive/questions/{question.path.name}" in result.stdout
    assert not list((repo / ".memory" / "questions").glob("*.md"))


def test_archiving_and_an_unrelated_edit_merge_cleanly(repo):
    store = Store(repo)
    question = store.create(make(entry_type="question", title="Which database?", status="dropped"))
    commit_all(repo, "base")

    run_git(repo, "checkout", "-q", "-b", "feature/a")
    entry = store.find(question.id)
    entry.set_section("Answer", "Not needed after all.")
    store.save(entry)
    commit_all(repo, "answer on a")

    run_git(repo, "checkout", "-q", "main")
    store.move(store.find(question.id), archived=True)
    commit_all(repo, "archive on main")

    result = run_git(repo, "merge", "--no-edit", "feature/a", check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    merged = store.find(question.id)
    assert store.is_archived(merged)
    assert merged.section("Answer") == "Not needed after all."


def test_status_change_and_new_entry_merge_cleanly(repo):
    store = Store(repo)
    reminder = store.create(make(entry_type="reminder", title="Bump deps after v1"))
    commit_all(repo, "base")

    run_git(repo, "checkout", "-q", "-b", "feature/a")
    entry = store.find(reminder.id)
    entry.status = "done"
    store.save(entry)
    commit_all(repo, "done on a")

    run_git(repo, "checkout", "-q", "main")
    store.create(make(title="Unrelated"))
    commit_all(repo, "main")

    result = run_git(repo, "merge", "--no-edit", "feature/a", check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert store.find(reminder.id).status == "done"
