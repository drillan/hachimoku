"""AgentRunner のテスト。

T020: pydantic-ai TestModel を使用し、run_agent の各結果パターンを検証する。
FR-RE-003: タイムアウト・ターン数制御・失敗許容。
FR-RE-004: タイムアウトと最大ターン数の制御。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError
from pydantic_ai import Tool

from hachimoku.agents.models import Phase
from hachimoku.engine._context import AgentExecutionContext
from hachimoku.engine._runner import run_agent
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)
from hachimoku.models.schemas import get_schema
from hachimoku.models.schemas._base import BaseAgentOutput


def _make_context(
    agent_name: str = "test-agent",
    timeout_seconds: int = 300,
    max_turns: int = 10,
    output_schema_name: str = "scored_issues",
    tools: tuple[Tool[None], ...] = (),
) -> AgentExecutionContext:
    """テスト用 AgentExecutionContext を生成するヘルパー。"""
    schema_cls = get_schema(output_schema_name)
    return AgentExecutionContext(
        agent_name=agent_name,
        model="test",
        system_prompt="You are a test review agent.",
        user_message="Review this code.",
        output_schema=schema_cls,
        tools=tools,
        timeout_seconds=timeout_seconds,
        max_turns=max_turns,
        phase=Phase.MAIN,
    )


def _make_dummy_tool() -> Tool[None]:
    """テスト用スタブツールを生成するヘルパー。"""

    def dummy_tool(query: str) -> str:
        """Dummy tool for testing."""
        return "dummy result"

    return Tool(dummy_tool, takes_ctx=False)


# =============================================================================
# run_agent — 正常完了 (AgentSuccess)
# =============================================================================


class TestRunAgentSuccess:
    """run_agent が AgentSuccess を返すケースのテスト。"""

    async def test_success_returns_agent_success(self) -> None:
        """正常完了時に AgentSuccess が返される。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)

    async def test_agent_name_propagated(self) -> None:
        """context.agent_name が結果に反映される。"""
        ctx = _make_context(agent_name="my-reviewer")
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert result.agent_name == "my-reviewer"

    async def test_elapsed_time_positive(self) -> None:
        """elapsed_time が正の値である。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert result.elapsed_time > 0

    async def test_cost_info_present(self) -> None:
        """CostInfo がトークン数を含む。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert result.cost is not None
        assert result.cost.input_tokens >= 0
        assert result.cost.output_tokens >= 0

    async def test_issues_list_returned(self) -> None:
        """出力の issues リストが結果に含まれる。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert isinstance(result.issues, list)


# =============================================================================
# run_agent — タイムアウト (AgentTimeout)
# =============================================================================


class TestRunAgentTimeout:
    """run_agent がタイムアウト時に AgentTimeout を返すケースのテスト。"""

    @patch("hachimoku.engine._runner.Agent")
    async def test_timeout_returns_agent_timeout(
        self, mock_agent_cls: MagicMock
    ) -> None:
        """asyncio.TimeoutError 発生時に AgentTimeout が返される。"""
        mock_instance = mock_agent_cls.return_value
        mock_instance.run = AsyncMock(side_effect=TimeoutError)

        ctx = _make_context(agent_name="timeout-agent", timeout_seconds=60)
        result = await run_agent(ctx)

        assert isinstance(result, AgentTimeout)
        assert result.agent_name == "timeout-agent"
        assert result.timeout_seconds == 60.0

    async def test_timeout_seconds_matches_context(self) -> None:
        """AgentTimeout の timeout_seconds が context の値と一致する。

        Note: タイムアウトを実際に発生させるテストは test_timeout_returns_agent_timeout
        で扱う。ここでは AgentTimeout モデルの構造を検証する。
        """
        timeout = AgentTimeout(agent_name="test", timeout_seconds=60.0)
        assert timeout.timeout_seconds == 60.0


# =============================================================================
# run_agent — ターン数超過 (AgentTruncated)
# =============================================================================


class TestRunAgentTruncated:
    """run_agent がターン数制限到達時に AgentTruncated を返すケースのテスト。"""

    async def test_usage_limit_returns_truncated(self) -> None:
        """request_limit=1 + ツール呼び出し強制で AgentTruncated が返される。"""
        tool = _make_dummy_tool()
        ctx = _make_context(max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)

    async def test_truncated_has_empty_issues(self) -> None:
        """AgentTruncated の issues リストは空（R-003）。"""
        tool = _make_dummy_tool()
        ctx = _make_context(max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)
        assert result.issues == []

    async def test_truncated_turns_consumed(self) -> None:
        """AgentTruncated の turns_consumed が max_turns と一致する。"""
        tool = _make_dummy_tool()
        ctx = _make_context(max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)
        assert result.turns_consumed == 1

    async def test_truncated_agent_name(self) -> None:
        """AgentTruncated の agent_name が context と一致する。"""
        tool = _make_dummy_tool()
        ctx = _make_context(agent_name="truncated-agent", max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)
        assert result.agent_name == "truncated-agent"


# =============================================================================
# run_agent — エラー (AgentError)
# =============================================================================


class TestRunAgentError:
    """run_agent が例外時に AgentError を返すケースのテスト。"""

    async def test_exception_returns_agent_error(self) -> None:
        """不正なモデル名で AgentError が返される。"""
        ctx = _make_context()
        # model フィールドを不正な値に差し替え（frozen なので新しいオブジェクトを作る）
        bad_ctx = AgentExecutionContext(
            agent_name=ctx.agent_name,
            model="nonexistent-model-that-will-fail",
            system_prompt=ctx.system_prompt,
            user_message=ctx.user_message,
            output_schema=ctx.output_schema,
            tools=ctx.tools,
            timeout_seconds=ctx.timeout_seconds,
            max_turns=ctx.max_turns,
            phase=ctx.phase,
        )
        result = await run_agent(bad_ctx)
        assert isinstance(result, AgentError)

    async def test_error_has_agent_name(self) -> None:
        """AgentError の agent_name が context と一致する。"""
        bad_ctx = AgentExecutionContext(
            agent_name="error-agent",
            model="nonexistent-model-that-will-fail",
            system_prompt="test",
            user_message="test",
            output_schema=get_schema("scored_issues"),
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        result = await run_agent(bad_ctx)
        assert isinstance(result, AgentError)
        assert result.agent_name == "error-agent"

    async def test_error_message_not_empty(self) -> None:
        """AgentError の error_message が空でない。"""
        bad_ctx = AgentExecutionContext(
            agent_name="error-agent",
            model="nonexistent-model-that-will-fail",
            system_prompt="test",
            user_message="test",
            output_schema=get_schema("scored_issues"),
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        result = await run_agent(bad_ctx)
        assert isinstance(result, AgentError)
        assert len(result.error_message) > 0


# =============================================================================
# run_agent — 出力スキーマ違反 (AgentError)
# =============================================================================


class TestRunAgentSchemaViolation:
    """run_agent が出力スキーマ違反時に AgentError を返すケースのテスト。"""

    @patch("hachimoku.engine._runner.Agent")
    async def test_validation_error_returns_agent_error(
        self, mock_agent_cls: MagicMock
    ) -> None:
        """出力パース時の ValidationError が AgentError に変換される。"""
        # BaseAgentOutput のバリデーションで実際の ValidationError を生成
        try:
            BaseAgentOutput.model_validate({"bad_field": "data"})
        except ValidationError as real_error:
            validation_error = real_error

        mock_instance = mock_agent_cls.return_value
        mock_instance.run = AsyncMock(side_effect=validation_error)

        ctx = _make_context(agent_name="schema-fail-agent")
        result = await run_agent(ctx)

        assert isinstance(result, AgentError)
        assert result.agent_name == "schema-fail-agent"
        assert len(result.error_message) > 0
