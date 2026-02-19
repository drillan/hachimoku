"""改善提案リスト。

code-simplifier が使用する出力スキーマ。
"""

from __future__ import annotations

from pydantic import Field, field_validator

from hachimoku.models._base import HachimokuBaseModel, normalize_enum_value
from hachimoku.models.review import FileLocation
from hachimoku.models.schemas._base import BaseAgentOutput
from hachimoku.models.severity import Severity


class ImprovementItem(HachimokuBaseModel):
    """改善提案の個別項目。"""

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Severity
    location: FileLocation | None = None

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: object) -> object:
        """priority 入力を PascalCase に正規化する。"""
        return normalize_enum_value(v, Severity)


class ImprovementSuggestions(BaseAgentOutput):
    """改善提案リスト。"""

    suggestions: list[ImprovementItem]
