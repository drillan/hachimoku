"""テストギャップ評価。

pr-test-analyzer が使用する出力スキーマ。
"""

from __future__ import annotations

from pydantic import Field, field_validator

from hachimoku.models._base import HachimokuBaseModel, normalize_enum_value
from hachimoku.models.schemas._base import BaseAgentOutput
from hachimoku.models.severity import Severity


class CoverageGap(HachimokuBaseModel):
    """テストカバレッジの欠落。"""

    file_path: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Severity

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, v: object) -> object:
        """priority 入力を PascalCase に正規化する。"""
        return normalize_enum_value(v, Severity)


class TestGapAssessment(BaseAgentOutput):
    """テストギャップ評価。"""

    coverage_gaps: list[CoverageGap]
    risk_level: Severity

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, v: object) -> object:
        """risk_level 入力を PascalCase に正規化する。"""
        return normalize_enum_value(v, Severity)
