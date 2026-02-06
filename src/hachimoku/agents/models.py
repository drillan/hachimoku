"""エージェント定義の基盤モデル。

Phase（実行フェーズ）、ApplicabilityRule（適用ルール）、LoadError（読み込みエラー）を定義する。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import Field, field_validator

from hachimoku.models._base import HachimokuBaseModel


# =============================================================================
# Phase（実行フェーズ）
# =============================================================================


class Phase(StrEnum):
    """エージェントの実行フェーズ。

    実行順序: EARLY → MAIN → FINAL
    同フェーズ内のエージェントは名前の辞書順で実行される。
    """

    EARLY = "early"
    MAIN = "main"
    FINAL = "final"


PHASE_ORDER: Final[Mapping[Phase, int]] = MappingProxyType(
    {
        Phase.EARLY: 0,
        Phase.MAIN: 1,
        Phase.FINAL: 2,
    }
)


# =============================================================================
# ApplicabilityRule（適用ルール）
# =============================================================================


class ApplicabilityRule(HachimokuBaseModel):
    """エージェントの適用条件。

    条件評価ロジック:
    1. always = True → 常に適用
    2. file_patterns のいずれかにファイル名（basename）がマッチ → 適用
    3. content_patterns のいずれかにコンテンツがマッチ → 適用
    4. 上記いずれも該当しない → 不適用

    条件 2 と 3 は OR 関係。
    """

    always: bool = False
    file_patterns: list[str] = Field(default_factory=list)
    content_patterns: list[str] = Field(default_factory=list)

    @field_validator("content_patterns")
    @classmethod
    def validate_regex_patterns(cls, v: list[str]) -> list[str]:
        """各パターンが有効な正規表現であることを検証する。"""
        for pattern in v:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}") from None
        return v


# =============================================================================
# LoadError（読み込みエラー情報）
# =============================================================================


class LoadError(HachimokuBaseModel):
    """エージェント定義読み込み時のエラー情報。"""

    source: str = Field(min_length=1)
    message: str = Field(min_length=1)
