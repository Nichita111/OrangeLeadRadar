"""[Contact suggestion](/architecture/rules.md#contact-suggestion): the retrieval query of step 1,
and steps 3 to 5, which of the LLM's candidates become suggestions. Pure: the capability
`leadradar.accounts.contact_suggestions` reads the passages and makes the call."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

#: Step 1: the question text and hint terms of the question-scoped retrieval.
QUESTION_TEXT = "Who leads the company, named with a job title?"
HINT_TERMS: tuple[str, ...] = (
    "CEO",
    "CFO",
    "CIO",
    "COO",
    "CTO",
    "CISO",
    "Chief",
    "Head of",
    "Director",
    "board of management",
    "managing director",
    "Vorstand",
    "Geschäftsführer",
    "Leiter",
)


@dataclass(frozen=True)
class Candidate:
    """One person of the LLM's output ([`ContactCandidate`]
    (/architecture/interfaces.md#contactcandidate))."""

    full_name: str
    job_title: str
    passage_id: str
    quote: str


@dataclass(frozen=True)
class SuggestionPassage:
    """A selected passage with what a suggestion takes from its document."""

    id: str
    text: str
    source_url: str
    document_title: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class Suggestion:
    """[`ContactSuggestion`](/architecture/interfaces.md#contactsuggestion)."""

    full_name: str
    job_title: str
    source_url: str
    quote: str
    document_title: str | None
    published_at: datetime | None


def normalised_name(full_name: str) -> str:
    """Step 4: names are compared case-folded with whitespace collapsed."""
    return " ".join(full_name.split()).casefold()


def _is_grounded(candidate: Candidate, passage_text: str) -> bool:
    """Step 3: the quote is verbatim in the passage and holds the name and the job title; the
    name has at least two words and no digit or `@`, so no address or number passes as one."""
    name = candidate.full_name.strip()
    title = candidate.job_title.strip()
    return (
        bool(candidate.quote)
        and candidate.quote in passage_text
        and bool(title)
        and name in candidate.quote
        and title in candidate.quote
        and len(name.split()) >= 2
        and "@" not in name
        and not any(char.isdigit() for char in name)
    )


def keep_suggestions(
    candidates: Sequence[Candidate],
    passages: Sequence[SuggestionPassage],
    *,
    existing_names: Iterable[str],
    limit: int,
) -> list[Suggestion]:
    """Steps 3 to 5 over `passages` in fused-score order: grounded candidates, ordered by their
    passage then their place in the output, without an existing contact's name or a name kept
    before, at most `limit` (`CONTACT_SUGGESTION_MAX`)."""
    by_id = {passage.id: (rank, passage) for rank, passage in enumerate(passages)}
    grounded = sorted(
        (
            (by_id[candidate.passage_id][0], position, candidate)
            for position, candidate in enumerate(candidates)
            if candidate.passage_id in by_id
            and _is_grounded(candidate, by_id[candidate.passage_id][1].text)
        ),
        key=lambda entry: (entry[0], entry[1]),
    )
    seen = {normalised_name(name) for name in existing_names}
    kept: list[Suggestion] = []
    for _, _, candidate in grounded:
        name = normalised_name(candidate.full_name)
        if name in seen:
            continue
        seen.add(name)
        passage = by_id[candidate.passage_id][1]
        kept.append(
            Suggestion(
                full_name=candidate.full_name.strip(),
                job_title=candidate.job_title.strip(),
                source_url=passage.source_url,
                quote=candidate.quote,
                document_title=passage.document_title,
                published_at=passage.published_at,
            )
        )
        if len(kept) == limit:
            break
    return kept
