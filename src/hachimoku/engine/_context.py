"""AgentExecutionContext — エージェント実行コンテキスト構築。

FR-RE-007: エージェント定義・設定・レビュー対象から実行コンテキストを構築。
FR-RE-004: タイムアウト・ターン数の優先順解決。
"""

from typing import TYPE_CHECKING, Self

from pydantic import ConfigDict, Field, SkipValidation, model_validator
from pydantic_ai import Tool

from hachimoku.agents.models import AgentDefinition, Phase
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import AgentConfig, HachimokuConfig, Provider
from hachimoku.models.schemas._base import BaseAgentOutput

# pydantic-ai の Tool[None] は内部ジェネリック型 (ToolFuncEither[ToolAgentDepsT]) が
# Pydantic のスキーマ生成と互換性がないため、TYPE_CHECKING ガードで型を分離する。
# ランタイム: SkipValidation[tuple] → Pydantic のスキーマ生成をスキップ
# 型チェッカー: SkipValidation[tuple[Tool[None], ...]] → 型安全性を維持
if TYPE_CHECKING:
    _ToolsTuple = tuple[Tool[None], ...]
else:
    _ToolsTuple = tuple


class AgentExecutionContext(HachimokuBaseModel):
    """単一エージェントの実行に必要な全情報。

    Attributes:
        agent_name: エージェント名。
        model: 解決済みモデル名（個別設定 > グローバル > デフォルト）。
        system_prompt: エージェント定義のシステムプロンプト。
        user_message: レビュー指示情報 + オプションコンテキスト。
        output_schema: 解決済み出力スキーマクラス。
        tools: 解決済み pydantic-ai ツールタプル。
        timeout_seconds: タイムアウト秒数（解決済み）。
        max_turns: 最大ターン数（解決済み）。
        phase: 実行フェーズ。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_name: str
    model: str
    provider: Provider
    system_prompt: str
    user_message: str
    output_schema: type[BaseAgentOutput]
    tools: SkipValidation[_ToolsTuple]
    timeout_seconds: int = Field(gt=0)
    max_turns: int = Field(gt=0)
    phase: Phase

    @model_validator(mode="after")
    def validate_tools(self) -> Self:
        """tools タプルの各要素が Tool インスタンスであることを検証する。"""
        for item in self.tools:
            if not isinstance(item, Tool):
                raise ValueError(
                    f"tools must contain only Tool instances, got {type(item).__name__}"
                )
        return self


def build_execution_context(
    agent_def: AgentDefinition,
    agent_config: AgentConfig | None,
    global_config: HachimokuConfig,
    user_message: str,
    resolved_tools: tuple[Tool[None], ...],
) -> AgentExecutionContext:
    """AgentDefinition と設定からエージェント実行コンテキストを構築する。

    設定値の解決優先順（FR-RE-004）:
        1. エージェント個別設定（agents.<name>.model / timeout / max_turns）
        2. グローバル設定（HachimokuConfig.model / timeout / max_turns）
        3. デフォルト値（HachimokuConfig のフィールドデフォルト）

    Args:
        agent_def: エージェント定義。
        agent_config: エージェント個別設定（存在する場合）。
        global_config: グローバル設定。
        user_message: 構築済みユーザーメッセージ。
        resolved_tools: 解決済みツールリスト。

    Returns:
        構築された実行コンテキスト。
    """
    return AgentExecutionContext(
        agent_name=agent_def.name,
        model=(
            agent_config.model
            if agent_config is not None and agent_config.model is not None
            else global_config.model
        ),
        provider=(
            agent_config.provider
            if agent_config is not None and agent_config.provider is not None
            else global_config.provider
        ),
        system_prompt=agent_def.system_prompt,
        user_message=user_message,
        output_schema=agent_def.resolved_schema,
        tools=resolved_tools,
        timeout_seconds=(
            agent_config.timeout
            if agent_config is not None and agent_config.timeout is not None
            else global_config.timeout
        ),
        max_turns=(
            agent_config.max_turns
            if agent_config is not None and agent_config.max_turns is not None
            else global_config.max_turns
        ),
        phase=agent_def.phase,
    )
