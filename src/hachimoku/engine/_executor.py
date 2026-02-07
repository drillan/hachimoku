"""Executor — 逐次/並列エージェント実行。

FR-RE-006: parallel 設定に応じたフェーズ順序制御。
フェーズ順（early → main → final）で実行し、
parallel=false では同フェーズ内を名前辞書順で逐次実行、
parallel=true では同フェーズ内を asyncio.TaskGroup で並列実行する。
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
    collected_results: list[AgentResult] | None = None,
) -> list[AgentResult]:
    """エージェントをフェーズ順・名前辞書順で逐次実行する。

    各エージェント実行前に shutdown_event をチェックし、
    セット済みなら残りの実行をスキップする。

    SC-RE-005: collected_results が指定された場合、結果を直接追加する。
    これによりキャンセル時にも完了済みエージェントの結果が保存される。

    Args:
        contexts: 実行コンテキストのリスト（ソート不要、内部でグループ化する）。
        shutdown_event: シグナルハンドラがセットする停止イベント。
        collected_results: 外部から結果を参照するための共有リスト。
            None の場合は内部でリストを作成する。

    Returns:
        実行完了したエージェントの AgentResult リスト。
    """
    results: list[AgentResult] = (
        collected_results if collected_results is not None else []
    )
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


async def execute_parallel(
    contexts: list[AgentExecutionContext],
    shutdown_event: asyncio.Event,
    collected_results: list[AgentResult] | None = None,
) -> list[AgentResult]:
    """同一フェーズ内のエージェントを並列実行する。

    FR-RE-006: parallel=true の場合に使用。
    フェーズ間は順序を保持（early → main → final）。
    同一フェーズ内は asyncio.TaskGroup で並列実行。

    各タスク内で全ての例外を捕捉し、進捗報告の失敗が
    TaskGroup に伝播して他タスクをキャンセルすることを防止する。

    SC-RE-005: collected_results が指定された場合、結果を直接追加する。
    これにより TaskGroup キャンセル時にも完了済みエージェントの結果が保存される。

    Args:
        contexts: 実行コンテキストのリスト（ソート不要、内部でグループ化する）。
        shutdown_event: シグナルハンドラがセットする停止イベント。
        collected_results: 外部から結果を参照するための共有リスト。
            None の場合は内部でリストを作成する。

    Returns:
        実行完了したエージェントの AgentResult リスト。
        フェーズ間の順序は保持されるが、同一フェーズ内の順序は非決定的。
    """
    # asyncio は単一スレッドで動作するため、
    # list.append は並列タスク間で安全に使用できる。
    results: list[AgentResult] = (
        collected_results if collected_results is not None else []
    )
    grouped = group_by_phase(contexts)

    for phase_contexts in grouped.values():
        if shutdown_event.is_set():
            return results

        async def _run_and_collect(ctx: AgentExecutionContext) -> None:
            if shutdown_event.is_set():
                return
            try:
                report_agent_start(ctx.agent_name)
            except Exception:
                pass
            result = await run_agent(ctx)
            try:
                report_agent_complete(ctx.agent_name, result)
            except Exception:
                pass
            results.append(result)

        async with asyncio.TaskGroup() as tg:
            for ctx in phase_contexts:
                tg.create_task(_run_and_collect(ctx))

    return results
