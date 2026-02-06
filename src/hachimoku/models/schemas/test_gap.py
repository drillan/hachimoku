"""テストギャップ評価。

pr-test-analyzer が使用する出力スキーマ。
"""

from __future__ import annotations

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.schemas._base import BaseAgentOutput
from hachimoku.models.severity import Severity


class CoverageGap(HachimokuBaseModel):
    """テストカバレッジの欠落。"""

    file_path: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: Severity


class TestGapAssessment(BaseAgentOutput):
    """テストギャップ評価。"""

    coverage_gaps: list[CoverageGap]
    risk_level: Severity
