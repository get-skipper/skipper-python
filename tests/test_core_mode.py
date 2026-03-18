"""Tests for skipper_core.SkipperMode and mode_from_env."""

from __future__ import annotations

import pytest
from skipper_core import SkipperMode, mode_from_env


class TestSkipperMode:
    def test_read_only_is_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SKIPPER_MODE", raising=False)
        assert mode_from_env() == SkipperMode.READ_ONLY

    def test_sync_mode_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SKIPPER_MODE", "sync")
        assert mode_from_env() == SkipperMode.SYNC

    def test_unknown_value_defaults_to_read_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SKIPPER_MODE", "unknown-value")
        assert mode_from_env() == SkipperMode.READ_ONLY

    def test_mode_is_string_comparable(self) -> None:
        assert SkipperMode.READ_ONLY == "read-only"
        assert SkipperMode.SYNC == "sync"
