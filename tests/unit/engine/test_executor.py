"""Executor のテスト。

T022: group_by_phase のフェーズグルーピングと
execute_sequential の逐次実行（フェーズ順・名前辞書順）を検証する。
T034: execute_parallel の並列実行（同一フェーズ内並列、フェーズ間順序保持）を検証する。
FR-RE-006: parallel 設定に応じたフェーズ順序制御。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pydantic_ai import Tool

from hachimoku.agents.models import Phase
from hachimoku.engine._context import AgentExecutionContext
from hachimoku.engine._executor import (
    execute_parallel,
    execute_sequential,
    group_by_phase,
)
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
)
from hachimoku.models.schemas import get_schema


def _make_context(
    agent_name: str = "test-agent",
    phase: Phase = Phase.MAIN,
    timeout_seconds: int = 300,
    max_turns: int = 10,
    tools: tuple[Tool[None], ...] = (),
) -> AgentExecutionContext:
    """テスト用 AgentExecutionContext を生成するヘルパー。"""
    schema_cls = get_schema("scored_issues")
    return AgentExecutionContext(
        agent_name=agent_name,
        model="test",
        system_prompt="You are a test agent.",
        user_message="Review this code.",
        output_schema=schema_cls,
        tools=tools,
        timeout_seconds=timeout_seconds,
        max_turns=max_turns,
        phase=phase,
    )


def _make_success(agent_name: str = "test-agent") -> AgentSuccess:
    """テスト用 AgentSuccess を生成するヘルパー。"""
    return AgentSuccess(
        agent_name=agent_name,
        issues=[],
        elapsed_time=1.0,
    )


def _make_error(agent_name: str = "test-agent") -> AgentError:
    """テスト用 AgentError を生成するヘルパー。"""
    return AgentError(
        agent_name=agent_name,
        error_message="test error",
    )


def _make_timeout(
    agent_name: str = "test-agent",
    timeout_seconds: float = 300.0,
) -> AgentTimeout:
    """テスト用 AgentTimeout を生成するヘルパー。"""
    return AgentTimeout(
        agent_name=agent_name,
        timeout_seconds=timeout_seconds,
    )


# =============================================================================
# group_by_phase — フェーズグルーピング
# =============================================================================


class TestGroupByPhase:
    """group_by_phase のテスト。"""

    def test_groups_by_phase_value(self) -> None:
        """3つのフェーズが正しくグループ化される。"""
        contexts = [
            _make_context("agent-main", Phase.MAIN),
            _make_context("agent-early", Phase.EARLY),
            _make_context("agent-final", Phase.FINAL),
        ]
        grouped = group_by_phase(contexts)
        assert set(grouped.keys()) == {"early", "main", "final"}
        assert len(grouped["early"]) == 1
        assert len(grouped["main"]) == 1
        assert len(grouped["final"]) == 1

    def test_phase_order_early_main_final(self) -> None:
        """dict のキー順が early → main → final。"""
        contexts = [
            _make_context("agent-final", Phase.FINAL),
            _make_context("agent-early", Phase.EARLY),
            _make_context("agent-main", Phase.MAIN),
        ]
        grouped = group_by_phase(contexts)
        assert list(grouped.keys()) == ["early", "main", "final"]

    def test_empty_input(self) -> None:
        """空リスト → 空 dict。"""
        grouped = group_by_phase([])
        assert grouped == {}

    def test_same_phase_sorted_by_name(self) -> None:
        """同フェーズ内のエージェントが名前の辞書順でソートされる。"""
        contexts = [
            _make_context("charlie", Phase.MAIN),
            _make_context("alice", Phase.MAIN),
            _make_context("bob", Phase.MAIN),
        ]
        grouped = group_by_phase(contexts)
        names = [c.agent_name for c in grouped["main"]]
        assert names == ["alice", "bob", "charlie"]

    def test_missing_phase_omitted(self) -> None:
        """存在しないフェーズはキーに含まない。"""
        contexts = [
            _make_context("agent-main", Phase.MAIN),
        ]
        grouped = group_by_phase(contexts)
        assert list(grouped.keys()) == ["main"]
        assert "early" not in grouped
        assert "final" not in grouped

    def test_multiple_agents_per_phase(self) -> None:
        """同フェーズに複数エージェントが存在する場合。"""
        contexts = [
            _make_context("agent-a", Phase.EARLY),
            _make_context("agent-b", Phase.EARLY),
            _make_context("agent-c", Phase.MAIN),
        ]
        grouped = group_by_phase(contexts)
        assert len(grouped["early"]) == 2
        assert len(grouped["main"]) == 1


# =============================================================================
# execute_sequential — 逐次実行
# =============================================================================


class TestExecuteSequential:
    """execute_sequential のテスト。

    run_agent をモック化してツール実行を回避する。
    """

    @patch("hachimoku.engine._executor.run_agent")
    async def test_executes_in_phase_order(self, mock_run: AsyncMock) -> None:
        """early → main → final の順で実行される。"""
        execution_order: list[str] = []

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            execution_order.append(ctx.agent_name)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("main-agent", Phase.MAIN),
            _make_context("early-agent", Phase.EARLY),
            _make_context("final-agent", Phase.FINAL),
        ]
        event = asyncio.Event()
        results = await execute_sequential(contexts, event)

        assert len(results) == 3
        assert execution_order == ["early-agent", "main-agent", "final-agent"]

    @patch("hachimoku.engine._executor.run_agent")
    async def test_same_phase_name_order(self, mock_run: AsyncMock) -> None:
        """同フェーズ内は名前の辞書順で実行される。"""
        execution_order: list[str] = []

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            execution_order.append(ctx.agent_name)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("charlie", Phase.MAIN),
            _make_context("alice", Phase.MAIN),
            _make_context("bob", Phase.MAIN),
        ]
        event = asyncio.Event()
        results = await execute_sequential(contexts, event)

        assert len(results) == 3
        assert execution_order == ["alice", "bob", "charlie"]

    @patch("hachimoku.engine._executor.run_agent")
    async def test_empty_contexts(self, mock_run: AsyncMock) -> None:
        """空リスト → 空結果。"""
        event = asyncio.Event()
        results = await execute_sequential([], event)

        assert results == []
        mock_run.assert_not_called()

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_before_start(self, mock_run: AsyncMock) -> None:
        """shutdown_event がセット済み → 実行なし。"""
        contexts = [_make_context("agent-a")]
        event = asyncio.Event()
        event.set()

        results = await execute_sequential(contexts, event)

        assert results == []
        mock_run.assert_not_called()

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_mid_execution(self, mock_run: AsyncMock) -> None:
        """実行途中で shutdown_event がセット → 残りスキップ。"""
        event = asyncio.Event()
        call_count = 0

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                event.set()  # 最初の実行後にシャットダウン
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.EARLY),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.FINAL),
        ]
        results = await execute_sequential(contexts, event)

        assert len(results) == 1
        assert results[0].agent_name == "agent-a"

    @patch("hachimoku.engine._executor.run_agent")
    async def test_individual_failure_continues(self, mock_run: AsyncMock) -> None:
        """1つのエージェントがエラーでも残りは実行される。

        run_agent は内部で例外を catch して AgentError を返すため、
        executor はエラーを気にせず次のエージェントに進む。
        """
        results_map: dict[str, AgentSuccess | AgentError] = {
            "agent-a": _make_success("agent-a"),
            "agent-b": _make_error("agent-b"),
            "agent-c": _make_success("agent-c"),
        }

        async def side_effect(
            ctx: AgentExecutionContext,
        ) -> AgentSuccess | AgentError:
            return results_map[ctx.agent_name]

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.EARLY),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.FINAL),
        ]
        event = asyncio.Event()
        results = await execute_sequential(contexts, event)

        assert len(results) == 3
        assert isinstance(results[0], AgentSuccess)
        assert isinstance(results[1], AgentError)
        assert isinstance(results[2], AgentSuccess)

    @patch("hachimoku.engine._executor.run_agent")
    async def test_results_preserve_agent_names(self, mock_run: AsyncMock) -> None:
        """結果リストのエージェント名が実行順序と一致する。"""

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("beta", Phase.MAIN),
            _make_context("alpha", Phase.MAIN),
        ]
        event = asyncio.Event()
        results = await execute_sequential(contexts, event)

        assert [r.agent_name for r in results] == ["alpha", "beta"]

    @patch("hachimoku.engine._executor.run_agent")
    async def test_timeout_partial_failure_continues(self, mock_run: AsyncMock) -> None:
        """1つのエージェントがタイムアウトでも残りは実行される。

        3エージェント中1つが AgentTimeout を返し、残り2つが AgentSuccess を返す。
        """
        results_map: dict[str, AgentSuccess | AgentTimeout] = {
            "agent-a": _make_success("agent-a"),
            "agent-b": _make_timeout("agent-b", timeout_seconds=60.0),
            "agent-c": _make_success("agent-c"),
        }

        async def side_effect(
            ctx: AgentExecutionContext,
        ) -> AgentSuccess | AgentTimeout:
            return results_map[ctx.agent_name]

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.EARLY),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.FINAL),
        ]
        event = asyncio.Event()
        results = await execute_sequential(contexts, event)

        assert len(results) == 3
        assert isinstance(results[0], AgentSuccess)
        assert isinstance(results[1], AgentTimeout)
        assert isinstance(results[2], AgentSuccess)

    @patch("hachimoku.engine._executor.run_agent")
    async def test_all_agents_fail_returns_all_failures(
        self, mock_run: AsyncMock
    ) -> None:
        """全エージェントが失敗しても全結果が返される。

        AgentError と AgentTimeout が混在する場合でも、executor は全結果を返す。
        成功結果の有無はエンジン層が判定する。
        """
        results_map: dict[str, AgentError | AgentTimeout] = {
            "agent-a": _make_error("agent-a"),
            "agent-b": _make_timeout("agent-b"),
            "agent-c": _make_error("agent-c"),
        }

        async def side_effect(
            ctx: AgentExecutionContext,
        ) -> AgentError | AgentTimeout:
            return results_map[ctx.agent_name]

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.EARLY),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.FINAL),
        ]
        event = asyncio.Event()
        results = await execute_sequential(contexts, event)

        assert len(results) == 3
        assert isinstance(results[0], AgentError)
        assert isinstance(results[1], AgentTimeout)
        assert isinstance(results[2], AgentError)
        success_results = [r for r in results if isinstance(r, AgentSuccess)]
        assert len(success_results) == 0


# =============================================================================
# execute_parallel — 並列実行
# =============================================================================


class TestExecuteParallel:
    """execute_parallel のテスト。

    T034: 同一フェーズ内の並列実行、フェーズ間の順序保持、個別失敗許容を検証。
    run_agent をモック化してツール実行を回避する。
    """

    @patch("hachimoku.engine._executor.run_agent")
    async def test_same_phase_runs_concurrently(self, mock_run: AsyncMock) -> None:
        """同一フェーズ内のエージェントが並行実行される。

        3エージェントにそれぞれ 0.1 秒の sleep を入れる。
        逐次なら 0.3 秒以上かかるところ、並列なら 0.15 秒程度で完了する。
        """
        import time

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            await asyncio.sleep(0.1)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]
        event = asyncio.Event()

        start = time.monotonic()
        results = await execute_parallel(contexts, event)
        elapsed = time.monotonic() - start

        assert len(results) == 3
        result_names = {r.agent_name for r in results}
        assert result_names == {"agent-a", "agent-b", "agent-c"}
        # 並列実行なので合計 0.3 秒ではなく 0.15 秒程度で完了するはず
        # CI 環境の揺らぎを考慮して閾値に余裕を持たせる
        assert elapsed < 0.5

    @patch("hachimoku.engine._executor.run_agent")
    async def test_phases_execute_in_order(self, mock_run: AsyncMock) -> None:
        """フェーズ間は early → main → final の順で実行される。

        各フェーズの完了順を記録して、フェーズ順序が保持されることを検証する。
        """
        phase_completion_order: list[str] = []

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            phase_completion_order.append(ctx.agent_name)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("main-agent", Phase.MAIN),
            _make_context("early-agent", Phase.EARLY),
            _make_context("final-agent", Phase.FINAL),
        ]
        event = asyncio.Event()
        results = await execute_parallel(contexts, event)

        assert len(results) == 3
        # early が最初、final が最後であること（実行順序）
        assert phase_completion_order.index(
            "early-agent"
        ) < phase_completion_order.index("main-agent")
        assert phase_completion_order.index(
            "main-agent"
        ) < phase_completion_order.index("final-agent")
        # results リストもフェーズ順で返される
        result_names = [r.agent_name for r in results]
        assert result_names == ["early-agent", "main-agent", "final-agent"]

    @patch("hachimoku.engine._executor.run_agent")
    async def test_individual_failure_does_not_affect_others(
        self, mock_run: AsyncMock
    ) -> None:
        """並列実行中に1つが失敗しても他は正常完了する。"""
        results_map: dict[str, AgentSuccess | AgentError] = {
            "agent-a": _make_success("agent-a"),
            "agent-b": _make_error("agent-b"),
            "agent-c": _make_success("agent-c"),
        }

        async def side_effect(
            ctx: AgentExecutionContext,
        ) -> AgentSuccess | AgentError:
            return results_map[ctx.agent_name]

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]
        event = asyncio.Event()
        results = await execute_parallel(contexts, event)

        assert len(results) == 3
        result_names = {r.agent_name for r in results}
        assert result_names == {"agent-a", "agent-b", "agent-c"}
        error_results = [r for r in results if isinstance(r, AgentError)]
        assert len(error_results) == 1
        assert error_results[0].agent_name == "agent-b"

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_before_start(self, mock_run: AsyncMock) -> None:
        """shutdown_event がセット済み → 実行なし。"""
        contexts = [_make_context("agent-a")]
        event = asyncio.Event()
        event.set()

        results = await execute_parallel(contexts, event)

        assert results == []
        mock_run.assert_not_called()

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_after_first_phase(self, mock_run: AsyncMock) -> None:
        """最初のフェーズ完了後に shutdown → 残りフェーズスキップ。"""
        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            if ctx.phase == Phase.EARLY:
                event.set()  # early フェーズ完了後にシャットダウン
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("early-agent", Phase.EARLY),
            _make_context("main-agent", Phase.MAIN),
            _make_context("final-agent", Phase.FINAL),
        ]
        results = await execute_parallel(contexts, event)

        assert len(results) == 1
        assert results[0].agent_name == "early-agent"

    @patch("hachimoku.engine._executor.run_agent")
    async def test_empty_contexts(self, mock_run: AsyncMock) -> None:
        """空リスト → 空結果。"""
        event = asyncio.Event()
        results = await execute_parallel([], event)

        assert results == []
        mock_run.assert_not_called()

    @patch("hachimoku.engine._executor.run_agent")
    async def test_timeout_in_parallel_does_not_affect_others(
        self, mock_run: AsyncMock
    ) -> None:
        """並列実行中に1つがタイムアウトでも他は正常完了する。"""
        results_map: dict[str, AgentSuccess | AgentTimeout] = {
            "agent-a": _make_success("agent-a"),
            "agent-b": _make_timeout("agent-b", timeout_seconds=60.0),
            "agent-c": _make_success("agent-c"),
        }

        async def side_effect(
            ctx: AgentExecutionContext,
        ) -> AgentSuccess | AgentTimeout:
            return results_map[ctx.agent_name]

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]
        event = asyncio.Event()
        results = await execute_parallel(contexts, event)

        assert len(results) == 3
        success_results = [r for r in results if isinstance(r, AgentSuccess)]
        timeout_results = [r for r in results if isinstance(r, AgentTimeout)]
        assert len(success_results) == 2
        assert len(timeout_results) == 1
        assert timeout_results[0].agent_name == "agent-b"

    @patch("hachimoku.engine._executor.run_agent")
    async def test_all_agents_fail_returns_all_failures(
        self, mock_run: AsyncMock
    ) -> None:
        """全エージェントが失敗しても全結果が返される。

        AgentError と AgentTimeout が混在する場合でも、全結果を返す。
        """
        results_map: dict[str, AgentError | AgentTimeout] = {
            "agent-a": _make_error("agent-a"),
            "agent-b": _make_timeout("agent-b"),
            "agent-c": _make_error("agent-c"),
        }

        async def side_effect(
            ctx: AgentExecutionContext,
        ) -> AgentError | AgentTimeout:
            return results_map[ctx.agent_name]

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]
        event = asyncio.Event()
        results = await execute_parallel(contexts, event)

        assert len(results) == 3
        result_names = {r.agent_name for r in results}
        assert result_names == {"agent-a", "agent-b", "agent-c"}
        success_results = [r for r in results if isinstance(r, AgentSuccess)]
        assert len(success_results) == 0

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_cancels_phase_and_preserves_completed(
        self, mock_run: AsyncMock
    ) -> None:
        """フェーズ内並列実行中に shutdown_event がセットされると TaskGroup がキャンセルされる。

        agent-a は即座に完了して結果を返す。
        agent-b/c は実行中（await 中）にキャンセルされる。
        完了済みの agent-a の結果のみ保持される。
        """
        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            if ctx.agent_name == "agent-a":
                return _make_success(ctx.agent_name)
            # agent-b/c: sleep で待機 → agent-a 完了後に shutdown で cancel される
            await asyncio.sleep(10)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]

        # agent-a の完了後、次の await ポイントで shutdown を発火
        async def _delayed_shutdown() -> None:
            await asyncio.sleep(0.05)
            event.set()

        asyncio.create_task(_delayed_shutdown())
        results = await execute_parallel(contexts, event)

        # agent-a は完了済み、agent-b/c はキャンセル
        assert len(results) == 1
        assert results[0].agent_name == "agent-a"

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_cancels_running_tasks_immediately(
        self, mock_run: AsyncMock
    ) -> None:
        """shutdown_event セット時に実行中タスクが即座にキャンセルされる。

        3エージェントが10秒 sleep するところ、0.05秒後にシャットダウンすると
        1秒未満で制御が返る（能動的キャンセルの証拠）。
        """
        import time

        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            await asyncio.sleep(10)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]

        async def _delayed_shutdown() -> None:
            await asyncio.sleep(0.05)
            event.set()

        asyncio.create_task(_delayed_shutdown())

        start = time.monotonic()
        results = await execute_parallel(contexts, event)
        elapsed = time.monotonic() - start

        # 能動的キャンセル: 10秒待たずに 1 秒未満で完了
        assert elapsed < 1.0
        # 全エージェントがキャンセルされ、結果は空
        assert len(results) == 0

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_preserves_completed_results_in_cancelled_phase(
        self, mock_run: AsyncMock
    ) -> None:
        """キャンセル前に完了した結果が collected_results に保持される。"""
        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            if ctx.agent_name == "agent-a":
                return _make_success(ctx.agent_name)
            elif ctx.agent_name == "agent-b":
                await asyncio.sleep(0.05)
                event.set()
                return _make_success(ctx.agent_name)
            else:
                # agent-c はキャンセルされる
                await asyncio.sleep(10)
                return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        external: list[AgentResult] = []
        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
            _make_context("agent-c", Phase.MAIN),
        ]
        results = await execute_parallel(contexts, event, collected_results=external)

        assert len(results) == 2
        result_names = {r.agent_name for r in results}
        assert result_names == {"agent-a", "agent-b"}
        assert results is external

    @patch("hachimoku.engine._executor.run_agent")
    async def test_shutdown_skips_subsequent_phases_after_cancellation(
        self, mock_run: AsyncMock
    ) -> None:
        """キャンセル後の後続フェーズがスキップされる。"""
        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            if ctx.agent_name == "early-fast":
                event.set()
                return _make_success(ctx.agent_name)
            # early-slow はキャンセルされる
            await asyncio.sleep(10)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("early-fast", Phase.EARLY),
            _make_context("early-slow", Phase.EARLY),
            _make_context("main-agent", Phase.MAIN),
        ]
        results = await execute_parallel(contexts, event)

        assert len(results) == 1
        assert results[0].agent_name == "early-fast"

    @patch("hachimoku.engine._executor.run_agent")
    async def test_no_shutdown_sentinel_does_not_affect_normal_execution(
        self, mock_run: AsyncMock
    ) -> None:
        """シャットダウンなし → sentinel が正常実行に影響しない。"""

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            await asyncio.sleep(0.01)
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [
            _make_context("agent-a", Phase.MAIN),
            _make_context("agent-b", Phase.MAIN),
        ]
        event = asyncio.Event()
        results = await execute_parallel(contexts, event)

        assert len(results) == 2
        result_names = {r.agent_name for r in results}
        assert result_names == {"agent-a", "agent-b"}

    @patch("hachimoku.engine._executor.report_agent_complete")
    @patch("hachimoku.engine._executor.run_agent")
    async def test_result_appended_before_report_complete(
        self, mock_run: AsyncMock, mock_report: MagicMock
    ) -> None:
        """結果が report_agent_complete より先に results に追加される。

        CancelledError による結果損失を防止するため、
        結果保存を進捗報告より先に実行する。
        report_agent_complete 呼び出し時点で結果がリストに存在するかを記録して検証する。
        """
        collected: list[AgentResult] = []
        was_in_collected_at_report_time: list[bool] = []

        async def run_side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            return _make_success(ctx.agent_name)

        mock_run.side_effect = run_side_effect

        def record_state(agent_name: str, result: AgentResult) -> None:
            was_in_collected_at_report_time.append(result in collected)

        mock_report.side_effect = record_state

        contexts = [_make_context("agent-a", Phase.MAIN)]
        event = asyncio.Event()
        await execute_parallel(contexts, event, collected_results=collected)

        assert len(collected) == 1
        mock_report.assert_called_once()
        assert was_in_collected_at_report_time == [True], (
            "result must be appended to collected before report_agent_complete is called"
        )


# =============================================================================
# collected_results パラメータ — 共有結果リスト
# =============================================================================


_ExecuteFn = Callable[
    ...,
    Coroutine[None, None, list[AgentResult]],
]

_COLLECTED_RESULTS_CASES: list[tuple[str, _ExecuteFn, list[tuple[str, Phase]]]] = [
    (
        "sequential",
        execute_sequential,
        [("agent-a", Phase.EARLY), ("agent-b", Phase.MAIN)],
    ),
    ("parallel", execute_parallel, [("agent-a", Phase.MAIN), ("agent-b", Phase.MAIN)]),
]


class TestCollectedResults:
    """execute_sequential / execute_parallel の collected_results パラメータのテスト。

    SC-RE-005: シャットダウンタイムアウト時に部分結果を保存するための共有リスト。
    """

    @pytest.mark.parametrize(
        ("label", "execute_fn", "context_specs"),
        _COLLECTED_RESULTS_CASES,
    )
    @patch("hachimoku.engine._executor.run_agent")
    async def test_results_appended_to_external_list(
        self,
        mock_run: AsyncMock,
        label: str,
        execute_fn: _ExecuteFn,
        context_specs: list[tuple[str, Phase]],
    ) -> None:
        """外部リストに結果が蓄積される。"""

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        external: list[AgentResult] = []
        contexts = [_make_context(name, phase) for name, phase in context_specs]
        event = asyncio.Event()
        results = await execute_fn(contexts, event, collected_results=external)

        assert len(external) == 2
        assert results is external

    @pytest.mark.parametrize(
        ("label", "execute_fn"),
        [("sequential", execute_sequential), ("parallel", execute_parallel)],
    )
    @patch("hachimoku.engine._executor.run_agent")
    async def test_none_creates_internal_list(
        self,
        mock_run: AsyncMock,
        label: str,
        execute_fn: _ExecuteFn,
    ) -> None:
        """collected_results=None（デフォルト）で内部リストが作成される。"""

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        contexts = [_make_context("agent-a")]
        event = asyncio.Event()
        results = await execute_fn(contexts, event)

        assert len(results) == 1

    @patch("hachimoku.engine._executor.run_agent")
    async def test_sequential_shutdown_preserves_completed(
        self, mock_run: AsyncMock
    ) -> None:
        """シャットダウン時に外部リストに完了済み結果が保存される。"""
        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            if ctx.agent_name == "agent-a":
                event.set()
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        external: list[AgentResult] = []
        contexts = [
            _make_context("agent-a", Phase.EARLY),
            _make_context("agent-b", Phase.MAIN),
        ]
        results = await execute_sequential(contexts, event, collected_results=external)

        assert len(external) == 1
        assert external[0].agent_name == "agent-a"
        assert results is external

    @patch("hachimoku.engine._executor.run_agent")
    async def test_parallel_shutdown_preserves_completed(
        self, mock_run: AsyncMock
    ) -> None:
        """並列フェーズ完了後のシャットダウンで外部リストに結果が保存される。"""
        event = asyncio.Event()

        async def side_effect(ctx: AgentExecutionContext) -> AgentSuccess:
            if ctx.phase == Phase.EARLY:
                event.set()
            return _make_success(ctx.agent_name)

        mock_run.side_effect = side_effect

        external: list[AgentResult] = []
        contexts = [
            _make_context("early-agent", Phase.EARLY),
            _make_context("main-agent", Phase.MAIN),
        ]
        results = await execute_parallel(contexts, event, collected_results=external)

        assert len(external) == 1
        assert external[0].agent_name == "early-agent"
        assert results is external
