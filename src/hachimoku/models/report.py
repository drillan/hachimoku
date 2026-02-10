"""レビューサマリーとレビューレポートの定義。

FR-DM-004: ReviewReport による結果集約。
FR-RE-014: load_errors フィールド。
FR-RE-018: AggregatedReport / RecommendedAction / Priority（Issue #152）。
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import Field, field_validator, model_validator

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import AgentResult, CostInfo
from hachimoku.models.review import ReviewIssue
from hachimoku.models.severity import Severity

if TYPE_CHECKING:
    from hachimoku.agents.models import LoadError


class Priority(StrEnum):
    """推奨アクションの優先度。

    RecommendedAction で使用される。Severity（問題重大度）とは別の概念。
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendedAction(HachimokuBaseModel):
    """集約エージェントが生成する推奨アクション。

    Attributes:
        description: 推奨アクションの内容。
        priority: 優先度（high/medium/low）。
    """

    description: str = Field(min_length=1)
    priority: Priority

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: object) -> object:
        """Priority 入力を lowercase に正規化する。

        LLM が "High" や "HIGH" を出力する場合に対応する。
        """
        if isinstance(v, str):
            lower = v.lower()
            for member in Priority:
                if lower == member.value:
                    return member.value
        return v


class AggregatedReport(HachimokuBaseModel):
    """集約エージェントの構造化出力。

    FR-RE-018: 重複排除された issues、strengths、推奨アクション、失敗エージェント情報。

    Attributes:
        issues: 重複排除・統合された指摘リスト。
        strengths: 良い実装に対するポジティブフィードバック。
        recommended_actions: 優先度付き推奨アクション。
        agent_failures: 失敗したエージェント名リスト（不完全性の通知用）。
    """

    issues: list[ReviewIssue]
    strengths: list[str]
    recommended_actions: list[RecommendedAction]
    agent_failures: list[str]


class ReviewSummary(HachimokuBaseModel):
    """レビュー結果の全体サマリー。

    ReviewReport で使用される。

    Attributes:
        total_issues: 検出された問題の総数（非負）。
        max_severity: 検出された問題の最大重大度。問題なしの場合は None。
        total_elapsed_time: 全エージェントの合計実行時間（非負）。
        total_cost: 全エージェントの合計コスト情報（オプション）。
    """

    total_issues: int = Field(ge=0)
    max_severity: Severity | None
    total_elapsed_time: float = Field(ge=0.0, allow_inf_nan=False)
    total_cost: CostInfo | None = None

    @model_validator(mode="after")
    def check_severity_consistency(self) -> ReviewSummary:
        """total_issues と max_severity の整合性を検証する。

        - total_issues=0 なら max_severity は None でなければならない。
        - total_issues>0 なら max_severity は None であってはならない。
        """
        if self.total_issues == 0 and self.max_severity is not None:
            raise ValueError("max_severity must be None when total_issues is 0")
        if self.total_issues > 0 and self.max_severity is None:
            raise ValueError("max_severity must not be None when total_issues > 0")
        return self


class ReviewReport(HachimokuBaseModel):
    """全エージェントの結果を集約したレビューレポート。

    results は空リストを許容する（全エージェント失敗時の部分レポート対応、SC-006）。

    Attributes:
        results: エージェント結果のリスト。
        summary: レビュー結果の全体サマリー。
        load_errors: エージェント読み込みエラーのタプル（FR-RE-014）。
        aggregated: LLM ベース集約結果（Issue #152）。None は集約なし/無効/失敗。
        aggregation_error: 集約エージェント失敗時のエラー情報（Issue #152）。
    """

    results: list[AgentResult]
    summary: ReviewSummary
    load_errors: tuple[LoadError, ...] = ()
    aggregated: AggregatedReport | None = None
    aggregation_error: str | None = None
