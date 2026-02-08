"""ReviewEngine — レビュー実行パイプライン。

FR-RE-002: エージェント実行パイプライン全体を統括する。
設定解決 → エージェント読み込み → 選択 → 実行 → 結果集約。
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Coroutine
from contextlib import suppress
from pathlib import Path
from typing import Final

from hachimoku.models.exit_code import ExitCode

from hachimoku.agents import load_agents
from hachimoku.agents.models import AgentDefinition, LoadError, LoadResult
from hachimoku.config import resolve_config
from hachimoku.engine._catalog import resolve_tools
from hachimoku.engine._context import AgentExecutionContext, build_execution_context
from hachimoku.engine._executor import execute_parallel, execute_sequential
from hachimoku.engine._instruction import build_review_instruction
from hachimoku.engine._signal import install_signal_handlers, uninstall_signal_handlers
from hachimoku.engine._progress import (
    report_load_warnings,
    report_selector_result,
    report_summary,
)
from hachimoku.engine._selector import SelectorError, run_selector
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
    CostInfo,
)
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.report import ReviewReport, ReviewSummary
from hachimoku.models.review import ReviewIssue
from hachimoku.models.severity import Severity, determine_exit_code


SHUTDOWN_TIMEOUT_SECONDS: Final[float] = 3.0
"""SC-RE-005: SIGINT/SIGTERM 受信後、エグゼキュータをキャンセルするまでの猶予時間（秒）。"""


class EngineResult(HachimokuBaseModel):
    """ReviewEngine の実行結果。

    Attributes:
        report: 生成されたレビューレポート。
        exit_code: 終了コード（ExitCode.SUCCESS/CRITICAL/IMPORTANT/EXECUTION_ERROR）。
    """

    report: ReviewReport
    exit_code: ExitCode


async def _execute_with_shutdown_timeout(
    executor_fn: Callable[
        [list[AgentExecutionContext], asyncio.Event, list[AgentResult] | None],
        Coroutine[object, object, list[AgentResult]],
    ],
    contexts: list[AgentExecutionContext],
    shutdown_event: asyncio.Event,
) -> list[AgentResult]:
    """シャットダウンタイムアウトを適用してエグゼキュータを実行する。

    SC-RE-005: shutdown_event がセットされた場合、SHUTDOWN_TIMEOUT_SECONDS 以内に
    エグゼキュータタスクをキャンセルし、それまでに完了したエージェントの結果を返す。

    完了済みエージェントの結果は collected_results 共有リストに蓄積される。
    タイムアウト後にエグゼキュータタスクがキャンセルされても、
    既に共有リストに追加された結果は保存される。

    Args:
        executor_fn: execute_sequential または execute_parallel。
        contexts: エージェント実行コンテキストのリスト。
        shutdown_event: シグナルハンドラがセットする停止イベント。

    Returns:
        完了したエージェントの AgentResult リスト。
        タイムアウト時は完了済み分のみ。
    """
    collected_results: list[AgentResult] = []

    executor_task: asyncio.Task[list[AgentResult]] = asyncio.create_task(
        executor_fn(contexts, shutdown_event, collected_results)
    )
    shutdown_waiter = asyncio.create_task(shutdown_event.wait())

    done, _ = await asyncio.wait(
        {executor_task, shutdown_waiter},
        return_when=asyncio.FIRST_COMPLETED,
    )

    shutdown_waiter.cancel()
    with suppress(asyncio.CancelledError):
        await shutdown_waiter

    if executor_task in done:
        return await executor_task

    # シャットダウン要求 → 猶予時間内に完了を待つ
    try:
        return await asyncio.wait_for(executor_task, timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except TimeoutError:
        executor_task.cancel()
        with suppress(asyncio.CancelledError):
            await executor_task
        print(
            f"Warning: Shutdown timeout ({SHUTDOWN_TIMEOUT_SECONDS}s) expired, "
            f"returning {len(collected_results)} partial result(s)",
            file=sys.stderr,
        )
        return collected_results


async def run_review(
    target: DiffTarget | PRTarget | FileTarget,
    config_overrides: dict[str, object] | None = None,
    custom_agents_dir: Path | None = None,
) -> EngineResult:
    """レビュー実行パイプラインを実行する。

    パイプライン:
        1. 設定解決（resolve_config）
        2. エージェント読み込み（load_agents）
        3. 無効エージェント除外（enabled=false）
        4. レビュー指示構築（ReviewInstructionBuilder）
        5. セレクターエージェント実行（SelectorAgent）
        6. 実行コンテキスト構築（AgentExecutionContext）
        7. エージェント実行（Parallel or Sequential）
        8. 結果集約（ReviewReport）

    Args:
        target: レビュー対象（DiffTarget / PRTarget / FileTarget）。
        config_overrides: CLI からの設定オーバーライド。
        custom_agents_dir: カスタムエージェント定義ディレクトリ。

    Returns:
        EngineResult: レビューレポートと終了コード。
    """
    # Step 1: 設定解決
    config = resolve_config(cli_overrides=config_overrides)

    # Step 2: エージェント読み込み
    load_result = load_agents(custom_dir=custom_agents_dir)
    if load_result.errors:
        report_load_warnings(load_result.errors)

    # Step 3: 無効エージェント除外
    disabled_names = _get_disabled_names(config)
    filtered_result, _ = _filter_disabled_agents(load_result, disabled_names)

    # Step 4: レビュー指示構築
    user_message = build_review_instruction(target)

    # Step 5: セレクターエージェント実行
    try:
        selector_output = await run_selector(
            target=target,
            available_agents=filtered_result.agents,
            selector_config=config.selector,
            global_model=config.model,
            global_timeout=config.timeout,
            global_max_turns=config.max_turns,
        )
        report_selector_result(
            len(selector_output.selected_agents),
            selector_output.reasoning,
        )
    except SelectorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return _build_empty_engine_result(
            load_result.errors, exit_code=ExitCode.EXECUTION_ERROR
        )

    # 空選択 → 正常終了
    if not selector_output.selected_agents:
        return _build_empty_engine_result(
            load_result.errors, exit_code=ExitCode.SUCCESS
        )

    # Step 6: 実行コンテキスト構築
    selected_agents = _resolve_selected_agents(
        filtered_result.agents, selector_output.selected_agents
    )
    contexts = [
        build_execution_context(
            agent_def=agent,
            agent_config=config.agents.get(agent.name),
            global_config=config,
            user_message=user_message,
            resolved_tools=resolve_tools(agent.allowed_tools),
        )
        for agent in selected_agents
    ]

    # Step 7: エージェント実行（並列 or 逐次）
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    try:
        install_signal_handlers(shutdown_event, loop)
        executor = execute_parallel if config.parallel else execute_sequential
        results: list[AgentResult] = await _execute_with_shutdown_timeout(
            executor, contexts, shutdown_event
        )
    finally:
        uninstall_signal_handlers(loop)

    # Step 8: 結果集約
    report = _build_report(results, load_result.errors)
    exit_code = _determine_exit_code(results, report.summary)

    # 進捗サマリー
    _report_execution_summary(results)

    return EngineResult(report=report, exit_code=exit_code)


def _filter_disabled_agents(
    load_result: LoadResult,
    disabled_names: frozenset[str],
) -> tuple[LoadResult, list[str]]:
    """設定で無効化されたエージェントを除外する。

    Args:
        load_result: エージェント読み込み結果。
        disabled_names: enabled=false のエージェント名集合。

    Returns:
        フィルタ済みの LoadResult と除外されたエージェント名リスト。
    """
    filtered = tuple(a for a in load_result.agents if a.name not in disabled_names)
    removed = [a.name for a in load_result.agents if a.name in disabled_names]
    return LoadResult(agents=filtered, errors=load_result.errors), removed


def _get_disabled_names(config: HachimokuConfig) -> frozenset[str]:
    """設定から無効化されたエージェント名の集合を取得する。"""
    return frozenset(
        name for name, agent_cfg in config.agents.items() if not agent_cfg.enabled
    )


def _resolve_selected_agents(
    agents: tuple[AgentDefinition, ...],
    selected_names: list[str],
) -> list[AgentDefinition]:
    """選択されたエージェント名から AgentDefinition を解決する。

    selected_names にあるが agents にないエージェントは無視する。
    """
    agent_map = {a.name: a for a in agents}
    return [agent_map[name] for name in selected_names if name in agent_map]


def _build_report(
    results: list[AgentResult],
    load_errors: tuple[LoadError, ...],
) -> ReviewReport:
    """実行結果からレビューレポートを構築する。"""
    summary = _build_summary(results)
    return ReviewReport(
        results=results,
        summary=summary,
        load_errors=load_errors,
    )


def _build_summary(results: list[AgentResult]) -> ReviewSummary:
    """実行結果からレビューサマリーを構築する。"""
    all_issues = _collect_issues(results)

    max_severity: Severity | None = None
    if all_issues:
        max_severity = max(issue.severity for issue in all_issues)

    total_elapsed = sum(
        r.elapsed_time for r in results if isinstance(r, (AgentSuccess, AgentTruncated))
    )

    total_cost = _aggregate_cost(results)

    return ReviewSummary(
        total_issues=len(all_issues),
        max_severity=max_severity,
        total_elapsed_time=total_elapsed,
        total_cost=total_cost,
    )


def _collect_issues(results: list[AgentResult]) -> list[ReviewIssue]:
    """成功・切り詰め結果から issues を収集する。"""
    issues: list[ReviewIssue] = []
    for r in results:
        if isinstance(r, (AgentSuccess, AgentTruncated)):
            issues.extend(r.issues)
    return issues


def _aggregate_cost(results: list[AgentResult]) -> CostInfo | None:
    """成功結果から CostInfo を集約する。"""
    has_cost = any(isinstance(r, AgentSuccess) and r.cost is not None for r in results)
    if not has_cost:
        return None

    total_input = sum(
        r.cost.input_tokens
        for r in results
        if isinstance(r, AgentSuccess) and r.cost is not None
    )
    total_output = sum(
        r.cost.output_tokens
        for r in results
        if isinstance(r, AgentSuccess) and r.cost is not None
    )
    return CostInfo(
        input_tokens=total_input,
        output_tokens=total_output,
    )


def _determine_exit_code(
    results: list[AgentResult],
    summary: ReviewSummary,
) -> ExitCode:
    """実行結果から終了コードを決定する。

    FR-RE-009: 全エージェント失敗 → exit_code=3。
    成功/切り詰めあり → severity マッピングに基づく exit_code。
    """
    has_valid = any(isinstance(r, (AgentSuccess, AgentTruncated)) for r in results)
    if not has_valid:
        return ExitCode.EXECUTION_ERROR

    return determine_exit_code(summary.max_severity)


def _build_empty_engine_result(
    load_errors: tuple[LoadError, ...],
    exit_code: ExitCode,
) -> EngineResult:
    """空のレビューレポートを含む EngineResult を構築する。"""
    report = ReviewReport(
        results=[],
        summary=ReviewSummary(
            total_issues=0,
            max_severity=None,
            total_elapsed_time=0.0,
        ),
        load_errors=load_errors,
    )
    return EngineResult(report=report, exit_code=exit_code)


def _report_execution_summary(results: list[AgentResult]) -> None:
    """実行結果のサマリーを stderr に出力する。"""
    success_count = sum(1 for r in results if isinstance(r, AgentSuccess))
    truncated_count = sum(1 for r in results if isinstance(r, AgentTruncated))
    error_count = sum(1 for r in results if isinstance(r, AgentError))
    timeout_count = sum(1 for r in results if isinstance(r, AgentTimeout))

    report_summary(
        total=len(results),
        success=success_count,
        truncated=truncated_count,
        errors=error_count,
        timeouts=timeout_count,
    )
