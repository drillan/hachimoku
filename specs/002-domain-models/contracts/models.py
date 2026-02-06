"""002-domain-models インターフェース契約.

このファイルはモデルの公開 API を型シグネチャとして定義する。
実装は src/hachimoku/models/ に配置される。

NOTE: このファイルは仕様ドキュメントであり、実行可能コードではない。
フィールド制約は Field() で型レベルに表現し、実装時にそのまま使用する。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field


# =============================================================================
# 基底モデル
# =============================================================================


class HachimokuBaseModel(BaseModel):
    """全ドメインモデルの基底クラス。extra="forbid" で厳格モードを一元管理。"""

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# Severity（重大度）
# =============================================================================

# Severity の順序定義（数値が大きいほど重大度が高い）
SEVERITY_ORDER: dict[str, int] = {
    "Nitpick": 0,
    "Suggestion": 1,
    "Important": 2,
    "Critical": 3,
}


class Severity(StrEnum):
    """レビュー問題の重大度。PascalCase で内部保持。

    入力は大文字小文字非依存。Pydantic モデルのフィールドとして使用する場合、
    ``@field_validator(mode="before")`` で入力値を PascalCase に正規化する。

    順序関係: Critical > Important > Suggestion > Nitpick
    比較演算は SEVERITY_ORDER に基づくカスタム実装を提供する。
    """

    CRITICAL = "Critical"
    IMPORTANT = "Important"
    SUGGESTION = "Suggestion"
    NITPICK = "Nitpick"

    def __lt__(self, other: object) -> bool:
        """重大度の順序比較。SEVERITY_ORDER に基づく。"""
        ...

    def __le__(self, other: object) -> bool: ...

    def __gt__(self, other: object) -> bool: ...

    def __ge__(self, other: object) -> bool: ...


# 終了コード定数
EXIT_CODE_SUCCESS: int = 0
EXIT_CODE_CRITICAL: int = 1
EXIT_CODE_IMPORTANT: int = 2


def determine_exit_code(max_severity: Severity | None) -> int:
    """最大重大度から終了コードを決定する。

    Args:
        max_severity: レビュー結果の最大重大度。問題なしの場合は None。

    Returns:
        終了コード (0, 1, 2)。

    Raises:
        ValueError: 未知の Severity 値が渡された場合。
    """
    ...


# =============================================================================
# FileLocation, ReviewIssue
# =============================================================================


class FileLocation(HachimokuBaseModel):
    """ファイル内位置。ファイルパスと行番号の組。"""

    file_path: str = Field(min_length=1)
    line_number: int = Field(ge=1)


class ReviewIssue(HachimokuBaseModel):
    """エージェントが検出したレビュー問題の統一表現。"""

    agent_name: str = Field(min_length=1)
    severity: Severity
    description: str = Field(min_length=1)
    location: FileLocation | None = None
    suggestion: str | None = None
    category: str | None = None


# =============================================================================
# AgentResult（判別共用体）
# =============================================================================


class CostInfo(HachimokuBaseModel):
    """LLM 実行コスト情報。"""

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_cost: float = Field(ge=0.0)


class AgentSuccess(HachimokuBaseModel):
    """エージェント実行の成功結果。判別キー: status="success"。"""

    status: Literal["success"] = "success"
    agent_name: str = Field(min_length=1)
    issues: list[ReviewIssue]
    elapsed_time: float = Field(gt=0)
    cost: CostInfo | None = None


class AgentError(HachimokuBaseModel):
    """エージェント実行のエラー結果。判別キー: status="error"。"""

    status: Literal["error"] = "error"
    agent_name: str = Field(min_length=1)
    error_message: str = Field(min_length=1)


class AgentTimeout(HachimokuBaseModel):
    """エージェント実行のタイムアウト結果。判別キー: status="timeout"。"""

    status: Literal["timeout"] = "timeout"
    agent_name: str = Field(min_length=1)
    timeout_seconds: float = Field(gt=0)


AgentResult = Annotated[
    Union[AgentSuccess, AgentError, AgentTimeout],
    Field(discriminator="status"),
]


# =============================================================================
# ReviewReport
# =============================================================================


class ReviewSummary(HachimokuBaseModel):
    """レビュー結果の全体サマリー。ReviewReport および ReviewHistoryRecord で共有。"""

    total_issues: int = Field(ge=0)
    max_severity: Severity | None
    total_elapsed_time: float = Field(ge=0.0)
    total_cost: CostInfo | None = None


class ReviewReport(HachimokuBaseModel):
    """全エージェントの結果を集約したレビューレポート。"""

    results: list[AgentResult]
    summary: ReviewSummary


# =============================================================================
# 出力スキーマ
# =============================================================================


class BaseAgentOutput(HachimokuBaseModel):
    """全出力スキーマの共通ベースモデル。"""

    issues: list[ReviewIssue]


class ScoredIssues(BaseAgentOutput):
    """スコア付き問題リスト。code-reviewer 等が使用。"""

    overall_score: float = Field(ge=0.0, le=10.0)


class SeverityClassified(BaseAgentOutput):
    """重大度分類問題リスト。silent-failure-hunter 等が使用。

    分類リスト（critical_issues 等）が LLM 出力として受け取るフィールド。
    issues は分類リストから computed_field で自動導出し、整合性を構造的に保証する。
    """

    critical_issues: list[ReviewIssue]
    important_issues: list[ReviewIssue]
    suggestion_issues: list[ReviewIssue]
    nitpick_issues: list[ReviewIssue]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def issues(self) -> list[ReviewIssue]:
        """全分類リストを結合して issues を導出する。"""
        ...


class CoverageGap(HachimokuBaseModel):
    """テストカバレッジの欠落。"""

    file_path: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Severity


class TestGapAssessment(BaseAgentOutput):
    """テストギャップ評価。pr-test-analyzer が使用。"""

    coverage_gaps: list[CoverageGap]
    risk_level: Severity


class DimensionScore(HachimokuBaseModel):
    """評価軸のスコア。"""

    name: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=10.0)
    description: str = Field(min_length=1)


class MultiDimensionalAnalysis(BaseAgentOutput):
    """多次元分析。type-design-analyzer が使用。"""

    dimensions: list[DimensionScore]


class CategoryClassification(BaseAgentOutput):
    """カテゴリ分類。comment-analyzer が使用。"""

    categories: dict[str, list[ReviewIssue]]


class ImprovementItem(HachimokuBaseModel):
    """改善提案の個別項目。"""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Severity
    location: FileLocation | None = None


class ImprovementSuggestions(BaseAgentOutput):
    """改善提案リスト。code-simplifier が使用。"""

    suggestions: list[ImprovementItem]


# =============================================================================
# SCHEMA_REGISTRY
# =============================================================================


class SchemaNotFoundError(Exception):
    """SCHEMA_REGISTRY に登録されていないスキーマ名が指定された場合のエラー。"""

    ...


class DuplicateSchemaError(Exception):
    """SCHEMA_REGISTRY に同名のスキーマが重複登録された場合のエラー。"""

    ...


def get_schema(name: str) -> type[BaseAgentOutput]:
    """スキーマ名から対応するスキーマモデルを取得する。

    Raises:
        SchemaNotFoundError: 未登録のスキーマ名が指定された場合。
    """
    ...


def register_schema(name: str, schema: type[BaseAgentOutput]) -> None:
    """スキーマを SCHEMA_REGISTRY に登録する。

    Raises:
        DuplicateSchemaError: 同名のスキーマが既に登録されている場合。
    """
    ...


# =============================================================================
# ReviewHistoryRecord（判別共用体）
# =============================================================================

# コミットハッシュの型エイリアス（40文字の16進数文字列）
CommitHash = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class DiffReviewRecord(HachimokuBaseModel):
    """diff レビューの履歴レコード。判別キー: review_mode="diff"。"""

    review_mode: Literal["diff"] = "diff"
    commit_hash: CommitHash
    branch_name: str = Field(min_length=1)
    reviewed_at: datetime
    results: list[AgentResult]
    summary: ReviewSummary


class PRReviewRecord(HachimokuBaseModel):
    """PR レビューの履歴レコード。判別キー: review_mode="pr"。"""

    review_mode: Literal["pr"] = "pr"
    commit_hash: CommitHash
    pr_number: int = Field(ge=1)
    branch_name: str = Field(min_length=1)
    reviewed_at: datetime
    results: list[AgentResult]
    summary: ReviewSummary


class FileReviewRecord(HachimokuBaseModel):
    """file レビューの履歴レコード。判別キー: review_mode="file"。"""

    review_mode: Literal["file"] = "file"
    file_paths: frozenset[str]  # field_validator で空集合・空文字列を検証
    reviewed_at: datetime
    working_directory: str  # 絶対パスバリデータで検証
    results: list[AgentResult]
    summary: ReviewSummary


ReviewHistoryRecord = Annotated[
    Union[DiffReviewRecord, PRReviewRecord, FileReviewRecord],
    Field(discriminator="review_mode"),
]
