import logging
import os

_logger = logging.getLogger("skipper")
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("[skipper] %(message)s"))
_logger.addHandler(_handler)
_logger.propagate = False


def _is_debug_enabled() -> bool:
    return bool(os.getenv("SKIPPER_DEBUG"))


def log(msg: str) -> None:
    if _is_debug_enabled():
        _logger.setLevel(logging.DEBUG)
        _logger.debug(msg)


def logf(fmt: str, *args: object) -> None:
    if _is_debug_enabled():
        _logger.setLevel(logging.DEBUG)
        _logger.debug(fmt, *args)


def warn(msg: str) -> None:
    if _is_debug_enabled():
        _logger.setLevel(logging.DEBUG)
        _logger.warning("WARN: %s", msg)
