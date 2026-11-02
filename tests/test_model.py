from datetime import timezone

import pytest

from mneme.model import (
    Entry,
    FormatError,
    branch_filename,
    dump_frontmatter,
    is_valid_id,
    new_id,
    parse_ts,
    slugify,
    split_document,
)

TRICKY = [
    "plain",
    "",
    " leading space",
    "key: value",
    "has # hash",
    "#starts with hash",
    "[not a list]",
    "true",
    "No",
    'say "hi"',
    "it's",
    "ends with colon:",
    "ünïcödé ✓",
    "- dash",
    "a, b",
    "back\\slash",
    "tab\there",
]


@pytest.mark.parametrize("value", TRICKY)
def test_scalar_round_trip(value):
    meta, _ = split_document(dump_frontmatter({"k": value}))
    assert meta == {"k": value}


def test_list_round_trip():
    items = ["a", "b, c", "specs/003-auth/spec.md#fr-2", "it's", 'q"uote', " x"]
    meta, _ = split_document(dump_frontmatter({"links": items, "empty": []}))
    assert meta == {"links": items, "empty": []}


def test_hand_written_frontmatter():
    text = (
        "---\n"
        "# a comment\n"
        "title: 'It''s fine'\n"
        'note: "line\\nbreak"\n'
        "tags: [a, 'b c' , \"d\"]\n"
        "url: http://example.com/x#y\n"
        "---\n"
        "\n"
        "Body\n"
    )
    meta, body = split_document(text)
    assert meta == {
        "title": "It's fine",
        "note": "line\nbreak",
        "tags": ["a", "b c", "d"],
        "url": "http://example.com/x#y",
    }
    assert body == "Body\n"


def test_crlf_and_bom_accepted():
    meta, body = split_document("﻿---\r\nid: D-abcdef\r\n---\r\n\r\nText\r\n")
    assert meta == {"id": "D-abcdef"}
    assert body == "Text\n"


@pytest.mark.parametrize(
    "text",
    [
        "no frontmatter\n",
        "---\nid: x\n",
        "---\nnested:\n  key: v\n---\n",
        "---\nid: x\nid: y\n---\n",
        "---\nmap: {a: 1}\n---\n",
        "---\nlist: [a, b\n---\n",
        "---\nlist: [a, , b]\n---\n",
        '---\nq: "open\n---\n',
        "---\nq: 'a' trailing\n---\n",
        "---\njust text\n---\n",
    ],
)
def test_bad_frontmatter_rejected(text):
    with pytest.raises(FormatError):
        split_document(text)


def test_entry_round_trip_keeps_unknown_keys_and_body():
    text = (
        "---\n"
        "id: D-7f3a2c\n"
        "type: decision\n"
        "title: Use one file per entry\n"
        "status: accepted\n"
        "created: 2026-11-02T14:03:11Z\n"
        "tags: [storage]\n"
        "deciders: [ana, bo]\n"
        "---\n"
        "\n"
        "## Context\n\nWhy.\n\n## Decision\n\nWhat.\n"
    )
    entry = Entry.from_text(text)
    assert entry.extra == {"deciders": ["ana", "bo"]}
    assert entry.section("Decision") == "What."
    assert Entry.from_text(entry.to_text()) == entry
    assert entry.to_text() == text


def test_set_section_orders_known_sections():
    entry = Entry(id="Q-abcdef", type="question", title="Why?", status="open",
                  created="2026-11-02T10:00:00Z", body="Intro\n\n## Question\n\nWhy?\n")
    entry.set_section("Answer", "Because.")
    assert entry.body == "Intro\n\n## Question\n\nWhy?\n\n## Answer\n\nBecause.\n"
    entry.set_section("Answer", "Changed.")
    assert entry.section("Answer") == "Changed."


def test_headings_inside_code_fences_are_not_sections():
    entry = Entry(id="N-abcdef", type="note", title="x", status="active",
                  created="2026-11-02T10:00:00Z", body="```\n## not a heading\n```\n")
    assert entry.sections() == {}


@pytest.mark.parametrize(
    "change, message",
    [
        ({"type": "goal"}, "unknown type"),
        ({"id": "D-zz"}, "bad id"),
        ({"id": "Q-abcdef"}, "does not match type"),
        ({"status": "open"}, "bad status"),
        ({"title": " "}, "empty title"),
        ({"title": "two\nlines"}, "one line"),
        ({"created": "2026-11-02T10:00:00"}, "time zone"),
        ({"supersedes": ["nope"]}, "supersedes"),
    ],
)
def test_validate(change, message):
    fields = dict(id="D-abcdef", type="decision", title="t", status="accepted",
                  created="2026-11-02T10:00:00Z")
    fields.update(change)
    with pytest.raises(FormatError, match=message):
        Entry(**fields).validate()


def test_missing_required_keys():
    with pytest.raises(FormatError, match="missing frontmatter keys: status, created"):
        Entry.from_text("---\nid: D-abcdef\ntype: decision\ntitle: t\n---\n")


def test_ids():
    assert is_valid_id(new_id("decision"))
    assert new_id("question").startswith("Q-")
    for legacy in ("D0001", "R-261102-c1d3"):
        assert is_valid_id(legacy)
    for bad in ("D-ABCDEF", "d-abcdef", "D-abcde", "X", "D-abcdef-slug"):
        assert not is_valid_id(bad)


def test_new_id_avoids_taken(monkeypatch):
    values = iter(["aaaaaa", "bbbbbb"])
    monkeypatch.setattr("mneme.model.secrets.token_hex", lambda n: next(values))
    assert new_id("note", {"N-aaaaaa"}) == "N-bbbbbb"


def test_timestamps_sort_in_utc():
    stamps = ["2026-11-02T06:00:00Z", "2026-11-02T10:00:00+05:00", "2026-11-02T01:00:00-03:00"]
    # Sorted as strings this would be 01:00, 06:00, 10:00; in UTC it is 04:00, 05:00, 06:00.
    ordered = sorted(stamps, key=parse_ts)
    assert ordered == ["2026-11-02T01:00:00-03:00", "2026-11-02T10:00:00+05:00",
                       "2026-11-02T06:00:00Z"]
    assert parse_ts(ordered[0]).tzinfo == timezone.utc


def test_slugify():
    assert slugify("Use SQLite for saves!") == "use-sqlite-for-saves"
    assert slugify("Ça marche — très bien") == "ca-marche-tres-bien"
    assert slugify("???") == "untitled"
    assert len(slugify("word " * 40)) <= 50


def test_branch_filename():
    assert branch_filename("feature/auth/login") == "feature--auth--login.md"
