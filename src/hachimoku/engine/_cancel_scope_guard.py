"""CancelScope 衝突ガード — agent.run() の安全なラッパー。

Issue #274: pydantic-ai v1.63.0 の内部 CancelScope（pydantic-graph の
TaskGroup + _run_tracked_task）と claude-agent-sdk の内部タスクグループが
衝突し、RuntimeError が発生する問題への対策。

対策は 2 層で構成される:

Layer 1 — _run_tracked_task パッチ:
    pydantic-graph の _run_tracked_task() から CancelScope ラッパーを除去する。
    CancelScope は並列タスクキャンセル用（fork/join）だが、pydantic-ai の
    エージェント実行は逐次的なため除去しても安全。これにより CancelScope
    ツリー破壊の影響を遮断する。

Layer 2 — run_agent_safe ラッパー:
    agent.iter() で結果をコンテキスト終了前に保存し、残存する CancelScope
    衝突（ClaudeCodeModel の move_on_after() 起因）を処理する。
    - 結果保存後の衝突: 保存済みの結果を返す。
    - 結果未保存の衝突: CLIExecutionError(error_type="timeout") を送出。

Note:
    ClaudeCodeModel の move_on_after().__exit__() で発生する偽タイムアウト
    （クエリ成功後の CancelScope 衝突を timeout と誤判定する問題）は
    claudecode-model 0.0.32 (Issue #144) で根本修正済み。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from claudecode_model.exceptions import CLIExecutionError

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.run import AgentRunResult

logger = logging.getLogger(__name__)


def _patch_graph_cancel_scope() -> None:
    """pydantic-graph の _run_tracked_task から CancelScope を除去する。

    claude-agent-sdk の内部タスクグループが anyio の CancelScope ツリーを破壊し、
    _run_tracked_task 内の ``with CancelScope()`` の ``__exit__()`` で RuntimeError
    が発生する。

    CancelScope は並列タスクキャンセル用（fork/join）だが、pydantic-ai の
    エージェント実行は逐次的なため、除去しても機能に影響しない。
    """
    from anyio import BrokenResourceError
    from pydantic_graph.beta.graph import (
        GraphTask,
        _GraphIterator,
        _GraphTaskAsyncIterable,
        _GraphTaskResult,
    )

    async def _safe_run_tracked_task(
        self: _GraphIterator,  # type: ignore[type-arg]
        t_: GraphTask,
    ) -> None:
        result = await self._run_task(t_)
        try:
            if isinstance(result, _GraphTaskAsyncIterable):
                async for new_tasks in result.iterable:
                    await self.iter_stream_sender.send(
                        _GraphTaskResult(t_, new_tasks, False)
                    )
                await self.iter_stream_sender.send(_GraphTaskResult(t_, []))
            else:
                await self.iter_stream_sender.send(_GraphTaskResult(t_, result))
        except BrokenResourceError:
            pass

    _GraphIterator._run_tracked_task = _safe_run_tracked_task  # type: ignore[assignment]


_patch_graph_cancel_scope()


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
