from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .credentials import Credentials


@dataclasses.dataclass(frozen=True)
class SkipperConfig:
    spreadsheet_id: str
    credentials: "Credentials"
    sheet_name: str | None = None
    reference_sheets: tuple[str, ...] = ()
    # Column header names in the spreadsheet (camelCase matches all other ports).
    test_id_column: str = "testId"
    disabled_until_column: str = "disabledUntil"
