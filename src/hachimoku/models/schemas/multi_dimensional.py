"""多次元分析。

type-design-analyzer が使用する出力スキーマ。
"""

from __future__ import annotations

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.schemas._base import BaseAgentOutput


class DimensionScore(HachimokuBaseModel):
    """評価軸のスコア。"""

    name: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=10.0)
    description: str = Field(min_length=1)


class MultiDimensionalAnalysis(BaseAgentOutput):
    """多次元分析。"""

    dimensions: list[DimensionScore]
