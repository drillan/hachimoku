"""Contract: ToolCatalog — カテゴリベースのツール管理.

FR-RE-016: ツールカタログの定義、バリデーション、解決を担当する。
"""

from __future__ import annotations

from pydantic_ai import Tool


def resolve_tools(categories: tuple[str, ...]) -> tuple[Tool[None], ...]:
    """カテゴリ名から pydantic-ai ツールリストを解決する.

    Args:
        categories: ツールカテゴリ名のタプル（例: ("git_read", "file_read")）。

    Returns:
        解決された pydantic-ai Tool オブジェクトのタプル。

    Raises:
        ValueError: カタログに存在しないカテゴリ名が含まれている場合。
    """
    ...


def validate_categories(categories: tuple[str, ...]) -> list[str]:
    """カテゴリ名をカタログに対してバリデーションする.

    Args:
        categories: 検証するカテゴリ名のタプル。

    Returns:
        カタログに存在しない不正なカテゴリ名のリスト。
        空リストの場合は全て有効。
    """
    ...


# カテゴリ → ツール関数リストのマッピング（実装時に定義）
# TOOL_CATALOG: dict[str, list[Tool]] = {
#     "git_read": [...],
#     "gh_read": [...],
#     "file_read": [...],
# }
