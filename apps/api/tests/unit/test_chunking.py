"""Unit tests of [Chunking and passage selection]
(/architecture/rules.md#chunking-and-passage-selection) (`S-ING-04`)."""

from __future__ import annotations

import pytest

from leadradar.core.chunking import (
    fuse_rankings,
    passage_header,
    select_passages,
    split_into_passages,
)

pytestmark = pytest.mark.unit


def test_short_document_is_one_passage_with_no_section() -> None:
    text = "A short job posting text."
    passages = split_into_passages(
        text, [], whole_document_max_chars=8000, chunk_target_chars=1600, chunk_overlap_chars=200
    )
    assert len(passages) == 1
    passage = passages[0]
    assert passage.section is None
    assert passage.char_start == 0
    assert passage.char_end == len(text)
    assert passage.text == text


def test_empty_document_has_no_passages() -> None:
    assert (
        split_into_passages(
            "", [], whole_document_max_chars=10, chunk_target_chars=5, chunk_overlap_chars=1
        )
        == []
    )


def test_long_document_splits_at_section_boundaries_and_carries_section_path() -> None:
    section_a = "Alpha. " * 50  # 350 chars
    section_b = "Beta. " * 50  # 300 chars
    text = section_a + section_b
    sections = [(0, "Intro"), (len(section_a), "Details")]
    passages = split_into_passages(
        text, sections, whole_document_max_chars=100, chunk_target_chars=200, chunk_overlap_chars=20
    )
    assert len(passages) > 1
    assert all(p.section in {"Intro", "Details"} for p in passages)
    # every passage of section A is entirely inside section A's span, and section B's inside B's.
    for p in passages:
        if p.section == "Intro":
            assert p.char_end <= len(section_a)
        else:
            assert p.char_start >= len(section_a)
    # ordinals are contiguous from 0.
    assert [p.ordinal for p in passages] == list(range(len(passages)))


def test_long_document_passages_never_split_inside_a_word() -> None:
    text = ("word " * 400).strip()  # 1999 chars, no punctuation at all
    passages = split_into_passages(
        text, [], whole_document_max_chars=100, chunk_target_chars=50, chunk_overlap_chars=5
    )
    for passage in passages:
        assert not passage.text.startswith(" ")
        # a cut lands on a space boundary (or at the very end), never mid-"word".
        assert passage.char_end == len(text) or text[passage.char_end - 1] == " "


def test_long_document_passages_overlap() -> None:
    text = "Sentence one is here. " * 100
    passages = split_into_passages(
        text, [], whole_document_max_chars=100, chunk_target_chars=300, chunk_overlap_chars=50
    )
    assert len(passages) > 1
    for first, second in zip(passages, passages[1:], strict=False):
        assert second.char_start < first.char_end


def test_passage_header_joins_account_document_section_and_date() -> None:
    header = passage_header(
        account_name="Lufthansa Group",
        document_title="Annual Report 2025",
        section="Strategy › Efficiency",
        date="2026-03-06",
    )
    assert header == "Lufthansa Group · Annual Report 2025 · Strategy › Efficiency · 2026-03-06"


def test_passage_header_without_section() -> None:
    header = passage_header(
        account_name="DHL Group", document_title="Careers", section=None, date="2026-03-06"
    )
    assert header == "DHL Group · Careers · 2026-03-06"


def test_fuse_rankings_sums_reciprocal_rank_and_orders_by_score_then_ordinal() -> None:
    keyword_ranking = [3, 1, 2]
    meaning_ranking = [1, 4]
    fused = fuse_rankings([keyword_ranking, meaning_ranking], candidates=50, rrf_k=60)
    fused_by_ordinal = dict(fused)
    # passage 1 appears in both rankings: 1/(60+2) [keyword rank2] + 1/(60+1) [meaning rank1]
    assert fused_by_ordinal[1] == pytest.approx(1 / 62 + 1 / 61)
    assert fused_by_ordinal[3] == pytest.approx(1 / 61)
    assert [ordinal for ordinal, _score in fused] == [1, 3, 4, 2]


def test_fuse_rankings_only_considers_first_candidates() -> None:
    fused = fuse_rankings([[1, 2, 3, 4]], candidates=2, rrf_k=60)
    assert {ordinal for ordinal, _score in fused} == {1, 2}


def test_select_passages_keeps_every_questions_best_passage_before_a_second() -> None:
    # Question A's best is passage 5 (a low-frequency signal); question B's top two are 1 and 2.
    per_question = {
        "A": [(5, 0.5)],
        "B": [(1, 0.9), (2, 0.8), (3, 0.1)],
    }
    selected = select_passages(per_question, max_passages_per_document=2)
    # Passage 5 (question A's only, best rank 1) and passage 1 (question B's best, rank 1) come
    # before question B's second-ranked passage 2.
    assert set(selected) == {5, 1}


def test_select_passages_caps_at_max_passages_per_document() -> None:
    per_question = {"A": [(1, 0.9), (2, 0.8), (3, 0.7)]}
    selected = select_passages(per_question, max_passages_per_document=2)
    assert selected == [1, 2]
