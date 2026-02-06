"""エージェント定義モデル。

Phase（実行フェーズ）、ApplicabilityRule（適用ルール）、AgentDefinition（エージェント定義）、
LoadError（読み込みエラー）、LoadResult（読み込み結果）を定義する。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import Field, field_validator, model_validator

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.schemas import BaseAgentOutput, SchemaNotFoundError, get_schema


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


# Phase の順序定義（数値が小さいほど先に実行）
PHASE_ORDER: Final[Mapping[Phase, int]] = MappingProxyType(
    {
        Phase.EARLY: 0,
        Phase.MAIN: 1,
        Phase.FINAL: 2,
    }
)

assert set(PHASE_ORDER.keys()) == set(Phase), (
    "PHASE_ORDER keys must match Phase members"
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
    file_patterns: tuple[str, ...] = ()
    content_patterns: tuple[str, ...] = ()

    @field_validator("content_patterns")
    @classmethod
    def validate_regex_patterns(cls, v: tuple[str, ...]) -> tuple[str, ...]:
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


# =============================================================================
# AgentDefinition（エージェント定義）
# =============================================================================

# エージェント名のバリデーションパターン
AGENT_NAME_PATTERN: str = r"^[a-z0-9-]+$"


class AgentDefinition(HachimokuBaseModel):
    """レビューエージェントの全構成情報。TOML 定義ファイルから構築される。

    Attributes:
        name: エージェント名（一意識別子）。アルファベット小文字・数字・ハイフンのみ。
        description: エージェントの説明。
        model: 使用する LLM モデル名。
        output_schema: SCHEMA_REGISTRY に登録されたスキーマ名。
        resolved_schema: output_schema から解決されたスキーマ型。
        system_prompt: エージェントのシステムプロンプト。
        allowed_tools: 許可するツールのリスト。
        applicability: 適用ルール。
        phase: 実行フェーズ。
    """

    name: str = Field(min_length=1, pattern=AGENT_NAME_PATTERN)
    description: str = Field(min_length=1)
    model: str = Field(min_length=1)
    output_schema: str = Field(min_length=1)
    resolved_schema: type[BaseAgentOutput] = Field(exclude=True)
    system_prompt: str = Field(min_length=1)
    allowed_tools: list[str] = Field(default_factory=list)
    applicability: ApplicabilityRule = Field(
        default_factory=lambda: ApplicabilityRule(always=True)
    )
    phase: Phase = Phase.MAIN

    @model_validator(mode="before")
    @classmethod
    def resolve_output_schema(cls, data: dict[str, object]) -> dict[str, object]:
        """output_schema から SCHEMA_REGISTRY のスキーマ型を解決する。

        Raises:
            SchemaNotFoundError: スキーマ名が SCHEMA_REGISTRY に未登録の場合。
        """
        if isinstance(data, dict) and "output_schema" in data:
            schema_name = data["output_schema"]
            if isinstance(schema_name, str):
                try:
                    data["resolved_schema"] = get_schema(schema_name)
                except SchemaNotFoundError as e:
                    raise ValueError(str(e)) from None
        return data


# =============================================================================
# LoadResult（読み込み結果）
# =============================================================================


class LoadResult(HachimokuBaseModel):
    """エージェント定義の読み込み結果。

    正常に読み込まれたエージェント定義と、スキップされたエラー情報を分離して保持する。
    呼び出し元がエラー情報の表示方法を決定できる。
    """

    agents: list[AgentDefinition]
    errors: list[LoadError] = Field(default_factory=list)
