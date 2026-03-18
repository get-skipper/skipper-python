"""Tests for skipper_core.testid utilities."""

from skipper_core import build_test_id, normalize_test_id


class TestNormalizeTestId:
    def test_lowercases_input(self) -> None:
        assert normalize_test_id("Login Test") == "login test"

    def test_trims_leading_trailing_whitespace(self) -> None:
        assert normalize_test_id("  test_foo  ") == "test_foo"

    def test_collapses_internal_whitespace(self) -> None:
        assert normalize_test_id("test  foo   bar") == "test foo bar"

    def test_preserves_separator(self) -> None:
        assert normalize_test_id("tests/auth.py > Login > test_login") == (
            "tests/auth.py > login > test_login"
        )

    def test_empty_string(self) -> None:
        assert normalize_test_id("") == ""

    def test_idempotent(self) -> None:
        once = normalize_test_id("  My TEST  ")
        assert normalize_test_id(once) == once


class TestBuildTestId:
    def test_relative_path_with_single_title(self) -> None:
        result = build_test_id("tests/test_auth.py", ["test_login"])
        assert result == "tests/test_auth.py > test_login"

    def test_relative_path_with_multiple_title_parts(self) -> None:
        result = build_test_id("tests/test_auth.py", ["AuthTests", "test_login"])
        assert result == "tests/test_auth.py > AuthTests > test_login"

    def test_empty_title_parts(self) -> None:
        result = build_test_id("tests/test_auth.py", [])
        assert result == "tests/test_auth.py"

    def test_forward_slash_normalisation(self) -> None:
        result = build_test_id("tests/sub/test_foo.py", ["test_bar"])
        assert "\\" not in result
        assert result == "tests/sub/test_foo.py > test_bar"
