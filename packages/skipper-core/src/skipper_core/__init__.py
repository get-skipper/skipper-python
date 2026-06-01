"""skipper-core — Google Sheets client and resolver for Skipper test-gating."""

from .cache import CacheManager
from .client import FetchAllResult, SheetFetchResult, SheetsClient, TestEntry
from .config import SkipperConfig
from .credentials import Base64Credentials, Credentials, FileCredentials, ServiceAccountCredentials
from .logger import log, logf, warn
from .mode import SkipperMode, mode_from_env
from .report import build_report, emit_summary
from .resolver import SkipperResolver
from .testid import build_test_id, normalize_test_id
from .writer import SheetsWriter

__all__ = [
    "CacheManager",
    "FetchAllResult",
    "SheetFetchResult",
    "SheetsClient",
    "SheetsWriter",
    "SkipperConfig",
    "SkipperMode",
    "SkipperResolver",
    "TestEntry",
    # Credentials
    "Base64Credentials",
    "Credentials",
    "FileCredentials",
    "ServiceAccountCredentials",
    # Helpers
    "build_report",
    "build_test_id",
    "emit_summary",
    "log",
    "logf",
    "mode_from_env",
    "normalize_test_id",
    "warn",
]
