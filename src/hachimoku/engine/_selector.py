"""SelectorAgent — エージェント選択処理。

FR-RE-002 Step 5: セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。
R-006: SelectorOutput モデル定義。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from claudecode_model import ClaudeCodeModel, ClaudeCodeModelSettings
from claudecode_model.exceptions import CLIExecutionError
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from hachimoku.agents.models import AgentDefinition, SelectorDefinition
from hachimoku.engine._catalog import resolve_tools
from hachimoku.engine._instruction import build_selector_instruction
from hachimoku.engine._model_resolver import resolve_model
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import SelectorConfig

logger = logging.getLogger(__name__)


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

    Attributes:
        exit_code: CLI プロセス終了コード（CLIExecutionError 由来、オプション）。
        error_type: 構造化エラー種別（CLIExecutionError 由来、オプション）。
        stderr: 標準エラー出力（CLIExecutionError 由来、オプション）。
        recoverable: リトライにより回復可能か（CLIExecutionError 由来、オプション）。
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        error_type: str | None = None,
        stderr: str | None = None,
        recoverable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.error_type = error_type
        self.stderr = stderr
        self.recoverable = recoverable


async def run_selector(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
    selector_definition: SelectorDefinition,
    selector_config: SelectorConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
    resolved_content: str,
) -> SelectorOutput:
    """セレクターエージェントを実行し、実行すべきエージェントを選択する。

    実行フロー:
        1. モデル解決（3層: config > definition > global）
        2. SelectorConfig からタイムアウト・ターン数を解決
        3. SelectorDefinition.allowed_tools からツールを解決
        4. build_selector_instruction() でユーザーメッセージを構築
        5. resolve_model() でモデルオブジェクトを生成
        6. pydantic-ai Agent(system_prompt=definition.system_prompt) を構築
        7. asyncio.timeout() + UsageLimits でエージェントを実行
        8. SelectorOutput を返す

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。
        selector_definition: セレクター定義（system_prompt, allowed_tools, model）。
        selector_config: セレクター個別設定（model, timeout, max_turns オーバーライド）。
        global_model: グローバルモデル名。
        global_timeout: グローバルタイムアウト秒数。
        global_max_turns: グローバル最大ターン数。
        resolved_content: 事前解決されたコンテンツ（diff テキスト、ファイル内容等）。

    Returns:
        SelectorOutput: 選択されたエージェント名リストと選択理由。

    Raises:
        SelectorError: セレクターエージェントの実行に失敗した場合。
    """
    # 3層モデル解決: config > definition > global
    if selector_config.model is not None:
        model = selector_config.model
    elif selector_definition.model is not None:
        model = selector_definition.model
    else:
        model = global_model

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

    try:
        tools = resolve_tools(selector_definition.allowed_tools)
        user_message = build_selector_instruction(
            target, available_agents, resolved_content
        )

        resolved = resolve_model(model)
        agent = Agent(
            model=resolved,
            output_type=SelectorOutput,
            tools=list(tools),
            system_prompt=selector_definition.system_prompt,
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
                model_settings=ClaudeCodeModelSettings(
                    max_turns=max_turns,
                    timeout=timeout,
                ),
            )

        return result.output

    except Exception as exc:
        logger.warning(
            "Selector agent failed with %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )

        exit_code: int | None = None
        error_type: str | None = None
        stderr: str | None = None
        recoverable: bool | None = None

        if isinstance(exc, CLIExecutionError):
            exit_code = exc.exit_code
            error_type = exc.error_type
            stderr = exc.stderr
            recoverable = exc.recoverable

        raise SelectorError(
            f"Selector agent failed: {exc}",
            exit_code=exit_code,
            error_type=error_type,
            stderr=stderr,
            recoverable=recoverable,
        ) from exc
