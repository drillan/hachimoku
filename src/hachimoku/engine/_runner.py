"""AgentRunner — 単一エージェントの実行。

FR-RE-003: タイムアウト・ターン数制御・失敗許容。
FR-RE-004: UsageLimits + ClaudeCodeModelSettings(timeout) による二段階制御。
R-001: pydantic-ai UsageLimits + model_settings max_turns の二重経路。
R-002: タイムアウトは ClaudeCodeModelSettings 経由で SDK に委譲。
R-003: UsageLimitExceeded 時は空 issues リストで AgentTruncated を返す。
R-011: result.usage() からトークン数を CostInfo に変換。
"""

from __future__ import annotations

import logging
import time

from claudecode_model import ClaudeCodeModel, ClaudeCodeModelSettings
from claudecode_model.exceptions import CLIExecutionError
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from hachimoku.engine._cancel_scope_guard import run_agent_safe
from hachimoku.engine._context import AgentExecutionContext
from hachimoku.engine._model_resolver import resolve_model
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
    CostInfo,
)

logger = logging.getLogger(__name__)


async def run_agent(context: AgentExecutionContext) -> AgentResult:
    """単一エージェントを実行し、AgentResult を返す。

    全ての例外を内部で捕捉し、適切な AgentResult バリアントに変換する。
    この関数は例外を送出しない。

    実行フロー:
        1. pydantic-ai Agent を構築（model, tools, builtin_tools, system_prompt, output_type）
        2. UsageLimits(request_limit=max_turns) でターン数制御
        3. agent.run() を実行（タイムアウトは ClaudeCodeModelSettings 経由で SDK に委譲）
        4. 結果を AgentResult に変換

    例外ハンドリング:
        - CLIExecutionError(error_type="timeout") → AgentTimeout
        - UsageLimitExceeded → AgentTruncated（空 issues リスト）
        - その他の例外 → AgentError

    Args:
        context: エージェント実行コンテキスト。

    Returns:
        AgentResult: AgentSuccess / AgentTruncated / AgentError / AgentTimeout。
    """
    start_time = time.monotonic()

    try:
        resolved = resolve_model(
            context.model,
            extra_builtin_tools=context.claudecode_builtin_names,
        )
        agent = Agent(
            model=resolved,
            output_type=context.output_schema,
            tools=list(context.tools),
            builtin_tools=list(context.builtin_tools),
            system_prompt=context.system_prompt,
        )
        if isinstance(resolved, ClaudeCodeModel):
            # mypy が FunctionToolset.tools の dict[str, Tool[Any]] を
            # AgentToolset.tools の dict[str, PydanticAITool] と互換とみなせないため。
            # set_agent_toolsets の docstring が agent._function_toolset を使用例として記載。
            resolved.set_agent_toolsets(agent._function_toolset)  # type: ignore[arg-type]

        result = await run_agent_safe(
            agent,
            user_prompt=context.user_message,
            usage_limits=UsageLimits(request_limit=context.max_turns),
            model_settings=ClaudeCodeModelSettings(
                max_turns=context.max_turns,
                timeout=context.timeout_seconds,
            ),
        )

        elapsed = time.monotonic() - start_time
        usage = result.usage()

        return AgentSuccess(
            agent_name=context.agent_name,
            issues=result.output.issues,
            elapsed_time=elapsed,
            cost=CostInfo(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            ),
        )

    except UsageLimitExceeded:
        elapsed = time.monotonic() - start_time
        return AgentTruncated(
            agent_name=context.agent_name,
            issues=[],
            elapsed_time=elapsed,
            turns_consumed=context.max_turns,
        )

    except Exception as exc:
        # CLIExecutionError(error_type="timeout") → AgentTimeout
        if isinstance(exc, CLIExecutionError) and exc.error_type == "timeout":
            return AgentTimeout(
                agent_name=context.agent_name,
                timeout_seconds=float(context.timeout_seconds),
            )

        logger.warning(
            "Agent '%s' failed with %s: %s",
            context.agent_name,
            type(exc).__name__,
            exc,
            exc_info=True,
        )

        exit_code: int | None = None
        error_type: str | None = None
        stderr: str | None = None

        if isinstance(exc, CLIExecutionError):
            exit_code = exc.exit_code
            error_type = exc.error_type
            stderr = exc.stderr

        return AgentError(
            agent_name=context.agent_name,
            error_message=str(exc),
            exit_code=exit_code,
            error_type=error_type,
            stderr=stderr,
        )
