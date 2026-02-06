"""設定管理モデルの型契約。

FR-CF-002: 設定項目の定義
FR-CF-004: バリデーション仕様
FR-CF-009: HachimokuBaseModel 継承
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import Field, field_validator

from hachimoku.agents.models import AGENT_NAME_PATTERN
from hachimoku.models._base import HachimokuBaseModel

# 既存の AGENT_NAME_PATTERN (str) をコンパイル済み正規表現として使用
_AGENT_NAME_RE: re.Pattern[str] = re.compile(AGENT_NAME_PATTERN)


class OutputFormat(StrEnum):
    """レビュー結果の出力形式。FR-CF-002."""

    MARKDOWN = "markdown"
    JSON = "json"


class AgentConfig(HachimokuBaseModel):
    """エージェント個別設定。FR-CF-002 エージェント個別設定セクション.

    enabled はデフォルト True の必須フィールド。
    model, timeout, max_turns はオプショナル（None 可）で、
    None の場合はグローバル設定値が適用される（FR-CF-008）。
    """

    enabled: bool = True
    model: str | None = Field(default=None, min_length=1)
    timeout: int | None = Field(default=None, gt=0)
    max_turns: int | None = Field(default=None, gt=0)


class HachimokuConfig(HachimokuBaseModel):
    """全設定項目を統合した不変モデル。FR-CF-002, FR-CF-009.

    デフォルト値のみで有効なインスタンスを構築可能。
    """

    # 実行設定
    model: str = Field(default="sonnet", min_length=1)
    timeout: int = Field(default=300, gt=0)
    max_turns: int = Field(default=10, gt=0)
    parallel: bool = False
    base_branch: str = Field(default="main", min_length=1)

    # 出力設定
    output_format: OutputFormat = OutputFormat.MARKDOWN
    save_reviews: bool = True
    show_cost: bool = False

    # ファイルモード設定
    max_files_per_review: int = Field(default=100, gt=0)

    # エージェント個別設定
    agents: dict[str, AgentConfig] = Field(default_factory=dict)

    @field_validator("agents")
    @classmethod
    def validate_agent_names(
        cls, v: dict[str, AgentConfig]
    ) -> dict[str, AgentConfig]:
        """エージェント名の形式を検証する。FR-CF-004."""
        for name in v:
            if not _AGENT_NAME_RE.match(name):
                msg = (
                    f"Invalid agent name '{name}': "
                    f"must match pattern {AGENT_NAME_PATTERN}"
                )
                raise ValueError(msg)
        return v
