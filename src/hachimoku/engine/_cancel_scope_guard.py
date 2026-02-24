"""CancelScope 衝突ガード — agent.run() の安全なラッパー。

Issue #274: pydantic-ai v1.63.0 の内部 CancelScope（pydantic-graph の
TaskGroup + _run_tracked_task）と claude-agent-sdk の内部タスクグループが
衝突し、RuntimeError が発生する問題への対策。

2つの衝突パターンを処理する:

1. __aexit__ 衝突（結果保存済み）: agent.iter() で結果をコンテキスト終了前に
   保存し、__aexit__ の CancelScope RuntimeError を許容して結果を返す。

2. イテレーション中衝突（結果未保存）: ClaudeCodeModel の move_on_after() が
   timeout 発火 → CancelScope ツリー破壊 → _run_tracked_task の CancelScope
   が RuntimeError を送出。元の CLIExecutionError(error_type="timeout") が
   RuntimeError に上書きされるため、timeout エラーを復元する。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from claudecode_model.exceptions import CLIExecutionError

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
    マネージャを使用するが、CancelScope の衝突が発生すると結果が失われる。

    このヘルパーは agent.iter() を直接使い、2つの衝突パターンを処理する:

    1. 結果保存後の __aexit__ 衝突: 保存済みの結果を返す。
    2. イテレーション中の衝突（結果未保存）: ClaudeCodeModel の
       move_on_after() timeout 発火による CancelScope ツリー破壊。
       RuntimeError に上書きされた CLIExecutionError(error_type="timeout")
       を復元して送出する。

    Args:
        agent: pydantic-ai Agent インスタンス。
        **run_kwargs: agent.iter() に渡すキーワード引数
            （user_prompt, deps, usage_limits, model_settings 等）。

    Returns:
        AgentRunResult: エージェントの実行結果。

    Raises:
        CLIExecutionError: CancelScope 衝突で結果が保存されていない場合
            （error_type="timeout"）。
        RuntimeError: CancelScope 以外の RuntimeError。
        Exception: iteration 中に発生したその他の例外。
    """
    result: AgentRunResult[Any] | None = None

    try:
        async with agent.iter(**run_kwargs) as agent_run:
            async for _node in agent_run:
                pass
            result = agent_run.result
    except RuntimeError as exc:
        if not _is_cancel_scope_error(exc):
            raise

        if result is not None:
            logger.warning(
                "Cancel scope conflict during agent cleanup (result preserved): %s",
                exc,
            )
        else:
            # CancelScope 衝突 + 結果なし = timeout 発火による衝突。
            # ClaudeCodeModel の move_on_after() が発火
            # → CLIExecutionError(error_type="timeout") が送出されるが、
            # _run_tracked_task の CancelScope.__exit__() が RuntimeError で
            # 上書きする。元の timeout エラーを復元する。
            logger.warning(
                "Cancel scope conflict during agent execution "
                "(no result, treating as timeout): %s",
                exc,
            )
            raise CLIExecutionError(
                "Agent execution interrupted by cancel scope conflict "
                "(timeout-induced cancel scope tree corruption)",
                error_type="timeout",
                recoverable=True,
            ) from exc

    if result is None:
        raise RuntimeError("Agent run did not produce a result")

    return result
