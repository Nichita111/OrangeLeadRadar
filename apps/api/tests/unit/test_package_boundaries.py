"""[Package layout](/guidelines/python.md#package-layout): `core` imports nothing from `db`,
`api`, `ai`, `plugins` or `worker`, and no I/O library. An `ast` walk needs no new dependency."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "leadradar" / "core"
FORBIDDEN_PACKAGES = {"db", "api", "ai", "plugins", "worker"}
FORBIDDEN_IO_MODULES = {
    "socket",
    "asyncio",
    "httpx",
    "requests",
    "sqlalchemy",
    "psycopg",
    "aiohttp",
}


def _imported_module_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "leadradar" and len(parts) > 1:
                roots.add(parts[1])
            else:
                roots.add(parts[0])
    return roots


def test_core_has_no_forbidden_import() -> None:
    python_files = list(CORE_DIR.rglob("*.py"))
    assert python_files, "expected core/ to contain modules"

    for path in python_files:
        tree = ast.parse(path.read_text(), filename=str(path))
        roots = _imported_module_roots(tree)
        forbidden = roots & (FORBIDDEN_PACKAGES | FORBIDDEN_IO_MODULES)
        assert not forbidden, f"{path} imports forbidden module(s): {forbidden}"
