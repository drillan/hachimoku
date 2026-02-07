"""003-agent-definition インターフェース契約.

このファイルはエージェント定義・ローダーの公開 API を型シグネチャとして定義する。
実装は src/hachimoku/agents/ に配置される。

NOTE: このファイルは仕様ドキュメントであり、実行可能コードではない。
フィールド制約は Field() で型レベルに表現し、実装時にそのまま使用する。
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.schemas import BaseAgentOutput, get_schema


# =============================================================================
# Phase（実行フェーズ）
# =============================================================================


# Phase の順序定義（数値が小さいほど先に実行）
PHASE_ORDER: dict["Phase", int] = {}  # Phase 定義後に設定


class Phase(StrEnum):
    """エージェントの実行フェーズ。

    実行順序: EARLY → MAIN → FINAL
    同フェーズ内のエージェントは名前の辞書順で実行される。
    """

    EARLY = "early"
    MAIN = "main"
    FINAL = "final"


# Phase 順序定義
PHASE_ORDER = {
    Phase.EARLY: 0,
    Phase.MAIN: 1,
    Phase.FINAL: 2,
}


# =============================================================================
# ApplicabilityRule（適用ルール）
# =============================================================================


class ApplicabilityRule(HachimokuBaseModel):
    """エージェントの適用条件（005-review-engine の SelectorAgent が参照する判断ガイダンス）。

    - always = true: SelectorAgent は他の条件に関わらず当該エージェントを選択すべきことを示すガイダンス
    - file_patterns: SelectorAgent がレビュー対象のファイルとの関連性を判断する際のガイダンス（fnmatch 互換グロブパターン）
    - content_patterns: SelectorAgent がレビュー対象のコンテンツとの関連性を判断する際のガイダンス（Python `re` 互換正規表現）

    実際の評価ロジック（エージェント選択）は 005-review-engine の SelectorAgent が担当する。
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
                data["resolved_schema"] = get_schema(schema_name)
        return data


# =============================================================================
# LoadError / LoadResult
# =============================================================================


class LoadError(HachimokuBaseModel):
    """エージェント定義読み込み時のエラー情報。"""

    source: str = Field(min_length=1)
    message: str = Field(min_length=1)


class LoadResult(HachimokuBaseModel):
    """エージェント定義の読み込み結果。

    正常に読み込まれたエージェント定義と、スキップされたエラー情報を分離して保持する。
    呼び出し元がエラー情報の表示方法を決定できる。
    """

    agents: list[AgentDefinition]
    errors: list[LoadError] = Field(default_factory=list)


# =============================================================================
# AgentLoader（ローダー関数群）
# =============================================================================


def load_builtin_agents() -> LoadResult:
    """ビルトインエージェント定義をパッケージリソースから読み込む。

    Returns:
        ビルトイン定義の読み込み結果。

    Raises:
        エラーは LoadResult.errors に収集され、例外は送出しない。
    """
    ...


def load_custom_agents(custom_dir: Path) -> LoadResult:
    """カスタムエージェント定義を指定ディレクトリから読み込む。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            存在しない場合は空の LoadResult を返す。

    Returns:
        カスタム定義の読み込み結果。
    """
    ...


def load_agents(custom_dir: Path | None = None) -> LoadResult:
    """ビルトインとカスタムを統合してエージェント定義を読み込む。

    カスタム定義がビルトイン定義と同名の場合、カスタム定義がビルトインを上書きする。
    カスタム定義がバリデーションエラーの場合、上書きは行われずビルトイン定義がそのまま使用される。

    Args:
        custom_dir: カスタム定義ファイルのディレクトリパス。
            None の場合はビルトインのみ読み込む。

    Returns:
        統合された読み込み結果。
    """
    ...


