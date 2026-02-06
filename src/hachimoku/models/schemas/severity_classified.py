"""重大度分類問題リスト。

silent-failure-hunter 等が使用する出力スキーマ。
"""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from hachimoku.models.review import ReviewIssue
from hachimoku.models.schemas._base import BaseAgentOutput


class SeverityClassified(BaseAgentOutput):
    """重大度分類問題リスト。

    分類リスト（critical_issues 等）が LLM 出力として受け取るフィールド。
    issues は分類リストから model_validator で自動導出し、整合性を構造的に保証する。
    issues を明示的に渡す必要はない（4つの分類リストから自動構築される）。
    """

    critical_issues: list[ReviewIssue]
    important_issues: list[ReviewIssue]
    suggestion_issues: list[ReviewIssue]
    nitpick_issues: list[ReviewIssue]

    @model_validator(mode="before")
    @classmethod
    def build_issues_from_classifications(cls, data: dict[str, Any]) -> dict[str, Any]:
        """4つの分類リストから issues を常に自動構築する。

        issues は分類リストの結合と常に等しいという不変条件を保証する。
        外部から issues を明示的に渡した場合でも分類リストから再計算する。
        分類リストが欠落している場合は構築をスキップし、
        後続の Pydantic フィールドバリデーションでエラーを検出する。
        """
        if isinstance(data, dict):
            keys = (
                "critical_issues",
                "important_issues",
                "suggestion_issues",
                "nitpick_issues",
            )
            if all(k in data for k in keys):
                data["issues"] = [
                    *data["critical_issues"],
                    *data["important_issues"],
                    *data["suggestion_issues"],
                    *data["nitpick_issues"],
                ]
        return data
