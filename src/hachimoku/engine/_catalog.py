"""ToolCatalog — カテゴリベースのツール管理。

FR-RE-016: ツールカタログの定義、バリデーション、解決を担当する。
R-004: カテゴリ→ツール解決のマッピング管理。
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from pydantic_ai import Tool

from hachimoku.engine._tools._file import list_directory, read_file
from hachimoku.engine._tools._gh import run_gh
from hachimoku.engine._tools._git import run_git

TOOL_CATALOG: Final[Mapping[str, tuple[Tool[None], ...]]] = MappingProxyType(
    {
        "git_read": (Tool(run_git, takes_ctx=False),),
        "gh_read": (Tool(run_gh, takes_ctx=False),),
        "file_read": (
            Tool(read_file, takes_ctx=False),
            Tool(list_directory, takes_ctx=False),
        ),
    }
)
"""カテゴリ名から pydantic-ai Tool へのマッピング。"""


def resolve_tools(categories: tuple[str, ...]) -> tuple[Tool[None], ...]:
    """カテゴリ名から pydantic-ai ツールリストを解決する。

    Args:
        categories: ツールカテゴリ名のタプル（例: ("git_read", "file_read")）。

    Returns:
        解決された pydantic-ai Tool オブジェクトのタプル。

    Raises:
        ValueError: カタログに存在しないカテゴリ名が含まれている場合。
    """
    invalid = validate_categories(categories)
    if invalid:
        raise ValueError(f"Unknown tool categories: {', '.join(invalid)}")

    tools: list[Tool[None]] = []
    for category in categories:
        tools.extend(TOOL_CATALOG[category])

    return tuple(tools)


def validate_categories(categories: tuple[str, ...]) -> list[str]:
    """カテゴリ名をカタログに対してバリデーションする。

    Args:
        categories: 検証するカテゴリ名のタプル。

    Returns:
        カタログに存在しない不正なカテゴリ名のリスト。
        空リストの場合は全て有効。
    """
    return [cat for cat in categories if cat not in TOOL_CATALOG]
