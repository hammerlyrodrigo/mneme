import pytest

from conftest import make
from mneme.recall import query_terms, recall, stem


@pytest.mark.parametrize(
    "a, b",
    [
        ("conflict", "conflicts"),
        ("conflict", "conflicted"),
        ("merge", "merging"),
        ("merge", "merged"),
        ("database", "databases"),
        ("entry", "entries"),
        ("match", "matches"),
    ],
)
def test_word_forms_share_a_stem(a, b):
    assert stem(a) == stem(b)


def test_short_words_and_double_s_are_kept():
    assert (stem("is"), stem("as"), stem("class")) == ("is", "as", "class")


def test_query_terms_drop_stopwords_unless_nothing_is_left():
    assert query_terms("why do we merge Conflicts") == {"merg": "merge", "conflict": "conflicts"}
    assert query_terms("what is") == {"what": "what", "is": "is"}


def test_full_matches_hide_partial_ones():
    both = make(title="Merge conflicts")
    one = make(title="Merge queue")
    result = recall([both, one], "merge conflict")
    assert (result.entries, result.partial) == ([both], False)


def test_rare_term_outranks_common_one():
    common = [make(title=f"Storage note {i}") for i in range(5)]
    rare = make(title="Storage of sqlite files")
    result = recall([*common, rare], "storage sqlite")
    assert result.entries == [rare]
    result = recall(common + [make(title="Only sqlite")], "storage sqlite")
    assert result.partial
    assert result.entries[0].title == "Only sqlite"
    assert result.hits[0].missing == ["storage"]


def test_title_beats_summary_beats_body():
    body = make(title="A", body="## Decision\n\nCaching.\n")
    summary = make(title="B", summary="Caching here")
    title = make(title="Caching")
    assert recall([body, summary, title], "caching").entries == [title, summary, body]
