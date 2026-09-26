"""Unit tests of [Document normalisation]
(/architecture/rules.md#document-normalisation) (`S-ING-03`)."""

from __future__ import annotations

import pytest

from leadradar.core.document_normalisation import (
    canonicalize_url,
    content_hash,
    detect_language,
    extract_html,
    extract_pdf,
    is_near_duplicate,
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
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buffer = _write_to_bytes(writer)

    extracted = extract_pdf(buffer)
    assert [path for _start, path in extracted.sections] == ["page 1", "page 2"]


def _write_to_bytes(writer: object) -> bytes:
    import io

    stream = io.BytesIO()
    writer.write(stream)  # type: ignore[attr-defined]
    return stream.getvalue()
