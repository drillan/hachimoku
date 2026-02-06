"""改善提案リスト。

code-simplifier が使用する出力スキーマ。
"""

from __future__ import annotations

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import FileLocation
from hachimoku.models.schemas._base import BaseAgentOutput
from hachimoku.models.severity import Severity


class ImprovementItem(HachimokuBaseModel):
    """改善提案の個別項目。"""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Severity
    location: FileLocation | None = None


class ImprovementSuggestions(BaseAgentOutput):
    """改善提案リスト。"""

    suggestions: list[ImprovementItem]
