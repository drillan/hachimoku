"""InputResolver のテスト。

FR-CLI-002: 位置引数の優先順ルールに基づくモード自動判定。
contracts/input_resolver.py の仕様に準拠。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hachimoku.cli._input_resolver import (
    DiffInput,
    FileInput,
    InputError,
    PRInput,
    ResolvedInput,
    _is_existing_path,
    _is_path_like,
    resolve_input,
)


class TestDiffInputModel:
    """DiffInput モデルの検証。"""

    def test_mode_is_diff(self) -> None:
        result = DiffInput()
        assert result.mode == "diff"

    def test_is_frozen(self) -> None:
        result = DiffInput()
        with pytest.raises(Exception):  # noqa: B017
            result.mode = "other"  # type: ignore[assignment]


class TestPRInputModel:
    """PRInput モデルの検証。"""

    def test_mode_is_pr(self) -> None:
        result = PRInput(pr_number=123)
        assert result.mode == "pr"

    def test_pr_number_stored(self) -> None:
        result = PRInput(pr_number=42)
        assert result.pr_number == 42

    def test_pr_number_must_be_positive(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater_than"):
            PRInput(pr_number=0)

    def test_pr_number_negative_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater_than"):
            PRInput(pr_number=-1)


class TestFileInputModel:
    """FileInput モデルの検証。"""

    def test_mode_is_file(self) -> None:
        result = FileInput(paths=("src/auth.py",))
        assert result.mode == "file"

    def test_paths_stored(self) -> None:
        result = FileInput(paths=("src/auth.py", "src/api.py"))
        assert result.paths == ("src/auth.py", "src/api.py")

    def test_paths_must_not_be_empty(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="too_short"):
            FileInput(paths=())

    def test_path_element_must_not_be_empty_string(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="too_short"):
            FileInput(paths=("",))


class TestResolvedInputType:
    """ResolvedInput 共用体型の検証。"""

    def test_diff_input_is_resolved_input(self) -> None:
        result: ResolvedInput = DiffInput()
        assert isinstance(result, DiffInput)

    def test_pr_input_is_resolved_input(self) -> None:
        result: ResolvedInput = PRInput(pr_number=1)
        assert isinstance(result, PRInput)

    def test_file_input_is_resolved_input(self) -> None:
        result: ResolvedInput = FileInput(paths=("a.py",))
        assert isinstance(result, FileInput)


class TestResolveInputDiffMode:
    """引数なし → DiffInput の判定を検証する。"""

    def test_none_args_returns_diff_input(self) -> None:
        result = resolve_input(None)
        assert isinstance(result, DiffInput)
        assert result.mode == "diff"

    def test_empty_list_returns_diff_input(self) -> None:
        result = resolve_input([])
        assert isinstance(result, DiffInput)
        assert result.mode == "diff"


class TestResolveInputPRMode:
    """整数引数 → PRInput の判定を検証する。"""

    def test_single_integer_returns_pr_input(self) -> None:
        result = resolve_input(["123"])
        assert isinstance(result, PRInput)
        assert result.pr_number == 123

    def test_pr_number_one(self) -> None:
        result = resolve_input(["1"])
        assert isinstance(result, PRInput)
        assert result.pr_number == 1

    def test_large_pr_number(self) -> None:
        result = resolve_input(["99999"])
        assert isinstance(result, PRInput)
        assert result.pr_number == 99999


class TestResolveInputFileMode:
    """パスライク引数 → FileInput の判定を検証する。"""

    def test_path_with_slash(self) -> None:
        result = resolve_input(["src/auth.py"])
        assert isinstance(result, FileInput)
        assert result.paths == ("src/auth.py",)

    def test_path_with_dot(self) -> None:
        result = resolve_input(["auth.py"])
        assert isinstance(result, FileInput)
        assert result.paths == ("auth.py",)

    def test_glob_pattern_with_star(self) -> None:
        result = resolve_input(["*.py"])
        assert isinstance(result, FileInput)
        assert result.paths == ("*.py",)

    def test_glob_pattern_with_double_star(self) -> None:
        result = resolve_input(["src/**/*.py"])
        assert isinstance(result, FileInput)

    def test_path_with_question_mark(self) -> None:
        result = resolve_input(["file?.py"])
        assert isinstance(result, FileInput)

    def test_path_with_backslash(self) -> None:
        result = resolve_input(["src\\auth.py"])
        assert isinstance(result, FileInput)

    def test_multiple_file_paths(self) -> None:
        result = resolve_input(["src/auth.py", "src/api/client.py"])
        assert isinstance(result, FileInput)
        assert result.paths == ("src/auth.py", "src/api/client.py")

    def test_existing_file_without_path_chars(self, tmp_path: Path) -> None:
        """ファイルシステム上に存在するパスは FileInput と判定される。"""
        test_file = tmp_path / "Makefile"
        test_file.touch()
        result = resolve_input([str(test_file)])
        assert isinstance(result, FileInput)


class TestResolveInputError:
    """判定不可能な引数パターンで InputError を検証する。"""

    def test_unknown_string_raises_input_error(self) -> None:
        with pytest.raises(InputError):
            resolve_input(["unknown_string_that_does_not_exist"])

    def test_integer_and_path_mixed_raises_input_error(self) -> None:
        """整数とパスライクの混在は InputError。"""
        with pytest.raises(InputError):
            resolve_input(["123", "src/auth.py"])

    def test_multiple_integers_raises_input_error(self) -> None:
        """複数の整数は InputError（PR番号は1つのみ）。"""
        with pytest.raises(InputError):
            resolve_input(["123", "456"])

    def test_error_message_contains_hint(self) -> None:
        """エラーメッセージに解決方法のヒントを含む（憲法 Art.3）。"""
        with pytest.raises(InputError, match="(?i)pr number|file path|diff"):
            resolve_input(["unknown_string_that_does_not_exist"])

    def test_zero_string_raises_input_error(self) -> None:
        """'0' は正の整数ではないので InputError。"""
        with pytest.raises(InputError):
            resolve_input(["0"])

    def test_negative_integer_string_raises_input_error(self) -> None:
        """'-1' は正の整数ではないので InputError。"""
        with pytest.raises(InputError):
            resolve_input(["-1"])


class TestIsPathLike:
    """_is_path_like() ヘルパー関数の検証。"""

    def test_slash_is_path_like(self) -> None:
        assert _is_path_like("src/auth.py") is True

    def test_backslash_is_path_like(self) -> None:
        assert _is_path_like("src\\auth.py") is True

    def test_star_is_path_like(self) -> None:
        assert _is_path_like("*.py") is True

    def test_question_mark_is_path_like(self) -> None:
        assert _is_path_like("file?.py") is True

    def test_dot_is_path_like(self) -> None:
        assert _is_path_like("auth.py") is True

    def test_plain_string_is_not_path_like(self) -> None:
        assert _is_path_like("Makefile") is False

    def test_integer_string_is_not_path_like(self) -> None:
        assert _is_path_like("123") is False

    def test_empty_string_is_not_path_like(self) -> None:
        assert _is_path_like("") is False


class TestIsExistingPath:
    """_is_existing_path() ヘルパー関数の検証。"""

    def test_existing_file_returns_true(self, tmp_path: Path) -> None:
        test_file = tmp_path / "existing_file"
        test_file.touch()
        assert _is_existing_path(str(test_file)) is True

    def test_existing_directory_returns_true(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "existing_dir"
        test_dir.mkdir()
        assert _is_existing_path(str(test_dir)) is True

    def test_nonexistent_path_returns_false(self) -> None:
        assert _is_existing_path("/nonexistent/path/to/file") is False

    def test_empty_string_returns_false(self) -> None:
        assert _is_existing_path("") is False
