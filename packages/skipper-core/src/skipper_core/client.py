from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from google.oauth2 import service_account  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from .config import SkipperConfig
from .logger import logf, warn
from .testid import normalize_test_id

_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


@dataclasses.dataclass
class TestEntry:
    test_id: str
    disabled_until: datetime | None  # None = no date → test is enabled
    notes: str = ""


@dataclasses.dataclass
class SheetFetchResult:
    sheet_name: str
    sheet_id: int
    header: list[str]
    entries: list[TestEntry]


@dataclasses.dataclass
class FetchAllResult:
    primary: SheetFetchResult
    entries: list[TestEntry]  # merged from primary + reference sheets
    service: Any  # googleapiclient Resource — reused by SheetsWriter


class SheetsClient:
    def __init__(self, config: SkipperConfig) -> None:
        self._config = config

    def fetch_all(self) -> FetchAllResult:
        cred_json = self._config.credentials.resolve()
        import json as _json

        info = _json.loads(cred_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=[_SHEETS_SCOPE])
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

        spreadsheet = svc.spreadsheets().get(spreadsheetId=self._config.spreadsheet_id).execute()

        primary_name = self._config.sheet_name
        if not primary_name:
            sheets = spreadsheet.get("sheets", [])
            primary_name = sheets[0]["properties"]["title"] if sheets else ""

        primary = self._fetch_sheet(svc, primary_name, spreadsheet)

        merged = _merge_entries([], primary.entries)

        for ref_name in self._config.reference_sheets:
            try:
                ref = self._fetch_sheet(svc, ref_name, spreadsheet)
                merged = _merge_entries(merged, ref.entries)
            except Exception as exc:
                warn(f"cannot fetch reference sheet {ref_name!r}: {exc}")

        return FetchAllResult(primary=primary, entries=merged, service=svc)

    def _fetch_sheet(
        self,
        svc: Any,
        sheet_name: str,
        spreadsheet: dict[str, Any],
    ) -> SheetFetchResult:
        resp = (
            svc.spreadsheets()
            .values()
            .get(spreadsheetId=self._config.spreadsheet_id, range=sheet_name)
            .execute()
        )
        values: list[list[Any]] = resp.get("values", [])

        if not values:
            return SheetFetchResult(
                sheet_name=sheet_name,
                sheet_id=_sheet_id_by_name(spreadsheet, sheet_name),
                header=[],
                entries=[],
            )

        header = [str(v) for v in values[0]]
        test_id_idx = _index_of(header, self._config.test_id_column)
        disabled_until_idx = _index_of(header, self._config.disabled_until_column)
        notes_idx = _index_of(header, "notes")

        if test_id_idx < 0:
            raise ValueError(
                f"column {self._config.test_id_column!r} not found in sheet {sheet_name!r}"
            )

        entries: list[TestEntry] = []
        for row in values[1:]:
            if test_id_idx >= len(row):
                continue
            test_id = str(row[test_id_idx]).strip()
            if not test_id:
                continue

            disabled_until: datetime | None = None
            if disabled_until_idx >= 0 and disabled_until_idx < len(row):
                raw = str(row[disabled_until_idx]).strip()
                if raw:
                    parsed = _parse_date(raw)
                    if parsed is not None:
                        disabled_until = parsed
                    else:
                        warn(f"cannot parse disabledUntil {raw!r} for test {test_id!r}")

            notes = ""
            if notes_idx >= 0 and notes_idx < len(row):
                notes = str(row[notes_idx])

            entries.append(TestEntry(test_id=test_id, disabled_until=disabled_until, notes=notes))

        logf("fetched %d entries from sheet %r", len(entries), sheet_name)
        return SheetFetchResult(
            sheet_name=sheet_name,
            sheet_id=_sheet_id_by_name(spreadsheet, sheet_name),
            header=header,
            entries=entries,
        )


def _merge_entries(existing: list[TestEntry], incoming: list[TestEntry]) -> list[TestEntry]:
    """Merge incoming entries, keeping the most restrictive (latest) disabledUntil."""
    idx: dict[str, int] = {}
    result = list(existing)
    for i, e in enumerate(result):
        idx[normalize_test_id(e.test_id)] = i

    for e in incoming:
        nid = normalize_test_id(e.test_id)
        if nid in idx:
            current = result[idx[nid]].disabled_until
            if _more_restrictive(e.disabled_until, current):
                result[idx[nid]] = dataclasses.replace(
                    result[idx[nid]], disabled_until=e.disabled_until
                )
        else:
            idx[nid] = len(result)
            result.append(e)

    return result


def _more_restrictive(candidate: datetime | None, current: datetime | None) -> bool:
    if candidate is None:
        return False
    if current is None:
        return True
    return candidate > current


def _parse_date(s: str) -> datetime | None:

    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                # Treat as end-of-day UTC so the full day is disabled.
                dt = dt.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _index_of(header: list[str], col: str) -> int:
    try:
        return header.index(col)
    except ValueError:
        return -1


def _sheet_id_by_name(spreadsheet: dict[str, Any], name: str) -> int:
    for s in spreadsheet.get("sheets", []):
        if s["properties"]["title"] == name:
            return int(s["properties"]["sheetId"])
    return 0
