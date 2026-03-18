"""Tests for skipper_core.CacheManager."""

from __future__ import annotations

import json
import os
import tempfile

from skipper_core import CacheManager


class TestCacheManager:
    def setup_method(self) -> None:
        self.manager = CacheManager()

    def test_write_and_read_resolver_cache(self) -> None:
        data = b'{"key": "value"}'
        tmpdir = self.manager.write_resolver_cache(data)
        try:
            cache_file = os.path.join(tmpdir, "cache.json")
            assert os.path.exists(cache_file)
            read_back = self.manager.read_resolver_cache(cache_file)
            assert read_back == data
        finally:
            self.manager.cleanup(tmpdir)

    def test_cleanup_removes_directory(self) -> None:
        tmpdir = self.manager.write_resolver_cache(b"{}")
        assert os.path.isdir(tmpdir)
        self.manager.cleanup(tmpdir)
        assert not os.path.exists(tmpdir)

    def test_write_discovered_ids_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ids = ["tests/test_a.py > test_one", "tests/test_b.py > test_two"]
            self.manager.write_discovered_ids(tmpdir, ids)
            files = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            assert len(files) == 1
            with open(os.path.join(tmpdir, files[0])) as fh:
                content = json.loads(fh.read())
            assert content == ids

    def test_merge_discovered_ids_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.manager.write_discovered_ids(tmpdir, ["test_a", "test_b"])
            self.manager.write_discovered_ids(tmpdir, ["test_b", "test_c"])
            merged = self.manager.merge_discovered_ids(tmpdir)
            assert sorted(merged) == ["test_a", "test_b", "test_c"]

    def test_merge_discovered_ids_ignores_cache_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a cache.json that should not be counted as discovered IDs.
            with open(os.path.join(tmpdir, "cache.json"), "w") as fh:
                fh.write('{"key": null}')
            self.manager.write_discovered_ids(tmpdir, ["test_a"])
            merged = self.manager.merge_discovered_ids(tmpdir)
            assert merged == ["test_a"]

    def test_merge_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assert self.manager.merge_discovered_ids(tmpdir) == []

    def test_cleanup_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "skipper-abc")
            os.makedirs(subdir)
            self.manager.cleanup(subdir)
            self.manager.cleanup(subdir)  # should not raise
