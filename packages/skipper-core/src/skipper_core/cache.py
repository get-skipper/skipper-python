from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from .logger import logf, warn

_CACHE_FILE_NAME = "cache.json"


class CacheManager:
    """Manages the temporary directory for sharing resolver state between processes."""

    def write_resolver_cache(self, data: bytes) -> str:
        """Write cache bytes to a temp directory. Returns the directory path.

        Set SKIPPER_CACHE_FILE to <dir>/cache.json so worker processes can
        rehydrate the resolver without re-fetching from Google Sheets.
        """
        tmpdir = tempfile.mkdtemp(prefix="skipper-")
        path = os.path.join(tmpdir, _CACHE_FILE_NAME)
        Path(path).write_bytes(data)
        logf("wrote resolver cache to %s", path)
        return tmpdir

    def read_resolver_cache(self, cache_file: str) -> bytes:
        """Read serialized resolver data from the given file path."""
        return Path(cache_file).read_bytes()

    def write_discovered_ids(self, directory: str, ids: list[str]) -> None:
        """Write discovered test IDs to a uniquely-named file in directory."""
        name = f"{os.getpid()}-{time.time_ns()}-{secrets.token_hex(4)}.json"
        path = os.path.join(directory, name)
        Path(path).write_text(json.dumps(ids), encoding="utf-8")

    def merge_discovered_ids(self, directory: str) -> list[str]:
        """Read all per-process discovered ID files, deduplicate, and return combined list."""
        seen: set[str] = set()
        result: list[str] = []

        for entry in sorted(Path(directory).iterdir()):
            if entry.is_dir() or entry.name == _CACHE_FILE_NAME or entry.suffix != ".json":
                continue
            try:
                ids: list[str] = json.loads(entry.read_text(encoding="utf-8"))
                for id_ in ids:
                    if id_ not in seen:
                        seen.add(id_)
                        result.append(id_)
            except Exception as exc:
                warn(f"cannot read discovered file {entry.name!r}: {exc}")

        return result

    def cleanup(self, directory: str) -> None:
        """Remove the temp directory and all its contents."""
        import shutil

        shutil.rmtree(directory, ignore_errors=True)
