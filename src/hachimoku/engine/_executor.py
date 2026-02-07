"""SequentialExecutor — 逐次エージェント実行。

FR-RE-006: parallel=false の場合のフェーズ順序制御。
フェーズ順（early → main → final）、同フェーズ内は名前辞書順で逐次実行。
"""

from __future__ import annotations

import asyncio
from typing import Final

from hachimoku.agents.models import Phase
from hachimoku.engine._context import AgentExecutionContext
from hachimoku.engine._progress import report_agent_complete, report_agent_start
from hachimoku.engine._runner import run_agent
from hachimoku.models.agent_result import AgentResult

PHASE_SEQUENCE: Final[tuple[Phase, ...]] = (Phase.EARLY, Phase.MAIN, Phase.FINAL)
"""フェーズの実行順序。"""


def group_by_phase(
    contexts: list[AgentExecutionContext],
) -> dict[str, list[AgentExecutionContext]]:
    """実行コンテキストをフェーズごとにグループ化する。

    フェーズ順（early → main → final）で辞書キーを構成し、
    同フェーズ内のエージェントは名前の辞書順でソートする。
    コンテキストが存在しないフェーズはキーに含めない。

    Args:
        contexts: 実行コンテキストのリスト。

    Returns:
        フェーズ名 → コンテキストリストの辞書（フェーズ順）。
    """
    grouped: dict[str, list[AgentExecutionContext]] = {}
    for phase in PHASE_SEQUENCE:
        phase_contexts = sorted(
            (c for c in contexts if c.phase == phase),
            key=lambda c: c.agent_name,
        )
        if phase_contexts:
            grouped[phase.value] = phase_contexts
    return grouped


async def execute_sequential(
    contexts: list[AgentExecutionContext],
    shutdown_event: asyncio.Event,
) -> list[AgentResult]:
    """エージェントをフェーズ順・名前辞書順で逐次実行する。

    各エージェント実行前に shutdown_event をチェックし、
    セット済みなら残りの実行をスキップする。

    Args:
        contexts: 実行コンテキストのリスト（ソート不要、内部でグループ化する）。
        shutdown_event: シグナルハンドラがセットする停止イベント。

    Returns:
        実行完了したエージェントの AgentResult リスト。
    """
    results: list[AgentResult] = []
    grouped = group_by_phase(contexts)

    for phase_contexts in grouped.values():
        for ctx in phase_contexts:
            if shutdown_event.is_set():
                return results

            report_agent_start(ctx.agent_name)
            result = await run_agent(ctx)
            report_agent_complete(ctx.agent_name, result)
            results.append(result)

    return results
