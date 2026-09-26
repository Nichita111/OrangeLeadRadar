"""[Package layout](/guidelines/python.md#package-layout): `core` imports nothing from `db`,
`api`, `ai`, `plugins` or `worker`, and no I/O library. `db` and the capability packages (for
example `audit`) do not import `api`: dependencies point one way, route or job handler →
capability function → store access ([Coding Structure](/guidelines/coding.md#structure), "a
cycle between layers is a design defect"). An `ast` walk needs no new dependency."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "leadradar"
CORE_DIR = SRC_DIR / "core"
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


@pytest.mark.parametrize("package", ["db", "audit"])
def test_store_and_capability_packages_do_not_import_api(package: str) -> None:
    python_files = list((SRC_DIR / package).rglob("*.py"))
    assert python_files, f"expected {package}/ to contain modules"

    for path in python_files:
        tree = ast.parse(path.read_text(), filename=str(path))
        roots = _imported_module_roots(tree)
        assert "api" not in roots, f"{path} imports the api package, a layering cycle"
