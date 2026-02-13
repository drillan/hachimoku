"""設定管理モデル。

FR-CF-002: 設定項目の定義
FR-CF-004: バリデーション仕様
FR-CF-009: HachimokuBaseModel 継承
FR-CF-010: セレクターエージェント設定
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final

from typing import Annotated

from pydantic import Field, StringConstraints, StrictBool, field_validator

from hachimoku.agents.models import AGENT_NAME_PATTERN
from hachimoku.models._base import HachimokuBaseModel

# _prefetch.DEFAULT_CONVENTION_FILES と同値。
# 循環インポート（config → engine._prefetch → engine/__init__ → _engine → config）を避けるためリテラル定義。
_DEFAULT_CONVENTION_FILES: tuple[str, ...] = ("CLAUDE.md", ".hachimoku/config.toml")

# 既存の AGENT_NAME_PATTERN (str) をコンパイル済み正規表現として使用
_AGENT_NAME_RE: re.Pattern[str] = re.compile(AGENT_NAME_PATTERN)

# グローバルデフォルト値（Issue #130: 複雑なレビューに対応するため引き上げ）
DEFAULT_TIMEOUT_SECONDS: Final[int] = 600
DEFAULT_MAX_TURNS: Final[int] = 30

# referenced_content のサイズ上限（Issue #172）
DEFAULT_REFERENCED_CONTENT_MAX_CHARS: Final[int] = 5000


class OutputFormat(StrEnum):
    """レビュー結果の出力形式。FR-CF-002."""

    MARKDOWN = "markdown"
    JSON = "json"


class SelectorConfig(HachimokuBaseModel):
    """セレクターエージェント設定。FR-CF-010.

    model, timeout, max_turns はオプショナル（None 可）で、
    None の場合はグローバル設定値が適用される。
    allowed_tools は selector.toml に移動済み。
    """

    model: str | None = Field(default=None, min_length=1)
    timeout: int | None = Field(default=None, gt=0)
    max_turns: int | None = Field(default=None, gt=0)
    referenced_content_max_chars: int = Field(
        default=DEFAULT_REFERENCED_CONTENT_MAX_CHARS, gt=0
    )
    convention_files: tuple[Annotated[str, StringConstraints(min_length=1)], ...] = (
        _DEFAULT_CONVENTION_FILES
    )


class AgentConfig(HachimokuBaseModel):
    """エージェント個別設定。FR-CF-002 エージェント個別設定セクション.

    enabled はデフォルト True の必須フィールド。
    model, timeout, max_turns はオプショナル（None 可）で、
    None の場合はグローバル設定値が適用される（FR-CF-008）。
    """

    enabled: StrictBool = True
    model: str | None = Field(default=None, min_length=1)
    timeout: int | None = Field(default=None, gt=0)
    max_turns: int | None = Field(default=None, gt=0)


class AggregationConfig(HachimokuBaseModel):
    """集約エージェント設定。FR-RE-019, Issue #152.

    SelectorConfig と同パターン。enabled で集約の有効/無効を切り替え可能。
    model, timeout, max_turns はオプショナル（None 可）で、
    None の場合はグローバル設定値が適用される。
    """

    enabled: StrictBool = True
    model: str | None = Field(default=None, min_length=1)
    timeout: int | None = Field(default=None, gt=0)
    max_turns: int | None = Field(default=None, gt=0)


class HachimokuConfig(HachimokuBaseModel):
    """全設定項目を統合した不変モデル。FR-CF-002, FR-CF-009.

    デフォルト値のみで有効なインスタンスを構築可能。
    """

    # 実行設定
    model: str = Field(default="claudecode:claude-opus-4-6", min_length=1)
    timeout: int = Field(default=DEFAULT_TIMEOUT_SECONDS, gt=0)
    max_turns: int = Field(default=DEFAULT_MAX_TURNS, gt=0)
    parallel: StrictBool = True
    base_branch: str = Field(default="main", min_length=1)

    # 出力設定
    output_format: OutputFormat = OutputFormat.MARKDOWN
    save_reviews: StrictBool = True
    show_cost: StrictBool = False

    # ファイルモード設定
    max_files_per_review: int = Field(default=100, gt=0)

    # セレクターエージェント設定
    selector: SelectorConfig = Field(default_factory=SelectorConfig)

    # 集約エージェント設定
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig)

    # エージェント個別設定
    agents: dict[str, AgentConfig] = Field(default_factory=dict)

    @field_validator("agents")
    @classmethod
    def validate_agent_names(cls, v: dict[str, AgentConfig]) -> dict[str, AgentConfig]:
        """エージェント名の形式を検証する。FR-CF-004."""
        for name in v:
            if not _AGENT_NAME_RE.fullmatch(name):
                msg = (
                    f"Invalid agent name '{name}': "
                    f"must match pattern {AGENT_NAME_PATTERN}"
                )
                raise ValueError(msg)
        return v
