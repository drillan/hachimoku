"""Contract: Executors — 逐次/並列エージェント実行.

FR-RE-005, FR-RE-006: フェーズ順序制御、並列実行、シグナルハンドリング。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from hachimoku.models.agent_result import AgentResult

if TYPE_CHECKING:
    from hachimoku.engine._context import AgentExecutionContext


async def execute_sequential(
    contexts: list[AgentExecutionContext],
    shutdown_event: asyncio.Event,
) -> list[AgentResult]:
    """エージェントをフェーズ順・名前辞書順で逐次実行する.

    FR-RE-006: parallel=false の場合に使用。
    各エージェント実行前に shutdown_event をチェックし、
    セット済みなら残りの実行をスキップする。

    Args:
        contexts: フェーズ順・名前辞書順にソート済みの実行コンテキスト。
        shutdown_event: シグナルハンドラがセットする停止イベント。

    Returns:
        実行完了したエージェントの AgentResult リスト。
    """
    ...


async def execute_parallel(
    contexts: list[AgentExecutionContext],
    shutdown_event: asyncio.Event,
) -> list[AgentResult]:
    """同一フェーズ内のエージェントを並列実行する.

    FR-RE-006: parallel=true の場合に使用。
    フェーズ間は順序を保持（early → main → final）。
    同一フェーズ内は asyncio.TaskGroup で並列実行。

    SIGINT/SIGTERM 受信時:
        - shutdown_event がセットされる
        - 現在のフェーズの TaskGroup がキャンセルされる
        - 完了済みの結果のみ返す

    Args:
        contexts: フェーズ順にソート済みの実行コンテキスト。
        shutdown_event: シグナルハンドラがセットする停止イベント。

    Returns:
        実行完了したエージェントの AgentResult リスト。
    """
    ...


def group_by_phase(
    contexts: list[AgentExecutionContext],
) -> dict[str, list[AgentExecutionContext]]:
    """実行コンテキストをフェーズごとにグループ化する.

    Args:
        contexts: 実行コンテキストのリスト。

    Returns:
        フェーズ名 → コンテキストリストの辞書（フェーズ順）。
    """
    ...
