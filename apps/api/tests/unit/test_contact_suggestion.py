"""Unit tests of [Contact suggestion](/architecture/rules.md#contact-suggestion) steps 3 to 5:
which of the LLM's candidates become suggestions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from leadradar.core.contact_suggestion import (
    Candidate,
    SuggestionPassage,
    keep_suggestions,
    normalised_name,
)

pytestmark = pytest.mark.unit

_BOARD = SuggestionPassage(
    id="p-board",
    text=(
        "Members of the Board of Management. Dr. Tobias Meyer, Chief Executive Officer. "
        "Melanie Kreis, Chief Financial Officer. Press contact: presse@example.com, "
        "+49 228 182-9944."
    ),
    source_url="https://group.example.com/board",
    document_title="Board of Management",
    published_at=datetime(2026, 8, 5, tzinfo=UTC),
)
_NEWS = SuggestionPassage(
    id="p-news",
    text="Ralf Jung, Leiter Prozessautomatisierung, kündigte das Programm an.",
    source_url="https://group.example.com/news",
    document_title=None,
    published_at=None,
)


def _candidate(full_name: str, job_title: str, passage_id: str, quote: str) -> Candidate:
    return Candidate(full_name=full_name, job_title=job_title, passage_id=passage_id, quote=quote)


def test_a_grounded_candidate_becomes_a_suggestion_with_its_documents_address() -> None:
    [suggestion] = keep_suggestions(
        [
            _candidate(
                "Dr. Tobias Meyer",
                "Chief Executive Officer",
                "p-board",
                "Dr. Tobias Meyer, Chief Executive Officer.",
            )
        ],
        [_BOARD],
        existing_names=[],
        limit=10,
    )

    assert suggestion.full_name == "Dr. Tobias Meyer"
    assert suggestion.job_title == "Chief Executive Officer"
    assert suggestion.source_url == "https://group.example.com/board"
    assert suggestion.quote == "Dr. Tobias Meyer, Chief Executive Officer."
    assert suggestion.document_title == "Board of Management"
    assert suggestion.published_at == datetime(2026, 8, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    ("candidate", "why"),
    [
        (
            _candidate("Tobias Meyer", "CEO", "p-board", "Tobias Meyer, CEO of the group."),
            "the quote is not in the passage",
        ),
        (
            _candidate(
                "Tobias M. Meyer",
                "Chief Executive Officer",
                "p-board",
                "Dr. Tobias Meyer, Chief Executive Officer.",
            ),
            "the name as given is not in the quote",
        ),
        (
            _candidate(
                "Melanie Kreis",
                "Chief Executive Officer",
                "p-board",
                "Melanie Kreis, Chief Financial Officer.",
            ),
            "the job title is not in the quote",
        ),
        (
            _candidate(
                "Dr. Tobias Meyer",
                "Chief Executive Officer",
                "p-unknown",
                "Dr. Tobias Meyer, Chief Executive Officer.",
            ),
            "the passage was not given",
        ),
        (
            _candidate("Meyer", "Chief Executive Officer", "p-board", "Meyer, Chief Executive"),
            "a one-word name",
        ),
        (
            _candidate(
                "presse@example.com",
                "Press contact",
                "p-board",
                "Press contact: presse@example.com",
            ),
            "an email address as the name",
        ),
        (
            _candidate(
                "+49 228 182-9944",
                "Press contact",
                "p-board",
                "Press contact: presse@example.com, +49 228 182-9944",
            ),
            "a phone number as the name",
        ),
        (
            _candidate("Dr. Tobias Meyer", " ", "p-board", "Dr. Tobias Meyer, Chief"),
            "an empty job title",
        ),
    ],
)
def test_an_ungrounded_candidate_is_dropped(candidate: Candidate, why: str) -> None:
    assert keep_suggestions([candidate], [_BOARD], existing_names=[], limit=10) == [], why


def test_existing_contacts_and_repeated_names_are_dropped_case_and_space_insensitively() -> None:
    kept = keep_suggestions(
        [
            _candidate(
                "Dr. Tobias Meyer",
                "Chief Executive Officer",
                "p-board",
                "Dr. Tobias Meyer, Chief Executive Officer.",
            ),
            _candidate(
                "Melanie Kreis",
                "Chief Financial Officer",
                "p-board",
                "Melanie Kreis, Chief Financial Officer.",
            ),
            _candidate(
                "Melanie  Kreis",
                "Chief Financial Officer",
                "p-board",
                "Melanie Kreis, Chief Financial Officer.",
            ),
        ],
        [_BOARD],
        existing_names=["dr. tobias   MEYER"],
        limit=10,
    )

    assert [suggestion.full_name for suggestion in kept] == ["Melanie Kreis"]


def test_suggestions_follow_the_passage_order_then_the_output_order_up_to_the_limit() -> None:
    news = _candidate(
        "Ralf Jung", "Leiter Prozessautomatisierung", "p-news", _NEWS.text.split(", kündigte")[0]
    )
    ceo = _candidate(
        "Dr. Tobias Meyer",
        "Chief Executive Officer",
        "p-board",
        "Dr. Tobias Meyer, Chief Executive Officer.",
    )
    cfo = _candidate(
        "Melanie Kreis",
        "Chief Financial Officer",
        "p-board",
        "Melanie Kreis, Chief Financial Officer.",
    )

    kept = keep_suggestions([news, ceo, cfo], [_BOARD, _NEWS], existing_names=[], limit=2)

    assert [suggestion.full_name for suggestion in kept] == ["Dr. Tobias Meyer", "Melanie Kreis"]


def test_names_compare_case_folded_with_whitespace_collapsed() -> None:
    assert normalised_name("  Dr.  Tobias\nMEYER ") == "dr. tobias meyer"
