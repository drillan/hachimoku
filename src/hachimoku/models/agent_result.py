"""エージェント実行結果の定義。

FR-DM-003: AgentResult 判別共用体。
status フィールドの固定値で型を一意に特定する。
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import ReviewIssue


class CostInfo(HachimokuBaseModel):
    """LLM 実行コスト情報。

    Attributes:
        input_tokens: 入力トークン数（非負）。
        output_tokens: 出力トークン数（非負）。
        total_cost: 合計コスト（非負）。金額計算未実装時は None。
    """

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_cost: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)


class AgentSuccess(HachimokuBaseModel):
    """エージェント実行の成功結果。判別キー: status="success"。

    Attributes:
        status: 判別キー。固定値 "success"。
        agent_name: エージェント名。
        issues: 検出されたレビュー問題のリスト。
        elapsed_time: 実行所要時間（秒、正の値）。
        cost: LLM 実行コスト情報（オプション）。
    """

    status: Literal["success"] = "success"
    agent_name: str = Field(min_length=1)
    issues: list[ReviewIssue]
    elapsed_time: float = Field(gt=0, allow_inf_nan=False)
    cost: CostInfo | None = None


class AgentError(HachimokuBaseModel):
    """エージェント実行のエラー結果。判別キー: status="error"。

    Attributes:
        status: 判別キー。固定値 "error"。
        agent_name: エージェント名。
        error_message: エラーメッセージ。
        exit_code: CLI プロセス終了コード（CLIExecutionError 由来、オプション）。
        error_type: 構造化エラー種別（CLIExecutionError 由来、オプション）。
        stderr: 標準エラー出力（CLIExecutionError 由来、オプション）。
    """

    status: Literal["error"] = "error"
    agent_name: str = Field(min_length=1)
    error_message: str = Field(min_length=1)
    exit_code: int | None = None
    error_type: str | None = Field(default=None, min_length=1)
    stderr: str | None = None


class AgentTimeout(HachimokuBaseModel):
    """エージェント実行のタイムアウト結果。判別キー: status="timeout"。

    Attributes:
        status: 判別キー。固定値 "timeout"。
        agent_name: エージェント名。
        timeout_seconds: タイムアウト閾値（秒、正の値）。
    """

    status: Literal["timeout"] = "timeout"
    agent_name: str = Field(min_length=1)
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)


class AgentTruncated(HachimokuBaseModel):
    """エージェント実行の切り詰め結果。判別キー: status="truncated"。

    最大ターン数に到達した場合の部分的な結果を保持する。
    ReviewSummary 計算時には AgentSuccess と同様に有効な結果として扱う（FR-RE-003）。

    cost フィールドは持たない。切り詰め時点では LLM 実行が中断されており、
    正確なコスト情報を取得できないため意図的に省略している。

    Attributes:
        status: 判別キー。固定値 "truncated"。
        agent_name: エージェント名。
        issues: その時点までに検出されたレビュー問題のリスト（部分的だが有効）。
        elapsed_time: 実行所要時間（秒、正の値）。
        turns_consumed: 切り詰めまでに消費したターン数（正の値）。
    """

    status: Literal["truncated"] = "truncated"
    agent_name: str = Field(min_length=1)
    issues: list[ReviewIssue]
    elapsed_time: float = Field(gt=0, allow_inf_nan=False)
    turns_consumed: int = Field(gt=0)


AgentResult = Annotated[
    Union[AgentSuccess, AgentTruncated, AgentError, AgentTimeout],
    Field(discriminator="status"),
]
"""エージェント結果の判別共用体。status フィールドの値で型を自動選択する。"""
