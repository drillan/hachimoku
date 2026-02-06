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
        """4つの分類リストから issues を自動構築する。"""
        if isinstance(data, dict) and "issues" not in data:
            critical = data.get("critical_issues", [])
            important = data.get("important_issues", [])
            suggestion = data.get("suggestion_issues", [])
            nitpick = data.get("nitpick_issues", [])
            data["issues"] = [*critical, *important, *suggestion, *nitpick]
        return data
