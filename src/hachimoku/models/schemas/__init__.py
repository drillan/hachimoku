"""出力スキーマパッケージ。

SCHEMA_REGISTRY による名前からスキーマへの解決を提供する。
FR-DM-005: BaseAgentOutput と6種スキーマの継承。
FR-DM-006: スキーマレジストリ。
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from hachimoku.models.schemas._base import BaseAgentOutput
from hachimoku.models.schemas.category_classification import CategoryClassification
from hachimoku.models.schemas.improvement_suggestions import (
    ImprovementItem,
    ImprovementSuggestions,
)
from hachimoku.models.schemas.multi_dimensional import (
    DimensionScore,
    MultiDimensionalAnalysis,
)
from hachimoku.models.schemas.scored_issues import ScoredIssues
from hachimoku.models.schemas.severity_classified import SeverityClassified
from hachimoku.models.schemas.test_gap import CoverageGap, TestGapAssessment


class SchemaNotFoundError(Exception):
    """SCHEMA_REGISTRY に登録されていないスキーマ名が指定された場合のエラー。"""


class DuplicateSchemaError(Exception):
    """SCHEMA_REGISTRY に同名のスキーマが重複登録された場合のエラー。"""


_SCHEMA_REGISTRY_INTERNAL: dict[str, type[BaseAgentOutput]] = {
    "scored_issues": ScoredIssues,
    "severity_classified": SeverityClassified,
    "test_gap_assessment": TestGapAssessment,
    "multi_dimensional_analysis": MultiDimensionalAnalysis,
    "category_classification": CategoryClassification,
    "improvement_suggestions": ImprovementSuggestions,
}

SCHEMA_REGISTRY: Mapping[str, type[BaseAgentOutput]] = MappingProxyType(
    _SCHEMA_REGISTRY_INTERNAL
)


def get_schema(name: str) -> type[BaseAgentOutput]:
    """スキーマ名から対応するスキーマモデルを取得する。

    Args:
        name: スキーマ名。

    Returns:
        対応するスキーマクラス。

    Raises:
        SchemaNotFoundError: 未登録のスキーマ名が指定された場合。
    """
    try:
        return SCHEMA_REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(SCHEMA_REGISTRY.keys()))
        raise SchemaNotFoundError(
            f"Schema '{name}' is not registered in SCHEMA_REGISTRY."
            f" Available schemas: {available}"
        ) from None


def register_schema(name: str, schema: type[BaseAgentOutput]) -> None:
    """スキーマを SCHEMA_REGISTRY に登録する。

    Args:
        name: スキーマ名。
        schema: 登録するスキーマクラス。

    Raises:
        DuplicateSchemaError: 同名のスキーマが既に登録されている場合。
        TypeError: schema が BaseAgentOutput のサブクラスでない場合。
    """
    if not (isinstance(schema, type) and issubclass(schema, BaseAgentOutput)):
        raise TypeError(f"schema must be a subclass of BaseAgentOutput, got {schema!r}")
    if name in _SCHEMA_REGISTRY_INTERNAL:
        raise DuplicateSchemaError(
            f"Schema '{name}' is already registered in SCHEMA_REGISTRY"
        )
    _SCHEMA_REGISTRY_INTERNAL[name] = schema


__all__ = [
    "BaseAgentOutput",
    "CategoryClassification",
    "CoverageGap",
    "DimensionScore",
    "DuplicateSchemaError",
    "ImprovementItem",
    "ImprovementSuggestions",
    "MultiDimensionalAnalysis",
    "SCHEMA_REGISTRY",
    "SchemaNotFoundError",
    "ScoredIssues",
    "SeverityClassified",
    "TestGapAssessment",
    "get_schema",
    "register_schema",
]
