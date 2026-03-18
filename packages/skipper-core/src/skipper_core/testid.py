from __future__ import annotations

import contextlib
import re
from pathlib import Path

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_test_id(test_id: str) -> str:
    """Lowercase, strip, and collapse whitespace for case-insensitive matching."""
    return _WHITESPACE_RE.sub(" ", test_id.strip().lower())


def build_test_id(file_path: str, title_parts: list[str]) -> str:
    """Build a test ID in the format: 'path/to/test.py > part1 > part2'.

    If file_path is absolute it is made relative to the project root
    (located by searching for pyproject.toml or setup.py).
    Path separators are normalised to forward slashes.
    """
    rel = _to_relative_path(file_path)
    return " > ".join([rel, *title_parts])


def _to_relative_path(file_path: str) -> str:
    p = Path(file_path)
    if p.is_absolute():
        root = _find_project_root(p)
        if root is None:
            import os

            root = Path(os.getcwd())
        with contextlib.suppress(ValueError):
            p = p.relative_to(root)
    return str(p).replace("\\", "/")


def _find_project_root(file_path: Path) -> Path | None:
    """Walk up looking for pyproject.toml (workspace root) or setup.py (module root)."""
    # Prefer pyproject.toml (uv workspace) over setup.py (legacy).
    pyproject_root: Path | None = None
    for parent in [file_path.parent, *file_path.parent.parents]:
        if (parent / "pyproject.toml").exists():
            # Keep walking up — we want the *outermost* pyproject.toml
            # (i.e., the workspace root, not a sub-package root).
            pyproject_root = parent
        if (parent / "uv.lock").exists():
            # uv workspace root — highest priority, stop immediately.
            return parent
    if pyproject_root is not None:
        return pyproject_root
    # Fallback: look for setup.py
    for parent in [file_path.parent, *file_path.parent.parents]:
        if (parent / "setup.py").exists():
            return parent
    return None
