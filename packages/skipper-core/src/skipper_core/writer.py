from __future__ import annotations

from typing import Any

from .client import SheetsClient, _index_of
from .config import SkipperConfig
from .logger import logf
from .testid import normalize_test_id


class SheetsWriter:
    """Reconciles a Google Spreadsheet with a set of discovered test IDs.

    Sync behaviour:
    - Rows whose test ID is no longer discovered (and belong to the same files
      as the current sync) are deleted.
    - Newly discovered test IDs are appended with an empty disabledUntil.
    """

    def __init__(self, config: SkipperConfig) -> None:
        self._config = config
        self._client = SheetsClient(config)

    def sync(self, discovered_ids: list[str]) -> None:
        logf("syncing %d discovered test IDs", len(discovered_ids))

        result = self._client.fetch_all()
        primary = result.primary
        svc: Any = result.service

        test_id_idx = _index_of(primary.header, self._config.test_id_column)
        if test_id_idx < 0:
            raise ValueError(
                f"column {self._config.test_id_column!r} not found in sheet {primary.sheet_name!r}"
            )

        discovered_set = {normalize_test_id(id_) for id_ in discovered_ids}

        # Determine which file paths are "owned" by this sync.
        owned_files: set[str] = set()
        owned_bases: set[str] = set()
        for id_ in discovered_ids:
            nid = normalize_test_id(id_)
            sep = nid.find(" > ")
            if sep >= 0:
                file = nid[:sep]
                owned_files.add(file)
                base_sep = file.rfind("/")
                owned_bases.add(file[base_sep + 1 :] if base_sep >= 0 else file)

        existing_map = {normalize_test_id(e.test_id): e.test_id for e in primary.entries}

        # Collect row indices (0-based, after header) to delete.
        rows_to_delete: list[int] = []
        for i, entry in enumerate(primary.entries):
            nid = normalize_test_id(entry.test_id)
            sep = nid.find(" > ")
            if sep < 0:
                # Malformed row — clean it up unconditionally.
                rows_to_delete.append(i + 1)
                continue
            file = nid[:sep]
            owned = file in owned_files
            if not owned and "/" not in file:
                owned = file in owned_bases
            if not owned:
                continue
            if nid not in discovered_set:
                rows_to_delete.append(i + 1)

        # Delete in descending order to avoid index shifting.
        if rows_to_delete:
            rows_to_delete.sort(reverse=True)
            requests = [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": primary.sheet_id,
                            "dimension": "ROWS",
                            "startIndex": row_idx,
                            "endIndex": row_idx + 1,
                        }
                    }
                }
                for row_idx in rows_to_delete
            ]
            svc.spreadsheets().batchUpdate(
                spreadsheetId=self._config.spreadsheet_id,
                body={"requests": requests},
            ).execute()
            logf("deleted %d rows from spreadsheet", len(rows_to_delete))

        # Append new rows.
        to_add = [id_ for id_ in discovered_ids if normalize_test_id(id_) not in existing_map]
        if to_add:
            header_len = len(primary.header)
            values: list[list[Any]] = []
            for id_ in to_add:
                row: list[Any] = [""] * header_len
                row[test_id_idx] = id_
                values.append(row)
            svc.spreadsheets().values().append(
                spreadsheetId=self._config.spreadsheet_id,
                range=primary.sheet_name,
                valueInputOption="RAW",
                body={"values": values},
            ).execute()
            logf("appended %d new test IDs to spreadsheet", len(to_add))
