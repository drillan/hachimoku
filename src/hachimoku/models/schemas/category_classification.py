"""カテゴリ分類。

comment-analyzer が使用する出力スキーマ。
"""

from __future__ import annotations

from hachimoku.models.review import ReviewIssue
from hachimoku.models.schemas._base import BaseAgentOutput


class CategoryClassification(BaseAgentOutput):
    """カテゴリ分類。"""

    categories: dict[str, list[ReviewIssue]]
