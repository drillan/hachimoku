"""レビューサマリーとレビューレポートの定義。

FR-DM-004: ReviewReport による結果集約。
FR-RE-014: load_errors フィールド。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import AgentResult
from hachimoku.models.severity import Severity

if TYPE_CHECKING:
    from hachimoku.agents.models import LoadError


class ReviewSummary(HachimokuBaseModel):
    """レビュー結果の全体サマリー。

    ReviewReport で使用される。

    Attributes:
        total_issues: 検出された問題の総数（非負）。
        max_severity: 検出された問題の最大重大度。問題なしの場合は None。
        total_elapsed_time: 全エージェントの合計実行時間（秒）。観測できない場合は None。
        overall_score: 総合品質スコア（0.0-10.0、オプション）。
    """

    total_issues: int = Field(ge=0)
    max_severity: Severity | None
    total_elapsed_time: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    overall_score: float | None = Field(default=None, ge=0.0, le=10.0)

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

    results は空リストを許容する（全エージェント失敗時の部分レポート対応）。

    Attributes:
        results: エージェント結果のリスト。
        summary: レビュー結果の全体サマリー。
        load_errors: エージェント読み込みエラーのタプル。
    """

    results: list[AgentResult]
    summary: ReviewSummary
    load_errors: tuple[LoadError, ...] = ()
