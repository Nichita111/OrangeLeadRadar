#!/usr/bin/env python3
"""Checks guard.py lane by lane: `python3 .claude/hooks/test_guard.py`; exit 1 on any mismatch."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / ".claude/hooks/guard.py"
GATE = ROOT / ".work/gate.json"
R = str(ROOT)

# (role, tool, tool_input, allowed[, gate phase: "docs", "code" or None; default "code"])
CASES = [
    ("architect", "Write", {"file_path": f"{R}/.work/t1/design.md"}, True),
    ("architect", "Write", {"file_path": f"{R}/.work/t1/task.md"}, False),
    ("architect", "Write", {"file_path": f"{R}/docs/architecture/rules.md"}, False),
    ("architect", "Edit", {"file_path": f"{R}/apps/api/x.py"}, False),
    ("architect", "Bash", {"command": "git diff main...HEAD --stat"}, True),
    ("architect", "Bash", {"command": "uv run --project scripts python scripts/check_docs.py 2>&1 | tail -5"}, True),
    ("architect", "Bash", {"command": "echo x > notes.txt"}, False),
    ("architect", "Bash", {"command": "git checkout -b foo"}, False),
    ("critic", "Write", {"file_path": f"{R}/.work/t1/review.md"}, True),
    ("critic", "Edit", {"file_path": f"{R}/apps/api/x.py"}, False),
    ("critic", "Bash", {"command": "rm -rf apps"}, False),
    ("coder", "Write", {"file_path": f"{R}/apps/api/src/leadradar/core/scoring.py"}, True),
    ("coder", "Write", {"file_path": f"{R}/docs/architecture/rules.md"}, True, "docs"),
    # the approval gate
    ("coder", "Write", {"file_path": f"{R}/apps/api/x.py"}, False, None),
    ("coder", "Write", {"file_path": f"{R}/docs/architecture/rules.md"}, False, None),
    ("coder", "Write", {"file_path": f"{R}/.work/t1/coder-notes.md"}, True, None),
    ("coder", "Write", {"file_path": f"{R}/apps/api/x.py"}, False, "docs"),
    ("coder", "Write", {"file_path": f"{R}/apps/api/tests/unit/test_x.py"}, False, "docs"),
    ("coder", "Bash", {"command": "echo x > apps/api/x.py"}, False, "docs"),
    ("coder", "Bash", {"command": "uv run --project scripts python scripts/build_indexes.py"}, True, "docs"),
    ("coder", "Write", {"file_path": f"{R}/docs/architecture/rules.md"}, False, "code"),
    ("coder", "Write", {"file_path": f"{R}/docs/log.md"}, False, "code"),
    ("coder", "Bash", {"command": "sed -i '' s/a/b/ docs/architecture/rules.md"}, False, "code"),
    ("coder", "Write", {"file_path": f"{R}/.work/t1/coder-notes.md"}, True, "code"),
    ("coder", "Write", {"file_path": f"{R}/.work/gate.json"}, False, "docs"),
    ("coder", "Bash", {"command": "echo '{\"phase\": \"code\"}' > .work/gate.json"}, False, "docs"),
    ("architect", "Write", {"file_path": f"{R}/.work/gate.json"}, False),
    ("coder", "Write", {"file_path": f"{R}/.work/t1/coder-notes.md"}, True),
    ("coder", "Write", {"file_path": f"{R}/.work/t1/review.md"}, False),
    ("coder", "Write", {"file_path": f"{R}/tests/acceptance/test_x.py"}, False),
    ("coder", "Write", {"file_path": f"{R}/docs/features/index.md"}, False),
    ("coder", "Write", {"file_path": f"{R}/docs/requirements/traceability.md"}, False),
    ("coder", "Write", {"file_path": f"{R}/.claude/agents/critic.md"}, False),
    ("coder", "Write", {"file_path": "/etc/hosts"}, False),
    ("coder", "Bash", {"command": "git commit -m x"}, False),
    ("coder", "Bash", {"command": "sed -i '' s/a/b/ tests/acceptance/test_x.py"}, False),
    ("coder", "Bash", {"command": "uv run pytest apps/api/tests -q"}, True),
]


def set_gate(phase: str | None) -> None:
    if phase is None:
        GATE.unlink(missing_ok=True)
    else:
        GATE.parent.mkdir(exist_ok=True)
        GATE.write_text(json.dumps({"task": "t1", "phase": phase}), encoding="utf-8")


def main() -> int:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": R}
    saved = GATE.read_text(encoding="utf-8") if GATE.exists() else None
    bad = 0
    try:
        bad = run_cases(env)
    finally:
        if saved is None:
            GATE.unlink(missing_ok=True)
        else:
            GATE.write_text(saved, encoding="utf-8")
    print(f"{len(CASES)} cases, {bad} mismatches")
    return 1 if bad else 0


def run_cases(env: dict[str, str]) -> int:
    bad = 0
    for role, tool, tin, allowed, *rest in CASES:
        set_gate(rest[0] if rest else "code")
        payload = json.dumps({"tool_name": tool, "tool_input": tin, "cwd": R})
        p = subprocess.run(
            [sys.executable, str(GUARD), role], input=payload, capture_output=True, text=True, env=env, check=False
        )
        if (p.returncode == 0) != allowed:
            bad += 1
            print(f"MISMATCH {role} {tool} {tin} -> exit {p.returncode}: {p.stderr.strip()[:120]}")
    return bad


if __name__ == "__main__":
    sys.exit(main())
