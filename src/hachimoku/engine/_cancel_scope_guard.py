"""CancelScope 衝突ガード — agent.run() の安全なラッパー。

Issue #274: pydantic-ai v1.63.0 の内部 CancelScope（pydantic-graph の
TaskGroup + _run_tracked_task）と claude-agent-sdk の内部タスクグループが
衝突し、__aexit__ で RuntimeError が発生する問題への対策。

agent.iter() を使い、結果をコンテキスト終了前に保存することで、
__aexit__ の CancelScope RuntimeError を許容しつつ結果を回復する。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.run import AgentRunResult

logger = logging.getLogger(__name__)


def _is_cancel_scope_error(error: RuntimeError) -> bool:
    """RuntimeError が anyio CancelScope の衝突かどうかを判定する。

    claudecode_model.model._is_cancel_scope_error と同じロジック。
    anyio のエラーメッセージ形式に依存する（anyio 4.x で検証済み）。
    """
    return "cancel scope" in str(error).lower()


async def run_agent_safe(
    agent: Agent[Any, Any],
    /,
    **run_kwargs: Any,
) -> AgentRunResult[Any]:
    """CancelScope 衝突を許容しつつ agent を実行する。

    pydantic-ai の agent.run() は内部で agent.iter() のコンテキスト
    マネージャを使用するが、__aexit__ で CancelScope の衝突が発生すると
    結果が失われる。

    このヘルパーは agent.iter() を直接使い、結果をコンテキスト終了前に
    保存する。__aexit__ で CancelScope RuntimeError が発生しても、
    保存済みの結果を返すことで回復する。

    Args:
        agent: pydantic-ai Agent インスタンス。
        **run_kwargs: agent.iter() に渡すキーワード引数
            （user_prompt, deps, usage_limits, model_settings 等）。

    Returns:
        AgentRunResult: エージェントの実行結果。

    Raises:
        RuntimeError: CancelScope 以外の RuntimeError、
            または結果が保存される前に CancelScope 衝突が発生した場合。
        Exception: iteration 中に発生したその他の例外。
    """
    result: AgentRunResult[Any] | None = None

    try:
        async with agent.iter(**run_kwargs) as agent_run:
            async for _node in agent_run:
                pass
            result = agent_run.result
    except RuntimeError as exc:
        if _is_cancel_scope_error(exc) and result is not None:
            logger.warning(
                "Cancel scope conflict during agent cleanup (result preserved): %s",
                exc,
            )
        else:
            raise

    if result is None:
        raise RuntimeError("Agent run did not produce a result")

    return result
