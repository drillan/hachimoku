"""ToolCatalog のテスト。

FR-RE-016: カテゴリベースのツール管理。
"""

import asyncio
from pathlib import Path

import pytest
from pydantic_ai import Tool
from pydantic_ai.builtin_tools import AbstractBuiltinTool, WebFetchTool

from hachimoku.engine._catalog import (
    BUILTIN_TOOL_CATALOG,
    CLAUDECODE_BUILTIN_MAP,
    TOOL_CATALOG,
    ResolvedTools,
    create_file_tools,
    resolve_tools,
    validate_categories,
)


# =============================================================================
# ResolvedTools
# =============================================================================


class TestResolvedTools:
    """ResolvedTools データクラスのテスト。"""

    def test_frozen(self) -> None:
        """イミュータブルである。"""
        resolved = ResolvedTools(
            tools=(), builtin_tools=(), claudecode_builtin_names=()
        )
        with pytest.raises(AttributeError):
            resolved.tools = ()  # type: ignore[misc]

    def test_holds_tools_and_builtin_tools(self) -> None:
        """通常ツールとビルトインツールを保持する。"""
        resolved = ResolvedTools(
            tools=(),
            builtin_tools=(WebFetchTool(),),
            claudecode_builtin_names=("WebFetch",),
        )
        assert len(resolved.builtin_tools) == 1
        assert isinstance(resolved.builtin_tools[0], WebFetchTool)
        assert resolved.claudecode_builtin_names == ("WebFetch",)


# =============================================================================
# BUILTIN_TOOL_CATALOG / CLAUDECODE_BUILTIN_MAP
# =============================================================================


class TestBuiltinToolCatalog:
    """BUILTIN_TOOL_CATALOG 定数のテスト。"""

    def test_web_fetch_registered(self) -> None:
        """web_fetch カテゴリが登録されている。"""
        assert "web_fetch" in BUILTIN_TOOL_CATALOG

    def test_web_fetch_contains_web_fetch_tool(self) -> None:
        """web_fetch カテゴリに WebFetchTool が含まれる。"""
        tools = BUILTIN_TOOL_CATALOG["web_fetch"]
        assert len(tools) == 1
        assert isinstance(tools[0], WebFetchTool)


class TestClaudeCodeBuiltinMap:
    """CLAUDECODE_BUILTIN_MAP 定数のテスト。"""

    def test_web_fetch_maps_to_webfetch(self) -> None:
        """web_fetch カテゴリが Claude Code の WebFetch にマッピングされる。"""
        assert "web_fetch" in CLAUDECODE_BUILTIN_MAP
        assert CLAUDECODE_BUILTIN_MAP["web_fetch"] == ("WebFetch",)

    def test_git_read_maps_to_mcp_tool(self) -> None:
        """git_read カテゴリが MCP ツール名にマッピングされる。"""
        assert "git_read" in CLAUDECODE_BUILTIN_MAP
        assert CLAUDECODE_BUILTIN_MAP["git_read"] == ("mcp__pydantic_tools__run_git",)

    def test_gh_read_maps_to_mcp_tool(self) -> None:
        """gh_read カテゴリが MCP ツール名にマッピングされる。"""
        assert "gh_read" in CLAUDECODE_BUILTIN_MAP
        assert CLAUDECODE_BUILTIN_MAP["gh_read"] == ("mcp__pydantic_tools__run_gh",)

    def test_file_read_maps_to_mcp_tools(self) -> None:
        """file_read カテゴリが2つの MCP ツール名にマッピングされる。"""
        assert "file_read" in CLAUDECODE_BUILTIN_MAP
        assert CLAUDECODE_BUILTIN_MAP["file_read"] == (
            "mcp__pydantic_tools__read_file",
            "mcp__pydantic_tools__list_directory",
        )

    def test_mcp_names_follow_naming_convention(self) -> None:
        """MCP ツール名が mcp__pydantic_tools__ プレフィックスに従う。"""
        for category, names in CLAUDECODE_BUILTIN_MAP.items():
            for name in names:
                if category != "web_fetch":
                    assert name.startswith("mcp__pydantic_tools__"), (
                        f"{category} の MCP ツール名 '{name}' が命名規則に従っていない"
                    )


# =============================================================================
# TOOL_CATALOG — async ツール関数
# =============================================================================


class TestToolCatalogAsync:
    """TOOL_CATALOG のツール関数が async であることを検証する。

    claudecode_model の MCP ブリッジ（create_tool_wrapper）は
    await original_function(**args) で呼び出すため、
    ツール関数は async でなければならない。
    """

    @pytest.mark.parametrize(
        ("category", "expected_names"),
        [
            ("git_read", ["run_git"]),
            ("gh_read", ["run_gh"]),
            ("file_read", ["read_file", "list_directory"]),
        ],
    )
    def test_tool_functions_are_async(
        self, category: str, expected_names: list[str]
    ) -> None:
        """各カテゴリのツール関数が async である。"""
        tools = TOOL_CATALOG[category]
        for tool, expected_name in zip(tools, expected_names, strict=True):
            assert asyncio.iscoroutinefunction(tool.function), (
                f"Tool '{expected_name}' in category '{category}' must be async"
            )

    @pytest.mark.parametrize(
        ("category", "expected_names"),
        [
            ("git_read", ["run_git"]),
            ("gh_read", ["run_gh"]),
            ("file_read", ["read_file", "list_directory"]),
        ],
    )
    def test_tool_names_preserved(
        self, category: str, expected_names: list[str]
    ) -> None:
        """async 化後もツール名が元の関数名を維持する。"""
        tools = TOOL_CATALOG[category]
        actual_names = [t.name for t in tools]
        assert actual_names == expected_names

    def test_tool_names_match_mcp_convention(self) -> None:
        """TOOL_CATALOG のツール名が CLAUDECODE_BUILTIN_MAP の MCP 名と整合する。"""
        mcp_prefix = "mcp__pydantic_tools__"
        for category, tools in TOOL_CATALOG.items():
            if category not in CLAUDECODE_BUILTIN_MAP:
                continue
            tool_names = [t.name for t in tools]
            mcp_names = CLAUDECODE_BUILTIN_MAP[category]
            for mcp_name in mcp_names:
                assert mcp_name.startswith(mcp_prefix), (
                    f"MCP name '{mcp_name}' missing prefix"
                )
                bare_name = mcp_name.removeprefix(mcp_prefix)
                assert bare_name in tool_names, (
                    f"MCP name '{mcp_name}' has no matching tool "
                    f"'{bare_name}' in TOOL_CATALOG['{category}']"
                )


# =============================================================================
# resolve_tools
# =============================================================================


class TestResolveTools:
    """resolve_tools 関数のテスト。"""

    def test_resolves_git_read(self) -> None:
        """git_read カテゴリからツールを解決する。"""
        resolved = resolve_tools(("git_read",))
        assert len(resolved.tools) > 0
        assert all(isinstance(t, Tool) for t in resolved.tools)
        assert resolved.builtin_tools == ()

    def test_resolves_git_read_includes_mcp_names(self) -> None:
        """git_read カテゴリの解決で MCP ツール名が claudecode_builtin_names に含まれる。"""
        resolved = resolve_tools(("git_read",))
        assert "mcp__pydantic_tools__run_git" in resolved.claudecode_builtin_names

    def test_resolves_gh_read(self) -> None:
        """gh_read カテゴリからツールを解決する。"""
        resolved = resolve_tools(("gh_read",))
        assert len(resolved.tools) > 0

    def test_resolves_file_read(self) -> None:
        """file_read カテゴリからツールを解決する。"""
        resolved = resolve_tools(("file_read",))
        assert len(resolved.tools) > 0

    def test_resolves_web_fetch_as_builtin(self) -> None:
        """web_fetch カテゴリをビルトインツールとして解決する。"""
        resolved = resolve_tools(("web_fetch",))
        assert resolved.tools == ()
        assert len(resolved.builtin_tools) == 1
        assert isinstance(resolved.builtin_tools[0], AbstractBuiltinTool)
        assert resolved.claudecode_builtin_names == ("WebFetch",)

    def test_resolves_mixed_regular_and_builtin(self) -> None:
        """通常カテゴリとビルトインカテゴリを混在して解決する。"""
        resolved = resolve_tools(("file_read", "web_fetch"))
        assert len(resolved.tools) > 0
        assert len(resolved.builtin_tools) == 1
        assert "mcp__pydantic_tools__read_file" in resolved.claudecode_builtin_names
        assert (
            "mcp__pydantic_tools__list_directory" in resolved.claudecode_builtin_names
        )
        assert "WebFetch" in resolved.claudecode_builtin_names

    def test_resolves_all_categories_includes_all_mcp_names(self) -> None:
        """全カテゴリ解決時に全 MCP ツール名が claudecode_builtin_names に含まれる。"""
        resolved = resolve_tools(("git_read", "gh_read", "file_read", "web_fetch"))
        expected_names = {
            "mcp__pydantic_tools__run_git",
            "mcp__pydantic_tools__run_gh",
            "mcp__pydantic_tools__read_file",
            "mcp__pydantic_tools__list_directory",
            "WebFetch",
        }
        assert expected_names == set(resolved.claudecode_builtin_names)

    def test_resolves_multiple_regular_categories(self) -> None:
        """複数の通常カテゴリのツールを統合して返す。"""
        single_git = resolve_tools(("git_read",))
        single_file = resolve_tools(("file_read",))
        combined = resolve_tools(("git_read", "file_read"))
        assert len(combined.tools) == len(single_git.tools) + len(single_file.tools)

    def test_returns_resolved_tools_instance(self) -> None:
        """戻り値が ResolvedTools インスタンスである。"""
        resolved = resolve_tools(("git_read",))
        assert isinstance(resolved, ResolvedTools)

    def test_unknown_category_raises_value_error(self) -> None:
        """不明なカテゴリで ValueError を送出する。"""
        with pytest.raises(ValueError, match="unknown_category"):
            resolve_tools(("unknown_category",))

    def test_mixed_known_and_unknown_raises_error(self) -> None:
        """既知と不明の混在で ValueError を送出する。"""
        with pytest.raises(ValueError, match="bad"):
            resolve_tools(("git_read", "bad"))

    def test_empty_categories_returns_empty(self) -> None:
        """空タプルで空の ResolvedTools を返す。"""
        resolved = resolve_tools(())
        assert resolved.tools == ()
        assert resolved.builtin_tools == ()
        assert resolved.claudecode_builtin_names == ()


# =============================================================================
# validate_categories
# =============================================================================


class TestValidateCategories:
    """validate_categories 関数のテスト。"""

    def test_all_valid_returns_empty_list(self) -> None:
        """全カテゴリ有効時に空リストを返す。"""
        invalid = validate_categories(("git_read", "gh_read", "file_read", "web_fetch"))
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

    def test_web_fetch_is_valid(self) -> None:
        """web_fetch は有効なカテゴリとして認識される。"""
        invalid = validate_categories(("web_fetch",))
        assert invalid == []


# =============================================================================
# create_file_tools
# =============================================================================


class TestCreateFileTools:
    """create_file_tools ファクトリ関数のテスト。"""

    def test_returns_two_tools(self) -> None:
        """read_file と list_directory の 2 ツールを返す。"""
        tools = create_file_tools()
        assert len(tools) == 2

    def test_tool_names_preserved(self) -> None:
        """ツール名が read_file, list_directory を維持する。"""
        tools = create_file_tools()
        names = [t.name for t in tools]
        assert names == ["read_file", "list_directory"]

    def test_tools_are_async(self) -> None:
        """ツール関数が async である。"""
        tools = create_file_tools()
        for tool in tools:
            assert asyncio.iscoroutinefunction(tool.function)

    def test_with_project_root_resolves_relative_path(self, tmp_path: Path) -> None:
        """project_root 付きで相対パスが解決される。"""
        subdir = tmp_path / "data"
        subdir.mkdir()
        (subdir / "test.txt").write_text("content")
        tools = create_file_tools(project_root=tmp_path)
        # list_directory ツールを取得
        list_dir_tool = tools[1]
        assert list_dir_tool.name == "list_directory"
        # 相対パス "data" が tmp_path/data に解決される
        # takes_ctx=False なので RunContext 不要だが、Tool.function の型は
        # RunContext を要求するため type: ignore で抑制
        result = asyncio.run(
            list_dir_tool.function("data")  # type: ignore[arg-type]
        )
        assert "test.txt" in result

    def test_without_project_root_uses_cwd(self) -> None:
        """project_root なしの場合、現行の cwd 基準動作を維持する。"""
        tools = create_file_tools()
        # project_root=None の場合はツールが作成されるが、
        # パス解決は従来通り cwd 基準
        assert len(tools) == 2


class TestResolveToolsWithProjectRoot:
    """resolve_tools の project_root 対応テスト。"""

    def test_file_read_uses_project_root(self, tmp_path: Path) -> None:
        """file_read カテゴリが project_root を使用してツールを作成する。"""
        resolved = resolve_tools(("file_read",), project_root=tmp_path)
        # ツールが作成されていることを確認
        assert len(resolved.tools) == 2
        tool_names = [t.name for t in resolved.tools]
        assert "read_file" in tool_names
        assert "list_directory" in tool_names

    def test_non_file_categories_unaffected(self, tmp_path: Path) -> None:
        """git_read/gh_read は project_root の影響を受けない。"""
        resolved_with = resolve_tools(("git_read",), project_root=tmp_path)
        resolved_without = resolve_tools(("git_read",))
        assert len(resolved_with.tools) == len(resolved_without.tools)

    def test_mixed_categories_with_project_root(self, tmp_path: Path) -> None:
        """混在カテゴリで project_root が正しく適用される。"""
        resolved = resolve_tools(
            ("git_read", "file_read", "web_fetch"), project_root=tmp_path
        )
        assert len(resolved.tools) > 0
        assert len(resolved.builtin_tools) == 1
