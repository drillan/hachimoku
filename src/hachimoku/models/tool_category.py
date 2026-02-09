"""ツールカテゴリの正規定義。

エージェントに許可されるツールのカテゴリを定義する。
004-configuration (FR-CF-004) と 005-review-engine (FR-RE-016) での使用を想定。
循環依存を回避するため 002-domain-models に配置（004-configuration spec.md Q5）。
"""

from __future__ import annotations

from enum import StrEnum


class ToolCategory(StrEnum):
    """エージェントに許可されるツールのカテゴリ。

    読み取り専用の3カテゴリを定義する。
    SelectorDefinition・AgentDefinition の allowed_tools バリデーション（FR-RE-016）と
    ToolCatalog のカテゴリ名解決での使用を想定。
    """

    GIT_READ = "git_read"
    GH_READ = "gh_read"
    FILE_READ = "file_read"
