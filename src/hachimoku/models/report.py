"""レビューサマリーとレビューレポートの定義。

FR-DM-004: ReviewReport による結果集約。
"""

from __future__ import annotations

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import AgentResult, CostInfo
from hachimoku.models.severity import Severity


class ReviewSummary(HachimokuBaseModel):
    """レビュー結果の全体サマリー。

    ReviewReport および ReviewHistoryRecord で共有される。

    Attributes:
        total_issues: 検出された問題の総数（非負）。
        max_severity: 検出された問題の最大重大度。問題なしの場合は None。
        total_elapsed_time: 全エージェントの合計実行時間（非負）。
        total_cost: 全エージェントの合計コスト情報（オプション）。
    """

    total_issues: int = Field(ge=0)
    max_severity: Severity | None
    total_elapsed_time: float = Field(ge=0.0)
    total_cost: CostInfo | None = None


class ReviewReport(HachimokuBaseModel):
    """全エージェントの結果を集約したレビューレポート。

    results は空リストを許容する（全エージェント失敗時の部分レポート対応、SC-006）。

    Attributes:
        results: エージェント結果のリスト。
        summary: レビュー結果の全体サマリー。
    """

    results: list[AgentResult]
    summary: ReviewSummary
