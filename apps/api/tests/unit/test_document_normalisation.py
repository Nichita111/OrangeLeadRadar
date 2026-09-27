"""Unit tests of [Document normalisation]
(/architecture/rules.md#document-normalisation) (`S-ING-03`)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pypdf import PdfWriter

from leadradar.core.document_normalisation import (
    DatedVector,
    canonicalize_url,
    content_hash,
    detect_language,
    extract_html,
    extract_pdf,
    is_near_duplicate,
    near_duplicate_of,
    normalise_item,
    normalise_text,
)

pytestmark = pytest.mark.unit


def test_normalise_text_collapses_horizontal_whitespace_and_keeps_one_blank_line() -> None:
    raw = "Title\t\t here \r\n\r\n\r\n\r\nBody   line.  \n\nSecond line."
    assert normalise_text(raw) == "Title here\n\nBody line.\n\nSecond line."


def test_content_hash_is_deterministic_and_sensitive_to_text() -> None:
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("Hello")


@pytest.mark.parametrize(
    ("similarity", "threshold", "expected"),
    [(0.94, 0.95, False), (0.95, 0.95, True), (0.96, 0.95, True)],
)
def test_is_near_duplicate_threshold(similarity: float, threshold: float, expected: bool) -> None:
    assert is_near_duplicate(similarity, threshold) is expected


@pytest.mark.parametrize(
    ("url", "canonical_link", "expected"),
    [
        (
            "https://example.com/a?utm_source=x&utm_medium=y&keep=1",
            None,
            "https://example.com/a?keep=1",
        ),
        ("https://example.com/a/", None, "https://example.com/a"),
        ("HTTPS://Example.com/a", None, "https://example.com/a"),
        ("https://example.com/a#section", None, "https://example.com/a"),
        (
            "https://example.com/a?gclid=1&fbclid=2&mc_cid=3&mc_eid=4&ref=x&source=y",
            None,
            "https://example.com/a",
        ),
        (
            "https://example.com/a?utm_source=x",
            "https://example.com/canonical-a",
            "https://example.com/canonical-a",
        ),
        (
            "https://example.com/a",
            "https://other.com/a",
            "https://example.com/a",
        ),
    ],
)
def test_canonicalize_url(url: str, canonical_link: str | None, expected: str) -> None:
    assert canonicalize_url(url, canonical_link) == expected


def test_detect_language_is_deterministic() -> None:
    english = "This is a plain English sentence about business automation and process mining."
    german = "Dies ist ein deutscher Satz über Automatisierung und Prozessoptimierung im Betrieb."
    assert detect_language(english) == "en"
    assert detect_language(german) == "de"
    assert detect_language(english) == detect_language(english)


def test_extract_html_finds_main_text_headings_and_canonical_link() -> None:
    html = """
    <html><head><link rel="canonical" href="https://example.com/canonical"></head>
    <body>
      <nav>Skip this navigation</nav>
      <article>
        <h1>Strategy</h1>
        <p>Intro paragraph about the company.</p>
        <h2>Efficiency</h2>
        <p>Details about efficiency programmes.</p>
      </article>
      <footer>Skip this footer</footer>
    </body></html>
    """
    extracted = extract_html(html)
    assert "Skip this navigation" not in extracted.text
    assert "Skip this footer" not in extracted.text
    assert "Intro paragraph about the company." in extracted.text
    assert extracted.canonical_link == "https://example.com/canonical"
    paths = [path for _start, path in extracted.sections]
    assert paths == ["Strategy", "Strategy › Efficiency"]


def test_extract_pdf_without_outline_gets_a_section_per_page(tmp_path: object) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buffer = _write_to_bytes(writer)

    extracted = extract_pdf(buffer)
    assert [path for _start, path in extracted.sections] == ["page 1", "page 2"]


def _write_to_bytes(writer: PdfWriter) -> bytes:
    import io

    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


_ARTICLE = (
    "<html><head><link rel='canonical' href='https://www.example.com/news/story/'></head>"
    "<body><nav>Menu</nav><article><h1>Big news</h1>"
    "<p>The company announced a new cargo hub near the airport this week.</p></article>"
    "</body></html>"
)
_MIN_CHARS = 20


def _pdf_with_text(text: str) -> bytes:
    """A one-page PDF whose only content is `text`."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_at,
    )
    return out


def test_normalise_item_of_html_gives_text_sections_canonical_url_language_and_hash() -> None:
    item = normalise_item(
        url="https://www.example.com/news/story?utm_source=x#top",
        content_type="HTML",
        body=_ARTICLE.encode(),
        title=None,
        min_document_chars=_MIN_CHARS,
    )

    assert item is not None
    assert (
        item.text == "Big news\n\nThe company announced a new cargo hub near the airport this week."
    )
    assert item.sections == ((0, "Big news"),)
    assert item.canonical_url == "https://www.example.com/news/story"
    assert item.language == "en"
    assert item.content_hash == content_hash(item.text)


def test_normalise_item_of_a_pdf_gives_its_text() -> None:
    item = normalise_item(
        url="https://example.com/report.pdf",
        content_type="PDF",
        body=_pdf_with_text("Annual report of the company on its cargo network."),
        title=None,
        min_document_chars=_MIN_CHARS,
    )

    assert item is not None
    assert "Annual report of the company" in item.text
    assert item.sections == ((0, "page 1"),)


def test_normalise_item_of_a_json_record_joins_title_description_and_content() -> None:
    body = json.dumps({"title": "Ops manager", "content": "Runs the hub and its shifts."})
    item = normalise_item(
        url="https://jobs.example.com/1",
        content_type="JSON",
        body=body.encode(),
        title="Ops manager",
        min_document_chars=_MIN_CHARS,
    )

    assert item is not None
    assert item.text == "Ops manager\n\nRuns the hub and its shifts."
    assert item.sections == ()


def test_normalise_item_below_the_minimum_length_gives_nothing() -> None:
    assert (
        normalise_item(
            url="https://example.com/a",
            content_type="HTML",
            body=b"<p>Too short.</p>",
            title=None,
            min_document_chars=_MIN_CHARS,
        )
        is None
    )


def test_normalise_item_gives_the_same_hash_for_the_same_text() -> None:
    first, second = (
        normalise_item(
            url=url,
            content_type="HTML",
            body=_ARTICLE.encode(),
            title=None,
            min_document_chars=_MIN_CHARS,
        )
        for url in ("https://a.example.com/x", "https://b.example.com/y")
    )

    assert first is not None and second is not None
    assert first.content_hash == second.content_hash


_DAY0 = datetime(2026, 9, 20, tzinfo=UTC)
_THRESHOLD = 0.95
_WINDOW_DAYS = 7


def _doc(days: float, vector: list[float], content_hash: str = "h") -> DatedVector:
    return DatedVector(uuid.uuid4(), _DAY0 + timedelta(days=days), content_hash, vector)


def _original_of(document: DatedVector, candidates: list[DatedVector]) -> uuid.UUID | None:
    return near_duplicate_of(document, candidates, similarity=_THRESHOLD, window_days=_WINDOW_DAYS)


def test_a_first_passage_at_the_threshold_within_the_window_is_a_near_duplicate() -> None:
    original = _doc(0, [1.0, 0.0])
    at_threshold = [_THRESHOLD, (1 - _THRESHOLD**2) ** 0.5]
    assert _original_of(_doc(1, at_threshold), [original]) == original.id


def test_below_the_threshold_or_beyond_the_window_is_not_a_near_duplicate() -> None:
    original = _doc(0, [1.0, 0.0])
    below = [0.94, (1 - 0.94**2) ** 0.5]
    assert _original_of(_doc(1, below), [original]) is None
    assert _original_of(_doc(_WINDOW_DAYS, [1.0, 0.0]), [original]) == original.id
    assert _original_of(_doc(_WINDOW_DAYS + 1, [1.0, 0.0]), [original]) is None


def test_the_earliest_qualifying_document_is_the_original() -> None:
    first, second = _doc(0, [1.0, 0.0]), _doc(1, [1.0, 0.0])
    assert _original_of(_doc(2, [1.0, 0.0]), [second, first]) == first.id


def test_a_later_document_is_never_the_original_of_an_earlier_one() -> None:
    later = _doc(2, [1.0, 0.0])
    assert _original_of(_doc(0, [1.0, 0.0]), [later]) is None


def test_the_document_is_not_its_own_original() -> None:
    document = _doc(0, [1.0, 0.0])
    assert _original_of(document, [document]) is None


def test_equal_dates_order_by_content_hash() -> None:
    a, b = _doc(0, [1.0, 0.0], "a"), _doc(0, [1.0, 0.0], "b")
    assert _original_of(b, [a]) == a.id
    assert _original_of(a, [b]) is None
