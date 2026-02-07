"""SequentialExecutor のテスト。

T022: group_by_phase のフェーズグルーピングと
execute_sequential の逐次実行（フェーズ順・名前辞書順）を検証する。
FR-RE-006: parallel=false の場合のフェーズ順序制御。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from pydantic_ai import Tool

from hachimoku.agents.models import Phase
from hachimoku.engine._context import AgentExecutionContext
from hachimoku.engine._executor import execute_sequential, group_by_phase
from hachimoku.models.agent_result import AgentError, AgentSuccess, AgentTimeout
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
