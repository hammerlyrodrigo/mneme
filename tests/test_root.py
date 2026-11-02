import pytest

from conftest import run_git
from mneme.root import (
    ConfigError,
    RootNotFound,
    current_branch,
    find_root,
    load_config,
    main_branch,
)


def test_root_is_git_toplevel(repo):
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    assert find_root(sub) == repo.resolve()


def test_root_without_git_walks_up_to_memory_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    (tmp_path / "proj" / ".memory").mkdir(parents=True)
    sub = tmp_path / "proj" / "src"
    sub.mkdir()
    assert find_root(sub) == (tmp_path / "proj").resolve()


def test_root_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with pytest.raises(RootNotFound):
        find_root(tmp_path)


def test_current_branch(repo):
    assert current_branch(repo) == "main"
    run_git(repo, "checkout", "-q", "-b", "feature/x")
    assert current_branch(repo) == "feature/x"
    run_git(repo, "checkout", "-q", "--detach")
    assert current_branch(repo) is None


def test_current_branch_on_unborn_branch(tmp_path):
    run_git(tmp_path, "init", "-q", "-b", "trunk")
    assert current_branch(tmp_path) == "trunk"


def test_config_and_main_branch(repo):
    assert main_branch(repo, load_config(repo)) == "main"
    (repo / ".memory").mkdir()
    (repo / ".memory" / "config.toml").write_text(
        'main_branch = "trunk"\nspec_dirs = ["specs"]\ndefault_author = "ana"\n', encoding="utf-8"
    )
    config = load_config(repo)
    assert (config.main_branch, config.spec_dirs, config.default_author) == ("trunk", ["specs"], "ana")
    assert main_branch(repo, config) == "trunk"


def test_main_branch_from_origin_head(repo):
    run_git(repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
    run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop")
    assert main_branch(repo, load_config(repo)) == "develop"


@pytest.mark.parametrize("text", ['main_branch = 3\n', 'spec_dirs = "specs"\n', 'colour = "x"\n', "= broken"])
def test_bad_config(repo, text):
    (repo / ".memory").mkdir()
    (repo / ".memory" / "config.toml").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(repo)
