"""skipper-core report — quarantine debt summary emitted at the end of every session."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def build_report(
    all_entries: dict[str, datetime | None],
    suppressed_this_run: list[str],
    re_enabled_this_run: list[str],
) -> dict[str, Any]:
    """Build a quarantine debt report from resolver state.

    Args:
        all_entries: mapping of normalized test ID → disabledUntil (from resolver cache).
        suppressed_this_run: test IDs that were skipped by Skipper in this session.
        re_enabled_this_run: test IDs that were in the sheet but ran normally (date expired).
    """
    now = datetime.now(tz=timezone.utc)
    week_later = now + timedelta(days=7)

    active_disabled = {k: v for k, v in all_entries.items() if v is not None and v > now}
    expiring_this_week = [k for k, v in active_disabled.items() if v <= week_later]
    quarantine_days = sum(max(0, (v - now).days) for v in active_disabled.values())

    return {
        "generated_at": now.isoformat(),
        "currently_suppressed": len(active_disabled),
        "suppressed_this_run": sorted(suppressed_this_run),
        "expiring_this_week": len(expiring_this_week),
        "re_enabled_this_run": sorted(re_enabled_this_run),
        "quarantine_days_debt": quarantine_days,
    }


def build_markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "## Skipper Quarantine Report\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Currently suppressed | {report['currently_suppressed']} |",
        f"| Suppressed this run | {len(report['suppressed_this_run'])} |",
        f"| Expiring this week | {report['expiring_this_week']} |",
        f"| Re-enabled this run | {len(report['re_enabled_this_run'])} |",
        f"| Quarantine-days debt | {report['quarantine_days_debt']} |",
        "",
    ]
    if report["suppressed_this_run"]:
        lines += ["### Suppressed this run", ""]
        for tid in report["suppressed_this_run"]:
            lines.append(f"- `{tid}`")
        lines.append("")
    if report["re_enabled_this_run"]:
        lines += ["### Re-enabled this run", ""]
        for tid in report["re_enabled_this_run"]:
            lines.append(f"- `{tid}`")
        lines.append("")
    return "\n".join(lines)


def emit_summary(report: dict[str, Any]) -> None:
    """Write the markdown summary to GITHUB_STEP_SUMMARY (or stdout) and skipper-report.json."""
    md = build_markdown_summary(report)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with Path(summary_file).open("a", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md)
    Path("skipper-report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
