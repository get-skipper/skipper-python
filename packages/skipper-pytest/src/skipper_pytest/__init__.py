"""skipper-pytest — pytest plugin for Skipper test-gating via Google Spreadsheet."""

from .plugin import configure_skipper

__all__ = ["configure_skipper"]
