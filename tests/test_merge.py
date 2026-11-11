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
