"""ToolCategory 列挙型のテスト。

ツールカテゴリの正規定義を検証する。
004-configuration (FR-CF-004) と 005-review-engine (FR-RE-016) が参照する。
"""

from enum import StrEnum

from hachimoku.models import ToolCategory
from hachimoku.models.tool_category import ToolCategory as DirectToolCategory


class TestToolCategoryExport:
    """__init__.py からのエクスポートを検証。"""

    def test_importable_from_package(self) -> None:
        """hachimoku.models パッケージからインポートできる。"""
        assert ToolCategory is DirectToolCategory


class TestToolCategoryEnumValues:
    """ToolCategory 列挙値の定義を検証。"""

    def test_has_three_members(self) -> None:
        """3つの列挙値が定義されている。"""
        assert len(ToolCategory) == 3

    def test_git_read_value(self) -> None:
        assert ToolCategory.GIT_READ == "git_read"
        assert ToolCategory.GIT_READ.value == "git_read"

    def test_gh_read_value(self) -> None:
        assert ToolCategory.GH_READ == "gh_read"
        assert ToolCategory.GH_READ.value == "gh_read"

    def test_file_read_value(self) -> None:
        assert ToolCategory.FILE_READ == "file_read"
        assert ToolCategory.FILE_READ.value == "file_read"


class TestToolCategoryIsStrEnum:
    """StrEnum としての振る舞いを検証。"""

    def test_is_strenum_subclass(self) -> None:
        assert issubclass(ToolCategory, StrEnum)

    def test_string_comparison(self) -> None:
        """文字列との直接比較が可能。"""
        assert ToolCategory.GIT_READ == "git_read"
        assert "gh_read" == ToolCategory.GH_READ

    def test_usable_as_dict_key_with_string(self) -> None:
        """StrEnum のため、文字列キーと互換性がある。"""
        data: dict[str, int] = {ToolCategory.GIT_READ: 1}
        assert data["git_read"] == 1
