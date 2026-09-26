"""[Document normalisation](/architecture/rules.md#document-normalisation) (`S-ING-03`): turning
one fetched item's raw content into the plain text, canonical URL, language, content hash and
section headings a `document` row needs, and the near-duplicate predicate. Pure functions of
their inputs: text extraction reads only the bytes it is given, never the network."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import py3langid
from bs4 import BeautifulSoup, Comment, Tag
from bs4.element import NavigableString
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from leadradar.core.account_identity import InvalidDomain, normalise_domain

#: Query parameters [Document normalisation](/architecture/rules.md#document-normalisation)
#: drops from a canonical URL; `utm_*` is a prefix, the rest are exact names.
_DROPPED_QUERY_KEYS = frozenset({"gclid", "fbclid", "mc_cid", "mc_eid", "ref", "source"})
_UTM_PREFIX = "utm_"

_HORIZONTAL_WS_RE = re.compile(r"[ \t ]+")
_BLANK_RUN_RE = re.compile(r"\n{3,}")

_HEADING_TAGS = frozenset({"h1", "h2", "h3"})
_BOILERPLATE_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "noscript"})
_BLOCK_TAGS = frozenset(
    {"p", "div", "section", "article", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6"}
)


@dataclass(frozen=True)
class ExtractedDocument:
    """What [text extraction](#extract_html) gives: the plain text of the item, its section
    headings in document order as `(char_start, section_path)` in the returned `text`, and the
    page's declared canonical link, if it has one."""

    text: str
    sections: tuple[tuple[int, str], ...]
    canonical_link: str | None


def normalise_text(raw: str) -> str:
    """Unicode NFC; horizontal whitespace collapsed to one space; a run of blank lines collapsed
    to one, so a paragraph break survives for [Chunking and passage
    selection](/architecture/rules.md#chunking-and-passage-selection) to break on."""
    nfc = unicodedata.normalize("NFC", raw).replace("\r\n", "\n").replace("\r", "\n")
    horizontal_collapsed = _HORIZONTAL_WS_RE.sub(" ", nfc)
    lines = [line.strip() for line in horizontal_collapsed.split("\n")]
    return _BLANK_RUN_RE.sub("\n\n", "\n".join(lines)).strip()


def content_hash(text: str) -> str:
    """SHA-256 of the normalised text, lower-case hex, for `document.content_hash`."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_language(text: str) -> str:
    """ISO 639-1 code of `text`'s language, `py3langid`'s deterministic classifier."""
    code, _confidence = py3langid.classify(text)
    return str(code)


def is_near_duplicate(similarity: float, threshold: float) -> bool:
    """Whether a first-passage cosine similarity of `similarity` makes two documents near
    duplicates at `NEAR_DUPLICATE_SIMILARITY`."""
    return similarity >= threshold


def canonicalize_url(url: str, canonical_link: str | None = None) -> str:
    """Lower-cases scheme and host, drops the fragment and the tracking query parameters, drops
    a trailing slash, and prefers `canonical_link` when it is on the same registrable domain."""
    chosen = url
    if canonical_link:
        try:
            if normalise_domain(canonical_link) == normalise_domain(url):
                chosen = canonical_link
        except InvalidDomain:
            pass
    parts = urlsplit(chosen)
    host = (parts.hostname or "").lower()
    port = f":{parts.port}" if parts.port else ""
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(_UTM_PREFIX) and key.lower() not in _DROPPED_QUERY_KEYS
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host + port, path, urlencode(query), ""))


def _heading_level(tag: Tag) -> int:
    return int(tag.name[1])


def _resolve_chain(stack: list[tuple[int, str]], level: int, title: str) -> str:
    """Pops every open heading at `level` or deeper, pushes `(level, title)`, and returns the
    chain of open headings joined by ` › `, the section path of [Chunking and passage
    selection](/architecture/rules.md#chunking-and-passage-selection)."""
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))
    return " › ".join(title for _level, title in stack)


def extract_html(raw_html: str) -> ExtractedDocument:
    """The main text of an HTML page — the `<article>` or `<main>` element when there is one,
    else the body — without navigation and boilerplate, with its `h1`-`h3` headings resolved to
    section paths at the offset in the returned text where each begins, and its declared
    `<link rel="canonical">`, if any."""
    soup = BeautifulSoup(raw_html, "html.parser")
    canonical_tag = soup.find("link", rel=lambda value: bool(value) and "canonical" in value)
    canonical_link = (
        str(canonical_tag["href"]) if canonical_tag and canonical_tag.get("href") else None
    )
    for tag in soup(_BOILERPLATE_TAGS):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup

    parts: list[str] = []
    sections: list[tuple[int, str]] = []
    stack: list[tuple[int, str]] = []

    def visit(node: object) -> None:
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                if parts and not parts[-1].endswith(("\n", " ")):
                    parts.append(" ")
                parts.append(text)
            return
        if isinstance(node, Tag):
            if node.name in _HEADING_TAGS:
                title = node.get_text(" ", strip=True)
                if title:
                    position = len("".join(parts))
                    path = _resolve_chain(stack, _heading_level(node), title)
                    sections.append((position, path))
            for child in node.children:
                visit(child)
            if node.name in _BLOCK_TAGS and parts and not parts[-1].endswith("\n"):
                parts.append("\n\n")

    visit(main)
    text = normalise_text("".join(parts))
    return ExtractedDocument(text=text, sections=tuple(sections), canonical_link=canonical_link)


def extract_pdf(raw_pdf: bytes) -> ExtractedDocument:
    """The text of every page, joined with a blank line, with its outline resolved to section
    paths at the char offset where each target page begins; a PDF with no outline gets one
    section per page, `page N` (1-based), per [Chunking and passage
    selection](/architecture/rules.md#chunking-and-passage-selection)."""
    reader = PdfReader(io.BytesIO(raw_pdf))
    page_texts = [normalise_text(page.extract_text() or "") for page in reader.pages]

    page_starts: list[int] = []
    offset = 0
    for page_text in page_texts:
        page_starts.append(offset)
        offset += len(page_text) + 2  # the "\n\n" joiner

    sections: list[tuple[int, str]] = []
    try:
        outline = reader.outline
    except PdfReadError:
        outline = []
    flattened = list(_flatten_outline(reader, outline))
    if flattened:
        stack: list[tuple[int, str]] = []
        for depth, title, page_number in flattened:
            if page_number is None or not (0 <= page_number < len(page_starts)):
                continue
            path = _resolve_chain(stack, depth, title)
            sections.append((page_starts[page_number], path))
    else:
        for index in range(len(page_texts)):
            sections.append((page_starts[index], f"page {index + 1}"))

    return ExtractedDocument(
        text=normalise_text("\n\n".join(page_texts)), sections=tuple(sections), canonical_link=None
    )


def _flatten_outline(
    reader: PdfReader, outline: object, depth: int = 0
) -> list[tuple[int, str, int | None]]:
    """Depth-first walk of `PdfReader.outline` (a list nesting sub-lists for children) to
    `(depth, title, page_number)`, in document order."""
    flat: list[tuple[int, str, int | None]] = []
    if not isinstance(outline, list):
        return flat
    for entry in outline:
        if isinstance(entry, list):
            flat.extend(_flatten_outline(reader, entry, depth + 1))
            continue
        title = getattr(entry, "title", None)
        if not title:
            continue
        try:
            page_number = reader.get_destination_page_number(entry)
        except (KeyError, ValueError, AttributeError):
            page_number = None
        flat.append((depth, str(title), page_number))
    return flat


def extract_json_record(*, title: str | None, description: str | None, content: str | None) -> str:
    """A provider's JSON record read as plain text: its `title`, `description` and `content`
    fields joined, blanks dropped."""
    return normalise_text("\n\n".join(field for field in (title, description, content) if field))
