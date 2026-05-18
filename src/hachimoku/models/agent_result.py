"""エージェント実行結果の定義。

FR-DM-003: AgentResult 判別共用体。
status フィールドの固定値で型を一意に特定する。
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import ReviewIssue


class AgentSuccess(HachimokuBaseModel):
    """エージェント実行の成功結果。判別キー: status="success"。

    Attributes:
        status: 判別キー。固定値 "success"。
        agent_name: エージェント名。
        issues: 検出されたレビュー問題のリスト。
        overall_score: 品質スコア（0.0-10.0、オプション）。
        elapsed_time: 実行所要時間（秒、正の値）。観測できない場合は None。
    """

    status: Literal["success"] = "success"
    agent_name: str = Field(min_length=1)
    issues: list[ReviewIssue]
    overall_score: float | None = Field(default=None, ge=0.0, le=10.0)
    elapsed_time: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class AgentError(HachimokuBaseModel):
    """エージェント実行のエラー結果。判別キー: status="error"。

    Attributes:
        status: 判別キー。固定値 "error"。
        agent_name: エージェント名。
        error_message: エラーメッセージ。
        exit_code: CLI プロセス終了コード（オプション）。
        error_type: 構造化エラー種別（オプション）。
        stderr: 標準エラー出力（オプション）。
    """

    status: Literal["error"] = "error"
    agent_name: str = Field(min_length=1)
    error_message: str = Field(min_length=1)
    exit_code: int | None = None
    error_type: str | None = Field(default=None, min_length=1)
    stderr: str | None = None


AgentResult = Annotated[
    Union[AgentSuccess, AgentError],
    Field(discriminator="status"),
]
"""エージェント結果の判別共用体。status フィールドの値で型を自動選択する。"""
