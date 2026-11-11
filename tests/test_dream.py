from conftest import make
from mneme.dream import build_dream, overlap_groups


def corpus():
    return [
        make(entry_type="learning", title="Mocking git hid merge conflicts in tests",
             keywords=["mock", "merge"]),
        make(entry_type="learning", title="Merge tests need real git, not mocks",
             summary="Mocked git missed conflicts", keywords=["mock"]),
        make(title="Store memory as one file per entry", tags=["storage"]),
        make(title="Timestamps are UTC", tags=["format"]),
        make(entry_type="concept", title="Handover", summary="A per-branch checkpoint"),
    ]


def test_near_duplicates_group_and_distinct_entries_do_not():
    entries = corpus()
    groups = overlap_groups(entries)
    assert len(groups) == 1
    group, shared = groups[0]
    assert [e.title for e in group] == [entries[0].title, entries[1].title]
    assert shared == ["conflicts", "git", "merge", "mocking", "tests"]


def test_common_words_do_not_chain_everything():
    entries = [make(title=f"Entry file rule {topic}", tags=["entry"])
               for topic in ("ids", "timestamps", "handover", "links", "status")]
    assert overlap_groups(entries) == []


def test_prompt_has_commands_groups_and_skips_other_types():
    entries = corpus() + [make(entry_type="question", title="Mocking git?"),
                          make(title="Rejected idea", status="rejected")]
    text = build_dream(entries, ["mneme new learning --title ..."], limit=0)
    assert text.startswith("# Consolidate project memory")
    assert "Below are 5 active entries" in text
    assert "mneme new learning --title ..." in text
    assert "## Likely overlaps" in text and "## Other entries" in text
    assert "Mocking git?" not in text and "Rejected idea" not in text
    assert "- learning: active, archived, superseded" in text


def test_limit_keeps_the_newest_and_says_so():
    entries = [make(title=f"Rule {i}", created=f"2026-11-0{i}T10:00:00Z") for i in range(1, 6)]
    text = build_dream(entries, [], limit=2)
    assert "Rule 5" in text and "Rule 4" in text and "Rule 3" not in text
    assert "Only the newest 2 of 5" in text
