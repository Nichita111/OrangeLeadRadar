"""Documentation bundle checker (docs/guidelines/documents/common.md, R8).

Usage: `uv run --project scripts python scripts/check_docs.py [docs-dir]`.
Checks R1/R3/R4/R5/R6 and the traceability rules of the registers; exit 1 on any finding.
"""

from __future__ import annotations

import collections
from collections.abc import Callable
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import build_indexes
import build_traceability
from docmd import (
    FrontmatterError,
    body_lines,
    find_fences,
    find_links,
    find_tables,
    frontmatter,
    frontmatter_lenient,
    heading_anchor,
    is_heading_numbered,
    parse_headings,
    read_bundle,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
TYPES = {
    "Reference",
    "Guideline",
    "Requirements",
    "Glossary",
    "Architecture",
    "Store",
    "Rule",
    "Interface",
    "Decision",
    "Service",
    "Feature",
}
FOLDER_TYPES = {
    "reference": {"Reference"},
    "guidelines": {"Guideline"},
    "guidelines/documents": {"Guideline"},
    "requirements": {"Requirements", "Glossary"},
    "architecture": {"Architecture", "Store", "Rule", "Interface"},
    "architecture/adrs": {"Decision"},
    "architecture/services": {"Service"},
    "features": {"Feature"},
}
FIELDS = ["type", "title", "description", "status", "tags"]
OPTIONAL = {"sources"}
RULES_DOC = "/guidelines/documents/common.md#the-eight-rules"
TRACE_DOC = "/guidelines/documents/common.md#traceability"
DECLARED_ID_RE = re.compile(r"^`?([A-Z]{1,6}-[A-Z0-9]+(?:-[A-Z0-9]+)*)`?$")
FL_HEADING_RE = re.compile(r"^(FL-\d{2}) \S")
REF_ID_RE = re.compile(r"\b(B-\d{2}|RULE-\d{2}|S-[A-Z]{3}-\d{2}|N-\d{2}|FL-\d{2})\b")
ENTITY_LINK_RE = re.compile(r"\]\(/architecture/sql-store\.md#([a-z0-9_-]+)\)")
FR_ROW_RE = re.compile(r"^`?FR-\d")
EPHEMERAL = [
    (r"[✅⚠️❌]", "status glyph"),
    (r"\b(src|apps)/[\w./-]+\.(py|tsx?):\d+", "code citation"),
    (r"(?<![\w/])§\s?\d", "section-number reference"),
    (r"\bGAP-\d", "GAP id"),
    (r"\bTODO\b", "to-do"),
    (r"\[NOT IMPLEMENTED", "not-implemented tag"),
]


def _internal_target(href: str) -> tuple[str | None, str | None] | None:
    u = urlsplit(href)
    if (
        u.scheme
        or u.netloc
        or u.query
        or (u.path and not (u.path.startswith("/") and u.path.endswith(".md")))
    ):
        return None
    path, anchor = u.path or None, (u.fragment or None)
    return None if not path and not anchor else (path, anchor)


def _column(header: list[str], name: str) -> int | None:
    names = [h.strip().lower() for h in header]
    return names.index(name.lower()) if name.lower() in names else None


def _check_file(
    rel: str, text: str, feature_slugs: set[str], add: Callable[..., None]
) -> None:
    posix = PurePosixPath(rel)
    base = posix.name
    folder = "" if posix.parent == PurePosixPath() else posix.parent.as_posix()
    if base in ("index.md", "log.md"):
        if text.startswith("---") and rel != "index.md":
            add(rel, 1, "frontmatter", f"{base} must not carry frontmatter")
        return
    fields = frontmatter_lenient(text)
    if fields is None:
        add(rel, 1, "frontmatter", "missing frontmatter")
        return
    parsed = None
    try:
        parsed = frontmatter(text)
    except FrontmatterError as exc:
        add(rel, 1, "frontmatter", f"frontmatter is not valid YAML: {exc}")
    for k in [k for k in FIELDS if k not in fields] + sorted(set(fields) - set(FIELDS) - OPTIONAL):
        add(rel, 1, "frontmatter", f"frontmatter {'missing' if k in FIELDS else 'extra field'} {k}")
    t = fields.get("type")
    if t not in TYPES:
        add(rel, 1, "frontmatter", f"unknown type {t}")
    if (allowed := FOLDER_TYPES.get(folder)) and t not in allowed:
        add(rel, 1, "frontmatter", f"type {t} not allowed in {folder}")
    if folder not in FOLDER_TYPES:
        add(rel, 1, "frontmatter", f"no document may live in folder '{folder or '/'}'")
    if fields.get("status") not in {"draft", "stable", "deprecated"}:
        add(rel, 1, "frontmatter", "bad status")
    tags = parsed.get("tags") if isinstance(parsed, dict) else None
    if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
        add(rel, 1, "frontmatter", "tags must be a list of feature slugs")
    else:
        for tag in tags:
            if tag not in feature_slugs:
                add(rel, 1, "frontmatter", f"unknown tag {tag!r}")
        if folder == "features" and not tags:
            add(rel, 1, "frontmatter", "a feature must tag itself")


def run(root: str) -> tuple[list[str], int]:
    files = read_bundle(root)
    lines_by_rel = {rel: body_lines(text) for rel, text in files.items()}
    errors: dict[str, list[tuple[int, str, str]]] = collections.defaultdict(list)

    def add(rel: str, line: int, rule: str, message: str) -> None:
        errors[rel].append((line, rule, message))

    feature_slugs = {
        PurePosixPath(rel).stem
        for rel in files
        if rel.startswith("features/") and PurePosixPath(rel).name != "index.md"
    }
    headings: dict[str, set[str]] = {}
    declared: dict[str, tuple[str, int]] = {}
    flows: dict[str, tuple[str, str]] = {}  # FL id -> (feature file, anchor)

    for rel, text in files.items():
        lines = lines_by_rel[rel]
        folder = PurePosixPath(rel).parent.as_posix()
        _check_file(rel, text, feature_slugs, add)
        if rel == "log.md":
            for n, raw in enumerate(lines, start=1):
                if not raw.strip() or raw.startswith("# "):
                    continue
                if raw.startswith("## "):
                    if not (re.match(r"^## \d{4}-\d{2}-\d{2}$", raw) or raw == "## Earlier"):
                        add(rel, n, "log", f"invalid log heading {raw!r}")
                elif not raw.startswith(("* **Update**: ", "* **Compacted** (10 entries): ")):
                    add(rel, n, "log", f"invalid log entry {raw[:60]!r}")
        heads = parse_headings(lines)
        if folder == "architecture/adrs" and PurePosixPath(rel).name != "index.md":
            base = PurePosixPath(rel).name
            if not re.match(r"^adr-\d{2}-[a-z0-9-]+\.md$", base):
                add(rel, 1, "adr", "ADR filename must be adr-nn-slug.md")
            h1 = next((h for h in heads if h.level == 1), None)
            m = re.match(r"^(ADR-\d{2}) (.+)$", h1.title) if h1 else None
            if m is None:
                add(rel, 1, "adr", "ADR must open with '# ADR-nn Title'")
            elif heading_anchor(h1.title) != base[:-3]:
                add(rel, 1, "adr", "ADR heading does not match its filename")
        slugs: collections.Counter[str] = collections.Counter()
        for h in heads:
            if is_heading_numbered(h.title) and not rel.startswith("reference/"):
                add(rel, h.line, "heading", f"numbered heading: {h.title}")
            if not h.title.isascii():
                add(rel, h.line, "heading", f"non-ASCII heading: {h.title}")
            slugs[heading_anchor(h.title)] += 1
            fl = FL_HEADING_RE.match(h.title)
            if fl:
                if folder != "features" or h.level != 3:
                    add(rel, h.line, "flow", f"{fl.group(1)} must be a ### heading in a feature")
                if fl.group(1) in flows:
                    add(rel, h.line, "duplicate-id", f"duplicate flow {fl.group(1)}")
                flows[fl.group(1)] = (rel, heading_anchor(h.title))
        for s, c in slugs.items():
            if c > 1:
                add(rel, 1, "heading", f"duplicate heading slug #{s} x{c}")
        headings[rel] = set(slugs)
        for table in find_tables(lines):
            for row, ln in zip(table.rows, table.row_lines, strict=True):
                if not row:
                    continue
                m = DECLARED_ID_RE.match(row[0].strip())
                if m and rel != build_traceability.TARGET:  # the matrix restates, never declares
                    ident = m.group(1)
                    if ident in declared:
                        prev = declared[ident]
                        add(rel, ln, "duplicate-id", f"{ident} already declared at {prev[0]}:{prev[1]}")
                    else:
                        declared[ident] = (rel, ln)
                if folder.startswith("architecture") and rel != "architecture/services/frontend.md":
                    if FR_ROW_RE.match(row[0].strip()):
                        add(rel, ln, "fr-row", "FR- row outside a feature or the frontend service")
        fenced = {i for f in find_fences(lines) for i in range(f.start, f.end + 1)}
        prose = "\n".join("" if i in fenced else s for i, s in enumerate(lines, start=1))
        if rel.startswith("reference/"):
            continue  # external material, kept as received
        for pat, name in EPHEMERAL:
            mm = re.search(pat, prose)
            if mm:
                add(rel, prose.count("\n", 0, mm.start()) + 1, "ephemeral", f"{name}: {mm.group(0)!r}")

    for rel in files:
        for link in find_links(lines_by_rel[rel]):
            parsed = _internal_target(link.target)
            if parsed is None:
                continue
            path, anchor = parsed
            target = path.lstrip("/") if path else rel
            if path and target not in files:
                add(rel, link.line, "link", f"broken file link {path}")
            elif anchor and anchor.lower() not in headings.get(target, set()):
                add(rel, link.line, "link", f"broken anchor {path or ''}#{anchor}")

    _check_traceability(files, lines_by_rel, flows, declared, add)
    _check_references(files, lines_by_rel, declared, add)
    _check_tags(files, lines_by_rel, add)

    generated, _ = build_indexes.generated(root, texts=files)
    generated["requirements/traceability.md"] = build_traceability.render(files)
    for rel, content in generated.items():
        if files.get(rel) != content:
            add(rel, 1, "generated-stale", "stale generated file; run the build scripts")

    out = [
        f"{rel}:{line}: {rule}: {message}"
        for rel in sorted(errors)
        for line, rule, message in sorted(errors[rel])
    ]
    return out, len(files)


def _check_traceability(
    files: dict[str, str],
    lines_by_rel: dict[str, list[str]],
    flows: dict[str, tuple[str, str]],
    declared: dict[str, tuple[str, int]],
    add: Callable[..., None],
) -> None:
    system, acceptance = "requirements/system.md", "requirements/acceptance.md"
    if system not in files or acceptance not in files:
        return
    store_entities = {
        heading_anchor(h.title)
        for h in parse_headings(lines_by_rel.get("architecture/sql-store.md", []))
        if h.level == 3
    }
    b_rows: dict[str, str] = {}
    for rel in ("requirements/business.md",):
        for table in find_tables(lines_by_rel.get(rel, [])):
            pcol = _column(table.header, "Priority")
            for row in table.rows:
                m = DECLARED_ID_RE.match(row[0].strip())
                if m and m.group(1).startswith("B-") and pcol is not None:
                    b_rows[m.group(1)] = row[pcol].strip()
    realised: set[str] = set()
    flows_used: set[str] = set()
    entities_used: set[str] = set()
    obligations: dict[str, int] = {}
    for table in find_tables(lines_by_rel[system]):
        cols = {n: _column(table.header, n) for n in ("Realises", "Flows", "Entities", "Specified in")}
        if any(c is None for c in cols.values()):
            add(system, table.line, "trace", "register table lacks Realises/Flows/Entities/Specified in")
            continue
        for row, ln in zip(table.rows, table.row_lines, strict=True):
            m = DECLARED_ID_RE.match(row[0].strip())
            if not m:
                continue
            ident = m.group(1)
            obligations[ident] = ln
            refs = REF_ID_RE.findall(row[cols["Realises"]])
            if not refs:
                add(system, ln, "trace", f"{ident} realises no B- or RULE- row")
            for r in refs:
                if r not in declared:
                    add(system, ln, "trace", f"{ident} realises unknown {r}")
            realised.update(refs)
            fl_cell = row[cols["Flows"]]
            fl_ids = [r for r in REF_ID_RE.findall(fl_cell) if r.startswith("FL-")]
            if not fl_ids and fl_cell.strip().lower() != "all":
                add(system, ln, "trace", f"{ident} names no flow")
            for f in fl_ids:
                if f not in flows:
                    add(system, ln, "trace", f"{ident} names unknown flow {f}")
            flows_used.update(fl_ids)
            ent_cell = row[cols["Entities"]]
            ents = ENTITY_LINK_RE.findall(ent_cell)
            if not ents and ent_cell.strip().lower() != "none":
                add(system, ln, "trace", f"{ident} names no entity")
            for e in ents:
                if e not in store_entities:
                    add(system, ln, "trace", f"{ident} names unknown entity #{e}")
            entities_used.update(ents)
            if "](" not in row[cols["Specified in"]]:
                add(system, ln, "trace", f"{ident} links no specifying heading")
    verified: set[str] = set()
    for table in find_tables(lines_by_rel[acceptance]):
        vcol = _column(table.header, "Verifies")
        if vcol is None:
            continue
        for row, ln in zip(table.rows, table.row_lines, strict=True):
            m = DECLARED_ID_RE.match(row[0].strip())
            if not m or not m.group(1).startswith("AC-"):
                continue
            refs = REF_ID_RE.findall(row[vcol])
            if not refs:
                add(acceptance, ln, "trace", f"{m.group(1)} verifies nothing")
            for r in refs:
                if r not in declared:
                    add(acceptance, ln, "trace", f"{m.group(1)} verifies unknown {r}")
            verified.update(refs)
    for ident, ln in obligations.items():
        if ident not in verified:
            add(system, ln, "trace", f"{ident} is verified by no AC- row")
    for ident, priority in b_rows.items():
        if priority in ("P0", "P1") and ident not in realised:
            add("requirements/business.md", declared[ident][1], "trace", f"{ident} is realised by no S- row")
    for fl, (rel, _anchor) in flows.items():
        if fl not in flows_used:
            add(rel, 1, "trace", f"{fl} is named by no requirement")
    for e in sorted(store_entities - entities_used):
        add("architecture/sql-store.md", 1, "trace", f"entity #{e} is named by no requirement")


ANY_ID_RE = re.compile(
    r"\b((?:API|AC|FR|WF|FL|ADR|B|N|RULE)-\d{1,3}|S-[A-Z]{3}-\d{2}|SC-[A-Z])\b"
)
WF_DECL_RE = re.compile(r"^(WF-\d{2}) — ", re.MULTILINE)
SC_DECL_RE = re.compile(r"\*\*`(SC-[A-Z])`")
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def _check_references(
    files: dict[str, str],
    lines_by_rel: dict[str, list[str]],
    declared: dict[str, tuple[str, int]],
    add: Callable[..., None],
) -> None:
    """Every identifier cited exists; families are numbered without gaps unless retired;
    S- rows inherit the highest priority they realise; the release gate lists exactly
    the non-P0 criteria and no scenario names one of them."""
    known = dict(declared)
    for rel, text in files.items():
        for m in WF_DECL_RE.finditer("\n".join(lines_by_rel[rel])):
            known.setdefault(m.group(1), (rel, 0))
        for m in SC_DECL_RE.finditer(text):
            known.setdefault(m.group(1), (rel, 0))
        for h in parse_headings(lines_by_rel[rel]):
            m = re.match(r"^(ADR-\d{2}|FL-\d{2}) ", h.title)
            if m:
                known.setdefault(m.group(1), (rel, h.line))
    glossary = files.get("requirements/glossary.md", "")
    retired = set(ANY_ID_RE.findall(glossary.split("## Retired identifiers", 1)[1])) if (
        "## Retired identifiers" in glossary
    ) else set()
    for rel, text in files.items():
        if rel.startswith("reference/") or rel == build_traceability.TARGET:
            continue
        for n, line in enumerate(lines_by_rel[rel], start=1):
            for ident in ANY_ID_RE.findall(line):
                if ident not in known and ident not in retired:
                    add(rel, n, "reference", f"{ident} is cited but declared nowhere")
    for family in ("API", "AC", "FR", "WF", "FL", "ADR", "B", "N", "RULE"):
        nums = {int(k.rsplit("-", 1)[1]) for k in known if re.fullmatch(rf"{family}-\d+", k)}
        nums |= {int(k.rsplit("-", 1)[1]) for k in retired if re.fullmatch(rf"{family}-\d+", k)}
        gaps = sorted(set(range(1, max(nums, default=0) + 1)) - nums)
        if gaps:
            add("index.md", 1, "numbering", f"{family} numbering has gaps {gaps}")
    tables = {
        rel: find_tables(lines_by_rel[rel])
        for rel in ("requirements/business.md", "requirements/system.md", "requirements/acceptance.md")
        if rel in files
    }
    b_prio: dict[str, str] = {}
    for t in tables.get("requirements/business.md", []):
        p = _column(t.header, "Priority")
        for row in t.rows:
            m = DECLARED_ID_RE.match(row[0].strip())
            if m and p is not None:
                b_prio[m.group(1)] = row[p].strip()
    s_prio: dict[str, str] = {}
    for t in tables.get("requirements/system.md", []):
        p, r = _column(t.header, "Priority"), _column(t.header, "Realises")
        if p is None or r is None:
            continue
        for row, ln in zip(t.rows, t.row_lines, strict=True):
            m = DECLARED_ID_RE.match(row[0].strip())
            if not m:
                continue
            s_prio[m.group(1)] = row[p].strip()
            if m.group(1).startswith("S-"):
                inherited = [b_prio[b] for b in REF_ID_RE.findall(row[r]) if b in b_prio]
                expected = min(inherited, key=PRIORITY_ORDER.__getitem__) if inherited else "P0"
                if row[p].strip() != expected:
                    add("requirements/system.md", ln, "priority",
                        f"{m.group(1)} is {row[p].strip()} but inherits {expected}")
    acceptance = files.get("requirements/acceptance.md", "")
    if "Outside the gate:" not in acceptance:
        return
    outside = set(re.findall(r"`(AC-\d{2})`", acceptance.split("Outside the gate:", 1)[1]))
    for t in tables.get("requirements/acceptance.md", []):
        v = _column(t.header, "Verifies")
        if v is None:
            continue
        for row, ln in zip(t.rows, t.row_lines, strict=True):
            m = DECLARED_ID_RE.match(row[0].strip())
            if not m:
                continue
            prios = [s_prio.get(i) or b_prio.get(i) for i in REF_ID_RE.findall(row[v])]
            prio = min([x for x in prios if x], key=PRIORITY_ORDER.__getitem__, default="P0")
            if (prio != "P0") != (m.group(1) in outside):
                add("requirements/acceptance.md", ln, "gate",
                    f"{m.group(1)} is {prio} but the release gate says otherwise")
    if "## Scenario pass criteria" in acceptance:
        scenarios = acceptance.split("## Scenario pass criteria", 1)[1].split("## Release gate", 1)[0]
        for ac in set(re.findall(r"`(AC-\d{2})`", scenarios)) & outside:
            add("requirements/acceptance.md", 1, "gate", f"a scenario names {ac}, outside the gate")


def _check_tags(
    files: dict[str, str], lines_by_rel: dict[str, list[str]], add: Callable[..., None]
) -> None:
    """A document's tags are exactly the features whose reading order links it (R6)."""
    linkers: dict[str, set[str]] = collections.defaultdict(set)
    for rel in files:
        if not rel.startswith("features/") or rel.endswith("index.md"):
            continue
        heads = parse_headings(lines_by_rel[rel])
        h = next((h for h in heads if h.level == 2 and h.title == "Reading order"), None)
        if h is None:
            add(rel, 1, "tags", "feature has no Reading order")
            continue
        for link in find_links(lines_by_rel[rel], h.line, h.end):
            target = link.target.split("#", 1)[0]
            if target.startswith("/") and target.endswith(".md"):
                linkers[target.lstrip("/")].add(PurePosixPath(rel).stem)
    for rel, text in files.items():
        if rel.startswith(("features/", "guidelines/", "reference/")) or rel.endswith(
            ("index.md", "log.md")
        ) or rel == build_traceability.TARGET:
            continue
        try:
            fm = frontmatter(text) or {}
        except FrontmatterError:
            continue
        tags = set(fm.get("tags") or [])
        if tags != linkers.get(rel, set()):
            add(rel, 1, "tags", f"tags {sorted(tags)} differ from the features whose reading "
                f"order links it: {sorted(linkers.get(rel, set()))}")


def main(root: str) -> int:
    out, nfiles = run(root)
    for line in out:
        print(line)
    print(f"\n{nfiles} files, {len(out)} findings")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else str(_REPO_ROOT / "docs")))
