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
        total_cost: 合計コスト（非負）。
    """

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_cost: float = Field(ge=0.0, allow_inf_nan=False)


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
    """

    status: Literal["error"] = "error"
    agent_name: str = Field(min_length=1)
    error_message: str = Field(min_length=1)


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


AgentResult = Annotated[
    Union[AgentSuccess, AgentError, AgentTimeout],
    Field(discriminator="status"),
]
"""エージェント結果の判別共用体。status フィールドの値で型を自動選択する。"""
