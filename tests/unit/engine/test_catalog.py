"""ToolCatalog のテスト。

FR-RE-016: カテゴリベースのツール管理。
"""

import pytest
from pydantic_ai import Tool

from hachimoku.engine._catalog import resolve_tools, validate_categories


# =============================================================================
# resolve_tools
# =============================================================================


class TestResolveTools:
    """resolve_tools 関数のテスト。"""

    def test_resolves_git_read(self) -> None:
        """git_read カテゴリからツールを解決する。"""
        tools = resolve_tools(("git_read",))
        assert len(tools) > 0
        assert all(isinstance(t, Tool) for t in tools)

    def test_resolves_gh_read(self) -> None:
        """gh_read カテゴリからツールを解決する。"""
        tools = resolve_tools(("gh_read",))
        assert len(tools) > 0

    def test_resolves_file_read(self) -> None:
        """file_read カテゴリからツールを解決する。"""
        tools = resolve_tools(("file_read",))
        assert len(tools) > 0

    def test_resolves_multiple_categories(self) -> None:
        """複数カテゴリのツールを統合して返す。"""
        single_git = resolve_tools(("git_read",))
        single_file = resolve_tools(("file_read",))
        combined = resolve_tools(("git_read", "file_read"))
        assert len(combined) == len(single_git) + len(single_file)

    def test_returns_tuple(self) -> None:
        """戻り値がタプルである。"""
        tools = resolve_tools(("git_read",))
        assert isinstance(tools, tuple)

    def test_unknown_category_raises_value_error(self) -> None:
        """不明なカテゴリで ValueError を送出する。"""
        with pytest.raises(ValueError, match="unknown_category"):
            resolve_tools(("unknown_category",))

    def test_mixed_known_and_unknown_raises_error(self) -> None:
        """既知と不明の混在で ValueError を送出する。"""
        with pytest.raises(ValueError, match="bad"):
            resolve_tools(("git_read", "bad"))

    def test_empty_categories_returns_empty_tuple(self) -> None:
        """空タプルで空タプルを返す。"""
        tools = resolve_tools(())
        assert tools == ()


# =============================================================================
# validate_categories
# =============================================================================


class TestValidateCategories:
    """validate_categories 関数のテスト。"""

    def test_all_valid_returns_empty_list(self) -> None:
        """全カテゴリ有効時に空リストを返す。"""
        invalid = validate_categories(("git_read", "gh_read", "file_read"))
        assert invalid == []

    def test_single_invalid_returns_list(self) -> None:
        """不正カテゴリ1つを含むリストを返す。"""
        invalid = validate_categories(("git_read", "unknown"))
        assert invalid == ["unknown"]

    def test_multiple_invalid_returns_all(self) -> None:
        """複数不正カテゴリを全て返す。"""
        invalid = validate_categories(("bad1", "git_read", "bad2"))
        assert set(invalid) == {"bad1", "bad2"}

    def test_empty_tuple_returns_empty_list(self) -> None:
        """空タプルで空リストを返す。"""
        invalid = validate_categories(())
        assert invalid == []

    def test_all_invalid_returns_all(self) -> None:
        """全て不正なカテゴリのリストを返す。"""
        invalid = validate_categories(("x", "y", "z"))
        assert set(invalid) == {"x", "y", "z"}
