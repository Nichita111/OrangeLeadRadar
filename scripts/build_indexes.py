"""Generates every index.md from frontmatter (docs/guidelines/documents/common.md, R8).

Usage: `uv run --project scripts python scripts/build_indexes.py [--check]`
(--check: exit 1 if any index on disk is stale).
"""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

from docmd import FrontmatterError, frontmatter, frontmatter_lenient

_REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = str(_REPO_ROOT / "docs")
# (folder, display title) for the root index; within a folder, files listed in ORDER come first
FOLDERS = [
    ("reference", "Reference"),
    ("guidelines", "Guidelines"),
    ("guidelines/documents", "Document conventions"),
    ("requirements", "Requirements"),
    ("architecture", "Architecture"),
    ("architecture/adrs", "Decisions"),
    ("architecture/services", "Services"),
    ("features", "Features"),
]
ORDER = {
    "reference": ["challenge-brief", "annex-1-participant-reference-pack"],
    "guidelines": ["coding", "python", "typescript", "testing", "commit-and-pr"],
    "guidelines/documents": ["common", "templates"],
    "requirements": ["business", "system", "acceptance", "traceability", "glossary"],
    "architecture": ["overview", "sql-store", "rules", "interfaces"],
    "architecture/services": ["api", "worker", "frontend"],
    "features": [
        "service-configuration",
        "accounts-and-discovery",
        "signal-pipeline",
        "prospect-dashboard",
        "evaluation-and-feedback",
        "outreach-and-crm",
        "identity-and-access",
        "audit-trail",
    ],
}
ROOT_TITLE = "LeadRadar"
SUMMARISED_IN_ROOT = {"architecture/adrs": "Architecture decision records, one file per ADR"}


def _fields(rel: str, text: str, findings: list[str]) -> dict[str, str]:
    try:
        strict = frontmatter(text)
    except FrontmatterError as exc:
        findings.append(f"{rel}: frontmatter is not valid YAML: {exc}")
        strict = None
    if strict is None and (strict := frontmatter_lenient(text)) is None:
        findings.append(f"{rel}: missing frontmatter")
    fields = {k: str(v) for k, v in (strict or {}).items()}
    findings.extend(
        f"{rel}: frontmatter lacks {k}" for k in ("title", "description") if not fields.get(k)
    )
    return fields


def docs_in(
    folder: str, docs_dir: str, texts: dict[str, str], findings: list[str]
) -> list[tuple[str, dict[str, str]]]:
    full = Path(docs_dir) / folder
    if not full.is_dir():
        return []
    names = sorted(
        p.stem for p in full.iterdir() if p.suffix == ".md" and p.name not in ("index.md", "log.md")
    )
    order = ORDER.get(folder, [])
    names.sort(key=lambda n: (order.index(n) if n in order else len(order), n))

    def _read(n: str) -> dict[str, str]:
        rel = f"{folder}/{n}.md"
        return _fields(rel, texts.get(rel) or (full / f"{n}.md").read_text(encoding="utf-8"), findings)

    return [(n, _read(n)) for n in names]


def line(title: str, href: str, desc: str) -> str:
    return f"* [{title}]({href}) - {desc}"


def root_index(docs_dir: str, texts: dict[str, str], findings: list[str]) -> str:
    out = [
        "---",
        'okf_version: "0.2"',
        "---",
        "",
        f"# {ROOT_TITLE}",
        "",
        line("Update log", "log.md", "What changed in this bundle, newest first"),
    ]
    for folder, title in FOLDERS:
        out += ["", f"# {title}", ""]
        if folder in SUMMARISED_IN_ROOT:
            out.append(line(title, f"{folder}/index.md", SUMMARISED_IN_ROOT[folder]))
            continue
        out += [
            line(fm.get("title") or n, f"{folder}/{n}.md", fm.get("description") or "")
            for n, fm in docs_in(folder, docs_dir, texts, findings)
        ]
    return "\n".join(out) + "\n"


def folder_index(
    folder: str, title: str, docs_dir: str, texts: dict[str, str], findings: list[str]
) -> str:
    out = [f"# {title}", ""]
    out += [
        line(fm.get("title") or n, f"{n}.md", fm.get("description") or "")
        for n, fm in docs_in(folder, docs_dir, texts, findings)
    ]
    subs = [(f, t) for f, t in FOLDERS if PurePosixPath(f).parent.as_posix() == folder]
    if subs:
        out += [""] + [
            line(t, f"{PurePosixPath(f).name}/index.md", f"Index of {t.lower()}") for f, t in subs
        ]
    return "\n".join(out) + "\n"


def generated(
    docs_dir: str = DOCS, texts: dict[str, str] | None = None
) -> tuple[dict[str, str], list[str]]:
    """`({rel_index_path: content}, findings)`."""
    texts = texts or {}
    findings: list[str] = []
    files = {"index.md": root_index(docs_dir, texts, findings)}
    for folder, title in FOLDERS:
        files[f"{folder}/index.md"] = folder_index(folder, title, docs_dir, texts, findings)
    return files, sorted(set(findings))


def main() -> None:
    check = "--check" in sys.argv
    stale: list[str] = []
    files, findings = generated(DOCS)
    for rel, content in files.items():
        path = Path(DOCS) / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(rel)
        if not check:
            path.write_text(content, encoding="utf-8")
    for msg in findings:
        print(msg)
    if check:
        for rel in stale:
            print(f"{rel}: stale index; run scripts/build_indexes.py")
        print(f"{len(files)} indexes, {len(stale)} stale")
        sys.exit(1 if (stale or findings) else 0)
    print(f"{len(files)} indexes written ({len(stale)} changed)")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
