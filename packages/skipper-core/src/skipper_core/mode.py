import os
from enum import Enum


class SkipperMode(str, Enum):
    READ_ONLY = "read-only"
    SYNC = "sync"


def mode_from_env() -> SkipperMode:
    if os.getenv("SKIPPER_MODE") == "sync":
        return SkipperMode.SYNC
    return SkipperMode.READ_ONLY
