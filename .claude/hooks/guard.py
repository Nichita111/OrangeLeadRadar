#!/usr/bin/env python3
"""PreToolUse guard for the /implement chain: keeps each agent inside its lane.

Usage (from an agent's frontmatter hook): guard.py <architect|coder|qa|critic>
Reads the hook JSON on stdin; exits 2 with a reason on stderr to block the tool call,
0 to allow it. The lanes are those of AGENTS.md.

The coder is also held by the approval gate in .work/gate.json, which only the /implement
orchestrator writes: in phase "docs" the coder may change only docs/, and code opens only
when a human has approved the resulting docs diff and the orchestrator sets phase "code",
in which docs/ is frozen. Without a gate the coder may write nothing.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
WORK = ".work/"
GATE = ".work/gate.json"
PHASES = ("docs", "code")

# Work-directory files each role may write; every other role only reads them.
WORK_FILES = {
    "architect": {"design.md"},
    "coder": {"coder-notes.md"},
    "qa": {"qa-report.md"},
    "critic": {"review.md"},
}
# Where each role may write outside the work directory; None means anywhere not denied.
WRITE_ALLOW: dict[str, list[str] | None] = {
    "architect": [],
    "critic": [],
    "qa": ["tests/acceptance/", "tests/e2e/"],
    "coder": None,
}
CODER_WRITE_DENY = [
    "tests/acceptance/",
    "tests/e2e/",
    ".claude/agents/",
    ".claude/hooks/",
    ".claude/skills/",
    ".claude/settings.json",
    "docs/reference/",
    "docs/requirements/traceability.md",
]
# QA reads only the specification: never the implementation or the notes about it.
QA_READ_DENY = ["apps/", "packages/"]
QA_READ_DENY_WORK = {"design.md", "coder-notes.md", "review.md"}
QA_SEARCH_ALLOW = ["docs/", "tests/", "fixtures/", "scripts/"]

READONLY_BASH = re.compile(
    r"\bgit\s+(commit|push|checkout|switch|reset|rebase|merge|stash|add|rm|mv|restore|clean|tag|cherry-pick)\b"
    r"|\b(rm|mv|cp|tee|touch|mkdir|chmod)\s"
    r"|\bsed\s+-i"
    r"|(?<![0-9&])>>?\s*(?!/dev/null|&)\S"
)
CODER_BASH_PROTECTED = [*CODER_WRITE_DENY[:6], GATE]
CODER_BASH_DENY = re.compile(r"\bgit\s+(push|commit|reset\s+--hard|clean|checkout\s+--)\b")
WRITE_OPS = re.compile(r"(?<![0-9&])>>?|\btee\b|\bsed\s+-i|\b(rm|mv|cp)\s")
QA_BASH_DENY = re.compile(
    r"(^|[\s'\"=:(/])(\./)?(apps|packages)/"
    r"|\bgit\s+(?!status\b)\w"
    r"|\bdocker\s+(compose\s+)?cp\b"
    r"|\bexec\b.*\b(cat|less|more|head|tail|grep|rg|find|ls|sed|awk|strings)\b"
)


def block(reason: str) -> None:
    print(f"Blocked by the /implement guard: {reason}", file=sys.stderr)
    sys.exit(2)


def rel(path: str | None, cwd: str) -> str | None:
    """Project-relative POSIX path, or None when the path is outside the project."""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = Path(cwd or ROOT) / p
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def work_file(r: str) -> str | None:
    """File name inside .work/<task>/, or None."""
    if not r.startswith(WORK):
        return None
    parts = r[len(WORK):].split("/")
    return parts[1] if len(parts) == 2 else None


def gate_phase() -> str | None:
    """The coder's current phase from the orchestrator's gate file, or None."""
    try:
        phase = json.loads((ROOT / GATE).read_text(encoding="utf-8")).get("phase")
    except (OSError, ValueError, AttributeError):
        return None
    return phase if phase in PHASES else None


def check_coder_phase(r: str) -> None:
    phase = gate_phase()
    if phase is None:
        block("no approved phase is open for the coder: the /implement orchestrator opens the "
              "docs or code phase in .work/gate.json after a human approval.")
    if phase == "docs" and not r.startswith("docs/"):
        block(f"docs phase: only document changes are allowed until a human approves the docs "
              f"diff; {r} is not under docs/. Finish the document changes and stop.")
    if phase == "code" and r.startswith("docs/"):
        block(f"code phase: documents are frozen after approval, so {r} cannot change now. "
              "Record the needed change in coder-notes.md under Disputes and gaps and stop, "
              "so a human can approve it first.")


def check_write(role: str, r: str | None, raw: str) -> None:
    if r is None:
        block(f"{role} may not write outside the project ({raw}).")
    if r.startswith(WORK):
        name = work_file(r)
        if name not in WORK_FILES[role]:
            block(f"{role} may write only {sorted(WORK_FILES[role])} in the task's work directory, not {r}.")
        return
    allow = WRITE_ALLOW[role]
    if allow is None:
        if any(r == d.rstrip("/") or r.startswith(d) for d in CODER_WRITE_DENY):
            block(f"the coder may not write {r}: acceptance and end-to-end tests belong to QA, "
                  "agent definitions and the reference brief are not the coder's, and generated "
                  "files are rebuilt by scripts/.")
        if re.fullmatch(r"docs/(.+/)?index\.md", r):
            block(f"{r} is generated; run scripts/build_indexes.py instead.")
        check_coder_phase(r)
        return
    if not any(r.startswith(a) for a in allow):
        where = ", ".join(allow) if allow else "nowhere but its work file"
        block(f"{role} may write only under {where}; not {r}.")


def check_qa_read(r: str | None) -> None:
    if r is None:
        return
    if any(r == d.rstrip("/") or r.startswith(d) for d in QA_READ_DENY):
        block(f"QA writes tests from the specification only and may not read {r}. "
              "Use docs/ (acceptance criteria, interfaces, demo dataset) and the running stack.")
    if r.startswith(WORK) and work_file(r) in QA_READ_DENY_WORK:
        block(f"QA may not read {r}: it describes the implementation. Read task.md and docs/.")


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else ""
    if role not in WORK_FILES:
        block(f"unknown role {role!r}.")
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input", {}) or {}
    cwd = data.get("cwd", "") or str(ROOT)

    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        raw = tin.get("file_path") or tin.get("notebook_path") or ""
        check_write(role, rel(raw, cwd), raw)
    elif tool == "Read" and role == "qa":
        check_qa_read(rel(tin.get("file_path"), cwd))
    elif tool in ("Grep", "Glob") and role == "qa":
        target = rel(tin.get("path") or cwd, cwd)
        pattern = f"{tin.get('pattern', '')} {tin.get('glob', '')}"
        if re.search(r"(^|[/\s*])(apps|packages)(/|\b)", pattern):
            block("QA may not search the implementation.")
        if target is None or not any(target.startswith(a.rstrip("/")) for a in QA_SEARCH_ALLOW):
            block(f"QA searches must name a path under {', '.join(QA_SEARCH_ALLOW)}; "
                  f"searching {target or 'outside the project'} would include the implementation.")
        check_qa_read(target)
    elif tool == "Bash":
        cmd = tin.get("command", "")
        if role in ("architect", "critic") and READONLY_BASH.search(cmd):
            block(f"{role} is read-only: commands that change files or git state are not allowed "
                  f"({cmd[:80]}).")
        if role == "coder":
            if CODER_BASH_DENY.search(cmd):
                block("the coder does not commit, push or discard work; the /implement "
                      "orchestrator commits once the Critic passes.")
            if WRITE_OPS.search(cmd) and any(d in cmd for d in CODER_BASH_PROTECTED):
                block("the coder may not change QA's tests, the chain's own files or the approval "
                      "gate from the shell.")
            phase = gate_phase()
            if WRITE_OPS.search(cmd):
                if phase == "docs" and re.search(r"(^|[\s'\"=:(/])(\./)?(apps|packages|tests)/", cmd):
                    block("docs phase: shell commands may not change code or tests yet.")
                if phase == "code" and re.search(r"(^|[\s'\"=:(/])(\./)?docs/", cmd):
                    block("code phase: documents are frozen; record the needed change in "
                          "coder-notes.md and stop.")
        if role == "qa" and QA_BASH_DENY.search(cmd):
            block("QA may run the stack and its tests but may not read the implementation, "
                  "use git history, or copy files out of containers.")
        if role == "qa":
            for token in re.findall(r"\.work/\S*", cmd):
                if not re.search(r"/(task|qa-report)\.md['\"]?$", token):
                    block("QA may use only task.md and qa-report.md of the task directory.")
        if role == "qa" and WRITE_OPS.search(cmd):
            targets = re.findall(r"(?:>>?|tee\s+(?:-a\s+)?)\s*([^\s;|&]+)", cmd)
            for t in targets:
                if t != "/dev/null":
                    check_write(role, rel(t, cwd), t)
    sys.exit(0)


if __name__ == "__main__":
    main()
