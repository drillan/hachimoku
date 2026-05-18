"""CancelScope 衝突ガード — agent.iter() ベースの安全なエージェント実行。

Issue #274: pydantic-ai の内部 CancelScope（pydantic-graph の TaskGroup +
_run_tracked_task）と claude-agent-sdk の内部タスクグループが衝突し、
RuntimeError が発生する問題への対策。

run_agent_safe() は agent.iter() で結果をコンテキスト終了前に保存し、
残存する CancelScope 衝突（ClaudeCodeModel の move_on_after() 起因）を処理する:

- 結果保存後の衝突: 保存済みの結果を返す。
- 結果未保存の衝突: CLIExecutionError(error_type="timeout") を送出。

Note:
    ClaudeCodeModel の move_on_after().__exit__() で発生する偽タイムアウト
    （クエリ成功後の CancelScope 衝突を timeout と誤判定する問題）は
    claudecode-model 0.0.32 (Issue #144) で根本修正済み。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar

from claudecode_model.exceptions import CLIExecutionError

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.run import AgentRunResult

_OutputT = TypeVar("_OutputT")

logger = logging.getLogger(__name__)


_CANCEL_SCOPE_ERROR_PATTERNS: tuple[str, ...] = (
    "attempted to exit a cancel scope that isn't the current tasks's current cancel scope",
    "attempted to exit cancel scope in a different task",
    "this cancel scope is not active",
)
"""anyio CancelScope の既知エラーメッセージパターン（anyio 4.x asyncio backend）。"""


def _is_cancel_scope_error(error: RuntimeError) -> bool:
    """RuntimeError が anyio CancelScope の衝突かどうかを判定する。

    claudecode_model.model._is_cancel_scope_error と同じプレフィックスマッチング。
    anyio のエラーメッセージ形式に依存する（anyio 4.x で検証済み）。
    """
    msg = str(error).lower()
    return any(msg.startswith(pattern) for pattern in _CANCEL_SCOPE_ERROR_PATTERNS)


async def run_agent_safe(
    agent: Agent[Any, _OutputT],
    /,
    **run_kwargs: Any,
) -> AgentRunResult[_OutputT]:
    """CancelScope 衝突を許容しつつ agent を実行する。

    agent.run() の代替として agent.iter() を直接使い、CancelScope 衝突時の
    結果喪失を防止する。

    2つの衝突パターンを処理する:

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
    result: AgentRunResult[_OutputT] | None = None

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
