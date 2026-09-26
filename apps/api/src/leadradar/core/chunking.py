"""[Chunking and passage selection](/architecture/rules.md#chunking-and-passage-selection)
(`S-ING-04`, [ADR-16](/architecture/adrs/adr-16-question-scoped-hybrid-passage-selection.md)):
splitting a normalised document into passages at its section boundaries, building a passage's
header, and — for the classifier call the [signal
graph](/architecture/services/worker.md#signal-graph) makes — fusing a keyword and a meaning
ranking by reciprocal rank and selecting a document's passages across its applicable questions.
Pure functions of their inputs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_PARAGRAPH_BREAK = "\n\n"
_SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?(?=\s|$)")


@dataclass(frozen=True)
class PassageDraft:
    """One passage of [`chunk`](/architecture/sql-store.md#chunk), before it is embedded."""

    ordinal: int
    char_start: int
    char_end: int
    section: str | None
    text: str


def _find_break(text: str, window_start: int, window_end: int) -> int:
    """The best cut point in `text[window_start:window_end]`: the last paragraph break, else the
    last sentence end, else the last space, so a passage never ends inside a word; the window's
    end when the segment holds no boundary at all (one long unbroken token)."""
    segment = text[window_start:window_end]
    paragraph = segment.rfind(_PARAGRAPH_BREAK)
    if paragraph != -1:
        return window_start + paragraph + len(_PARAGRAPH_BREAK)
    sentence_end = None
    for match in _SENTENCE_END_RE.finditer(segment):
        sentence_end = match.end()
    if sentence_end is not None:
        return window_start + sentence_end
    space = segment.rfind(" ")
    if space != -1:
        return window_start + space + 1
    return window_end


def _split_segment(
    text: str, seg_start: int, seg_end: int, *, chunk_target_chars: int, chunk_overlap_chars: int
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pos = seg_start
    while pos < seg_end:
        tentative_end = min(pos + chunk_target_chars, seg_end)
        cut = tentative_end
        if tentative_end < seg_end:
            found = _find_break(text, pos, tentative_end)
            if found > pos:
                cut = found
        spans.append((pos, cut))
        if cut >= seg_end:
            break
        pos = max(cut - chunk_overlap_chars, pos + 1)
    return spans


def _section_at(sections: Sequence[tuple[int, str]]) -> Sequence[tuple[int, str]]:
    return sorted(sections, key=lambda entry: entry[0])


def split_into_passages(
    text: str,
    sections: Sequence[tuple[int, str]],
    *,
    whole_document_max_chars: int,
    chunk_target_chars: int,
    chunk_overlap_chars: int,
) -> list[PassageDraft]:
    """A document of at most `whole_document_max_chars` is one passage with no section
    (`WHOLE_DOCUMENT_MAX_CHARS`); a longer one is split at the boundaries of `sections` — each
    `(char_start, section_path)` [text extraction](/guidelines/python.md) records — first, then
    into passages of at most `chunk_target_chars` with `chunk_overlap_chars` of overlap inside a
    section, breaking at a paragraph, then a sentence, then a word boundary."""
    if not text:
        return []
    if len(text) <= whole_document_max_chars:
        return [PassageDraft(0, 0, len(text), None, text)]

    ordered_sections = _section_at(sections)
    boundaries = sorted({0, len(text)} | {start for start, _ in ordered_sections})
    drafts: list[PassageDraft] = []
    for seg_start, seg_end in zip(boundaries, boundaries[1:], strict=False):
        if seg_start >= seg_end:
            continue
        section = next(
            (path for start, path in reversed(ordered_sections) if start <= seg_start), None
        )
        for start, end in _split_segment(
            text,
            seg_start,
            seg_end,
            chunk_target_chars=chunk_target_chars,
            chunk_overlap_chars=chunk_overlap_chars,
        ):
            if start >= end:
                continue
            drafts.append(PassageDraft(len(drafts), start, end, section, text[start:end]))
    return drafts


def passage_header(
    *, account_name: str, document_title: str | None, section: str | None, date: str
) -> str:
    """The one-line header every passage is read with: account, document, section when it has
    one, and its date — `"Lufthansa Group · Annual Report 2025 · Strategy › Efficiency ·
    2026-03-06"`. Never part of the passage text itself, so no quote comes from it."""
    parts = [account_name]
    if document_title:
        parts.append(document_title)
    if section:
        parts.append(section)
    parts.append(date)
    return " · ".join(parts)


def fuse_rankings(
    rankings: Sequence[Sequence[int]], *, candidates: int, rrf_k: int
) -> list[tuple[int, float]]:
    """Reciprocal-rank fusion of rankings of passage `ordinal`s: each ranking's first
    `candidates` entries contribute `1 / (rrf_k + rank)` (rank from 1); a passage's fused score
    is the sum over every ranking it appears in. Ordered by fused score, highest first, ties by
    `ordinal`."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for index, ordinal in enumerate(ranking[:candidates]):
            scores[ordinal] = scores.get(ordinal, 0.0) + 1.0 / (rrf_k + index + 1)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def select_passages[QuestionId](
    per_question: Mapping[QuestionId, Sequence[tuple[int, float]]],
    *,
    max_passages_per_document: int,
) -> list[int]:
    """The document's selection: the union of each question's fused ranking (already truncated
    to `PASSAGES_PER_QUESTION` by the caller), capped at `max_passages_per_document`, kept in
    order of a passage's best rank across the questions it was selected for, then its highest
    fused score, then its `ordinal` — so every question keeps its best passage before any
    question keeps its second ([ADR-16]
    (/architecture/adrs/adr-16-question-scoped-hybrid-passage-selection.md)). A document with one
    passage never calls this: it selects that passage directly."""
    best_rank: dict[int, int] = {}
    best_score: dict[int, float] = {}
    for ranked in per_question.values():
        for rank, (ordinal, score) in enumerate(ranked, start=1):
            if rank < best_rank.get(ordinal, rank + 1):
                best_rank[ordinal] = rank
            if score > best_score.get(ordinal, score - 1):
                best_score[ordinal] = score
    ordered = sorted(
        best_rank, key=lambda ordinal: (best_rank[ordinal], -best_score[ordinal], ordinal)
    )
    return ordered[:max_passages_per_document]
