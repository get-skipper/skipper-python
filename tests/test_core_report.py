"""Tests for skipper_core.report — quarantine debt summary."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from skipper_core.report import build_markdown_summary, build_report, emit_summary


def _future(days: int = 7) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=days)


def _past(days: int = 1) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


class TestBuildReport:
    def test_counts_currently_suppressed(self) -> None:
        entries = {
            "tests/a.py > test_disabled": _future(5),
            "tests/b.py > test_enabled": _past(1),
            "tests/c.py > test_no_date": None,
        }
        report = build_report(entries, suppressed_this_run=[], re_enabled_this_run=[])
        assert report["currently_suppressed"] == 1

    def test_counts_expiring_this_week(self) -> None:
        entries = {
            "tests/a.py > test_soon": _future(3),
            "tests/b.py > test_later": _future(10),
        }
        report = build_report(entries, suppressed_this_run=[], re_enabled_this_run=[])
        assert report["expiring_this_week"] == 1

    def test_quarantine_days_debt(self) -> None:
        entries = {
            "tests/a.py > test_x": _future(5),
            "tests/b.py > test_y": _future(10),
        }
        report = build_report(entries, suppressed_this_run=[], re_enabled_this_run=[])
        # Should be approximately 5 + 10 = 15 (timedelta.days truncates fractions)
        assert 13 <= report["quarantine_days_debt"] <= 17

    def test_suppressed_this_run_included(self) -> None:
        entries = {"tests/a.py > test_x": _future(5)}
        suppressed = ["tests/a.py > test_x"]
        report = build_report(entries, suppressed_this_run=suppressed, re_enabled_this_run=[])
        assert report["suppressed_this_run"] == ["tests/a.py > test_x"]

    def test_re_enabled_this_run_included(self) -> None:
        entries = {}
        re_enabled = ["tests/b.py > test_y"]
        report = build_report(entries, suppressed_this_run=[], re_enabled_this_run=re_enabled)
        assert report["re_enabled_this_run"] == ["tests/b.py > test_y"]

    def test_report_has_generated_at(self) -> None:
        report = build_report({}, suppressed_this_run=[], re_enabled_this_run=[])
        assert "generated_at" in report


class TestBuildMarkdownSummary:
    def test_contains_header(self) -> None:
        report = build_report({}, suppressed_this_run=[], re_enabled_this_run=[])
        md = build_markdown_summary(report)
        assert "## Skipper Quarantine Report" in md

    def test_contains_metrics_table(self) -> None:
        entries = {"tests/a.py > test_x": _future(3)}
        report = build_report(
            entries, suppressed_this_run=["tests/a.py > test_x"], re_enabled_this_run=[]
        )
        md = build_markdown_summary(report)
        assert "Currently suppressed" in md
        assert "Quarantine-days debt" in md

    def test_lists_suppressed_tests(self) -> None:
        entries = {"tests/a.py > test_x": _future(3)}
        report = build_report(
            entries, suppressed_this_run=["tests/a.py > test_x"], re_enabled_this_run=[]
        )
        md = build_markdown_summary(report)
        assert "tests/a.py > test_x" in md

    def test_lists_re_enabled_tests(self) -> None:
        report = build_report(
            {}, suppressed_this_run=[], re_enabled_this_run=["tests/b.py > test_y"]
        )
        md = build_markdown_summary(report)
        assert "tests/b.py > test_y" in md


class TestEmitSummary:
    def test_writes_to_stdout_without_github_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        monkeypatch.chdir(tmp_path)
        report = build_report({}, suppressed_this_run=[], re_enabled_this_run=[])
        emit_summary(report)
        out = capsys.readouterr().out
        assert "Skipper Quarantine Report" in out

    def test_writes_skipper_report_json(self, tmp_path: Path) -> None:
        os.chdir(tmp_path)
        entries = {"tests/a.py > test_x": _future(4)}
        report = build_report(entries, suppressed_this_run=[], re_enabled_this_run=[])
        emit_summary(report)
        report_path = tmp_path / "skipper-report.json"
        assert report_path.exists()
        loaded = json.loads(report_path.read_text())
        assert loaded["currently_suppressed"] == 1

    def test_appends_to_github_step_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        summary_file = tmp_path / "step_summary.md"
        summary_file.write_text("existing content\n")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
        monkeypatch.chdir(tmp_path)

        report = build_report({}, suppressed_this_run=[], re_enabled_this_run=[])
        emit_summary(report)

        content = summary_file.read_text()
        assert "existing content" in content
        assert "Skipper Quarantine Report" in content
