"""SelectorAgent — エージェント選択処理。

FR-RE-002 Step 5: セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。
R-006: SelectorOutput モデル定義。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Final

from claudecode_model import ClaudeCodeModel
from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from hachimoku.agents.models import AgentDefinition
from hachimoku.engine._catalog import resolve_tools
from hachimoku.engine._instruction import build_selector_instruction
from hachimoku.engine._model_resolver import resolve_model
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import Provider, SelectorConfig

SELECTOR_SYSTEM_PROMPT: Final[str] = (
    "You are an agent selector for code review. "
    "Analyze the review target using the provided tools, "
    "then select the most applicable review agents from the available list. "
    "Consider each agent's description, applicability rules (file_patterns, "
    "content_patterns), and phase when making your selection. "
    "Return the selected agent names and your reasoning."
)
"""セレクターエージェントのシステムプロンプト。"""


class SelectorOutput(HachimokuBaseModel):
    """セレクターエージェントの構造化出力。

    Attributes:
        selected_agents: 実行すべきエージェント名リスト。
        reasoning: 選択理由（デバッグ・監査用）。
    """

    selected_agents: list[str]
    reasoning: str


class SelectorError(Exception):
    """セレクターエージェントの実行失敗。

    タイムアウト・実行エラー・不正な出力など、セレクター実行中の
    あらゆる失敗を表す。
    """


async def run_selector(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
    selector_config: SelectorConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
    global_provider: Provider,
) -> SelectorOutput:
    """セレクターエージェントを実行し、実行すべきエージェントを選択する。

    実行フロー:
        1. SelectorConfig からモデル・プロバイダー・タイムアウト・ターン数を解決
        2. ToolCatalog から SelectorConfig.allowed_tools のツールを解決
        3. build_selector_instruction() でユーザーメッセージを構築
        4. resolve_model() でプロバイダーに応じたモデルオブジェクトを生成
        5. pydantic-ai Agent(output_type=SelectorOutput) を構築
        6. asyncio.timeout() + UsageLimits でエージェントを実行
        7. SelectorOutput を返す

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。
        selector_config: セレクター個別設定。
        global_model: グローバルモデル名。
        global_timeout: グローバルタイムアウト秒数。
        global_max_turns: グローバル最大ターン数。
        global_provider: グローバル LLM プロバイダー。

    Returns:
        SelectorOutput: 選択されたエージェント名リストと選択理由。

    Raises:
        SelectorError: セレクターエージェントの実行に失敗した場合。
    """
    model = selector_config.model if selector_config.model is not None else global_model
    timeout = (
        selector_config.timeout
        if selector_config.timeout is not None
        else global_timeout
    )
    max_turns = (
        selector_config.max_turns
        if selector_config.max_turns is not None
        else global_max_turns
    )
    provider = (
        selector_config.provider
        if selector_config.provider is not None
        else global_provider
    )

    try:
        tool_categories = tuple(str(t) for t in selector_config.allowed_tools)
        tools = resolve_tools(tool_categories)
        user_message = build_selector_instruction(target, available_agents)

        resolved = resolve_model(model, provider)
        agent = Agent(
            model=resolved,
            output_type=SelectorOutput,
            tools=list(tools),
            system_prompt=SELECTOR_SYSTEM_PROMPT,
        )
        if isinstance(resolved, ClaudeCodeModel):
            # mypy が FunctionToolset.tools の dict[str, Tool[Any]] を
            # AgentToolset.tools の dict[str, PydanticAITool] と互換とみなせないため。
            # set_agent_toolsets の docstring が agent._function_toolset を使用例として記載。
            resolved.set_agent_toolsets(agent._function_toolset)  # type: ignore[arg-type]

        async with asyncio.timeout(timeout):
            result = await agent.run(
                user_message,
                usage_limits=UsageLimits(request_limit=max_turns),
                # ClaudeCodeModel の内部ターン制限を設定。
                # ModelSettings TypedDict に max_turns は未定義のためキャスト。
                model_settings=ModelSettings(max_turns=max_turns),  # type: ignore[typeddict-unknown-key]
            )

        return result.output

    except Exception as exc:
        raise SelectorError(f"Selector agent failed: {exc}") from exc
