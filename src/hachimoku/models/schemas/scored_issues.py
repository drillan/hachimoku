"""スコア付き問題リスト。

code-reviewer 等が使用する出力スキーマ。
"""

from __future__ import annotations

from pydantic import Field

from hachimoku.models.schemas._base import BaseAgentOutput


class ScoredIssues(BaseAgentOutput):
    """スコア付き問題リスト。

    overall_score はコード品質の全体スコア (0.0-10.0) を表す。
    """

    overall_score: float = Field(ge=0.0, le=10.0)
