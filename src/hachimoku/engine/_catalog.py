"""ToolCatalog — カテゴリベースのツール管理。

FR-RE-016: ツールカタログの定義、バリデーション、解決を担当する。
R-004: カテゴリ→ツール解決のマッピング管理。
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from pydantic_ai import Tool
from pydantic_ai.builtin_tools import AbstractBuiltinTool, WebFetchTool

from hachimoku.engine._tools._file import list_directory, read_file
from hachimoku.engine._tools._gh import run_gh
from hachimoku.engine._tools._git import run_git


# ---------------------------------------------------------------------------
# async ラッパー — claudecode_model の MCP ブリッジ互換
#
# claudecode_model の create_tool_wrapper は常に await で呼び出すため、
# ツール関数は async でなければならない。
# 同期関数（run_git, run_gh 等）を asyncio.to_thread でラップし、
# name= で元のツール名を維持する。
# ---------------------------------------------------------------------------


async def _run_git_async(args: list[str]) -> str:
    return await asyncio.to_thread(run_git, args)


async def _run_gh_async(args: list[str]) -> str:
    return await asyncio.to_thread(run_gh, args)


async def _read_file_async(path: str) -> str:
    return await asyncio.to_thread(read_file, path)


async def _list_directory_async(path: str, pattern: str | None = None) -> str:
    return await asyncio.to_thread(list_directory, path, pattern)


TOOL_CATALOG: Final[Mapping[str, tuple[Tool[None], ...]]] = MappingProxyType(
    {
        "git_read": (Tool(_run_git_async, takes_ctx=False, name="run_git"),),
        "gh_read": (Tool(_run_gh_async, takes_ctx=False, name="run_gh"),),
        "file_read": (
            Tool(_read_file_async, takes_ctx=False, name="read_file"),
            Tool(_list_directory_async, takes_ctx=False, name="list_directory"),
        ),
    }
)
"""カテゴリ名から pydantic-ai Tool へのマッピング。"""

BUILTIN_TOOL_CATALOG: Final[Mapping[str, tuple[AbstractBuiltinTool, ...]]] = (
    MappingProxyType(
        {
            "web_fetch": (WebFetchTool(),),
        }
    )
)
"""カテゴリ名から pydantic-ai ビルトインツールへのマッピング。"""

CLAUDECODE_BUILTIN_MAP: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "git_read": ("mcp__pydantic_tools__run_git",),
        "gh_read": ("mcp__pydantic_tools__run_gh",),
        "file_read": (
            "mcp__pydantic_tools__read_file",
            "mcp__pydantic_tools__list_directory",
        ),
        "web_fetch": ("WebFetch",),
    }
)
"""カテゴリ名から claudecode: モデルの allowed_tools に追加するツール名へのマッピング。

CLI ビルトインツール名（例: "WebFetch"）と MCP ツール名
（例: "mcp__pydantic_tools__run_git"）の両方を含む。
MCP ツール名は set_agent_toolsets() で MCP サーバー経由で登録される
pydantic-ai ツールに対応する。
"""

_ALL_CATEGORIES: Final[frozenset[str]] = frozenset(
    (*TOOL_CATALOG.keys(), *BUILTIN_TOOL_CATALOG.keys(), *CLAUDECODE_BUILTIN_MAP.keys())
)
"""全有効カテゴリ名。通常ツール、ビルトインツール、claudecode ビルトインの全カタログを含む。"""


@dataclass(frozen=True)
class ResolvedTools:
    """カテゴリ解決結果。通常ツールとビルトインツールを分離して保持する。

    Attributes:
        tools: pydantic-ai Tool[None] インスタンス（git_read, gh_read, file_read 用）。
        builtin_tools: pydantic-ai AbstractBuiltinTool インスタンス（web_fetch 用の WebFetchTool 等）。
        claudecode_builtin_names: claudecode: モデル使用時に allowed_tools に追加するツール名文字列。
    """

    tools: tuple[Tool[None], ...]
    builtin_tools: tuple[AbstractBuiltinTool, ...]
    claudecode_builtin_names: tuple[str, ...]


def resolve_tools(categories: tuple[str, ...]) -> ResolvedTools:
    """カテゴリ名からツールを解決する。通常ツールとビルトインツールを分離して返す。

    Args:
        categories: ツールカテゴリ名のタプル（例: ("git_read", "web_fetch")）。

    Returns:
        ResolvedTools: 通常ツール、ビルトインツール、claudecode ビルトイン名を含む。

    Raises:
        ValueError: カタログに存在しないカテゴリ名が含まれている場合。
    """
    invalid = validate_categories(categories)
    if invalid:
        raise ValueError(f"Unknown tool categories: {', '.join(invalid)}")

    tools: list[Tool[None]] = []
    builtin_tools: list[AbstractBuiltinTool] = []
    claudecode_names: list[str] = []

    for category in categories:
        if category in TOOL_CATALOG:
            tools.extend(TOOL_CATALOG[category])
        if category in BUILTIN_TOOL_CATALOG:
            builtin_tools.extend(BUILTIN_TOOL_CATALOG[category])
        if category in CLAUDECODE_BUILTIN_MAP:
            claudecode_names.extend(CLAUDECODE_BUILTIN_MAP[category])

    return ResolvedTools(
        tools=tuple(tools),
        builtin_tools=tuple(builtin_tools),
        claudecode_builtin_names=tuple(claudecode_names),
    )


def validate_categories(categories: tuple[str, ...]) -> list[str]:
    """カテゴリ名をカタログに対してバリデーションする。

    Args:
        categories: 検証するカテゴリ名のタプル。

    Returns:
        カタログに存在しない不正なカテゴリ名のリスト。
        空リストの場合は全て有効。
    """
    return [cat for cat in categories if cat not in _ALL_CATEGORIES]
