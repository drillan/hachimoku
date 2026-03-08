"""ツールカテゴリの正規定義。

エージェントに許可されるツールのカテゴリを定義する。
004-configuration (FR-CF-004) と 005-review-engine (FR-RE-016) での使用を想定。
循環依存を回避するため 002-domain-models に配置（004-configuration spec.md Q5）。
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class ToolCategory(StrEnum):
    """エージェントに許可されるツールのカテゴリ。

    読み取り専用の4カテゴリを定義する。
    SelectorDefinition・AgentDefinition の allowed_tools バリデーション（FR-RE-016）と
    ToolCatalog のカテゴリ名解決での使用を想定。
    """

    GIT_READ = "git_read"
    GH_READ = "gh_read"
    FILE_READ = "file_read"
    WEB_FETCH = "web_fetch"


CATEGORY_TOOL_NAMES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        ToolCategory.GIT_READ: ("run_git",),
        ToolCategory.GH_READ: ("run_gh",),
        ToolCategory.FILE_READ: ("list_directory", "read_file"),
        ToolCategory.WEB_FETCH: ("web_fetch_tool",),
    }
)
"""カテゴリに含まれる個別ツール名。バリデーションエラーメッセージでの案内に使用する。"""
