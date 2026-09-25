"""Markdown and frontmatter reading for the docs tooling (docs/guidelines/documents/common.md, R8).

A thin adapter over `markdown-it-py` and `pyyaml`: dataclasses with 1-based line numbers,
shape only, no meaning. Every other script reads the bundle through this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

_MD = MarkdownIt("gfm-like")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
_FIELD_RE = re.compile(r"^([A-Za-z_][\w-]*):(.*)$")
_ANCHOR_PUNCTUATION_RE = re.compile(r"[^\w\s-]")
_ANCHOR_WHITESPACE_RE = re.compile(r"\s")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(?:\d+[\.\)]|\d+(?:\.\d+)+[\.\)]?)\s")


class FrontmatterError(ValueError):
    """A frontmatter block is present but is not valid YAML."""


@dataclass
class Heading:
    level: int
    title: str
    line: int
    end: int  # exclusive: the next heading at a level <= this one, or len(lines) + 1


@dataclass
class Table:
    header: list[str]
    rows: list[list[str]]
    row_lines: list[int]
    line: int


@dataclass
class Fence:
    lang: str
    start: int
    end: int


@dataclass
class Link:
    label: str
    target: str
    line: int


def blank_frontmatter(text: str) -> str:
    """Blank a leading frontmatter block, keeping the line count, so line numbers still match."""
    m = FRONTMATTER_RE.match(text)
    return text if not m else ("\n" * text.count("\n", 0, m.end())) + text[m.end() :]


def frontmatter(text: str) -> dict[str, Any] | None:
    """Parsed frontmatter: `None` without a block, `FrontmatterError` when it is not YAML."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise FrontmatterError(str(exc).splitlines()[0]) from exc
    return data if isinstance(data, dict) else {}


def frontmatter_lenient(text: str) -> dict[str, str] | None:
    """Top-level `key: value` pairs read line by line, for reporting a broken block."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fields: dict[str, str] = {}
    for raw in m.group(1).splitlines():
        fm = _FIELD_RE.match(raw)
        if fm:
            fields[fm.group(1).strip()] = fm.group(2).strip().strip('"')
    return fields


@lru_cache(maxsize=128)
def _tree_for_text(text: str) -> SyntaxTreeNode:
    return SyntaxTreeNode(_MD.parse(text))


def _tree(lines: list[str]) -> SyntaxTreeNode:
    return _tree_for_text("\n".join(lines))


def heading_anchor(title: str) -> str:
    """GitHub heading slug: lowercase, punctuation removed, one hyphen per space."""
    text = _ANCHOR_PUNCTUATION_RE.sub("", title.lower())
    return _ANCHOR_WHITESPACE_RE.sub("-", text.strip())


def is_heading_numbered(title: str) -> bool:
    return bool(_NUMBERED_HEADING_RE.match(title))


def parse_headings(lines: list[str]) -> list[Heading]:
    raw = [
        (int(n.tag[1]), n.map[0] + 1, (n.children[0].content if n.children else "").strip())
        for n in _tree(lines).walk(include_self=False)
        if n.type == "heading" and n.map is not None
    ]
    heads = [Heading(level=lvl, title=title, line=ln, end=len(lines) + 1) for lvl, ln, title in raw]
    for idx, h in enumerate(heads):
        nxt = next((n for n in heads[idx + 1 :] if n.level <= h.level), None)
        if nxt:
            h.end = nxt.line
    return heads


def find_tables(lines: list[str], start: int = 1, end: int | None = None) -> list[Table]:
    end = len(lines) + 1 if end is None else end
    out: list[Table] = []
    for t in _tree(lines).walk(include_self=False):
        if t.type != "table" or t.map is None:
            continue
        table_line = t.map[0] + 1
        if not (start <= table_line < end):
            continue
        thead = next((c for c in t.children if c.type == "thead"), None)
        tbody = next((c for c in t.children if c.type == "tbody"), None)
        header = (
            [cell.children[0].content if cell.children else "" for cell in thead.children[0].children]
            if thead
            else []
        )
        rows, row_lines = [], []
        for tr in tbody.children if tbody else []:
            rows.append([cell.children[0].content if cell.children else "" for cell in tr.children])
            row_lines.append(tr.map[0] + 1 if tr.map else table_line)
        out.append(Table(header=header, rows=rows, row_lines=row_lines, line=table_line))
    return out


def find_fences(lines: list[str]) -> list[Fence]:
    return [
        Fence(lang=(n.info or "").strip(), start=n.map[0] + 1, end=n.map[1])
        for n in _tree(lines).walk(include_self=False)
        if n.type == "fence" and n.map is not None
    ]


def find_links(lines: list[str], start: int = 1, end: int | None = None) -> list[Link]:
    end = len(lines) + 1 if end is None else end
    out: list[Link] = []
    for inline in _tree(lines).walk(include_self=False):
        if inline.type != "inline" or inline.map is None:
            continue
        line = inline.map[0] + 1
        if not (start <= line < end):
            continue
        for c in inline.children:
            if c.type in ("softbreak", "hardbreak"):
                line += 1
            elif c.type == "link":
                label = "".join(g.content for g in c.children if g.type in ("text", "code_inline"))
                href = (c.attrs or {}).get("href")
                out.append(Link(label=label, target=str(href) if href else "", line=line))
    return out


def read_bundle(root: str) -> dict[str, str]:
    """Every `.md` file under `root`, keyed by its bundle-relative POSIX path."""
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(Path(root).rglob("*.md"))
    }


def body_lines(text: str) -> list[str]:
    return blank_frontmatter(text).split("\n")
