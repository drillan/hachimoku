"""スコア付き問題リスト。

code-reviewer 等が使用する出力スキーマ。
overall_score は BaseAgentOutput から継承する。
"""

from __future__ import annotations

from hachimoku.models.schemas._base import BaseAgentOutput


class ScoredIssues(BaseAgentOutput):
    """スコア付き問題リスト。

    overall_score は BaseAgentOutput から継承する（0.0-10.0）。
    SCHEMA_REGISTRY の "scored_issues" エントリとの後方互換のため維持。
    """

    pass
