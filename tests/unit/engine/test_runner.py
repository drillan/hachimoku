"""AgentRunner のテスト。

T020: pydantic-ai TestModel を使用し、run_agent の各結果パターンを検証する。
FR-RE-003: タイムアウト・ターン数制御・失敗許容。
FR-RE-004: タイムアウトと最大ターン数の制御。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claudecode_model import ClaudeCodeModel
from claudecode_model.exceptions import CLIExecutionError
from pydantic import ValidationError
from pydantic_ai import Tool
from pydantic_ai.usage import UsageLimits

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

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_success_returns_agent_success(self, _: MagicMock) -> None:
        """正常完了時に AgentSuccess が返される。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_agent_name_propagated(self, _: MagicMock) -> None:
        """context.agent_name が結果に反映される。"""
        ctx = _make_context(agent_name="my-reviewer")
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert result.agent_name == "my-reviewer"

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_elapsed_time_positive(self, _: MagicMock) -> None:
        """elapsed_time が正の値である。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert result.elapsed_time > 0

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_cost_info_present(self, _: MagicMock) -> None:
        """CostInfo がトークン数を含む。"""
        ctx = _make_context()
        result = await run_agent(ctx)
        assert isinstance(result, AgentSuccess)
        assert result.cost is not None
        assert result.cost.input_tokens >= 0
        assert result.cost.output_tokens >= 0

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_issues_list_returned(self, _: MagicMock) -> None:
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

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_timeout_returns_agent_timeout(
        self, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """CLIExecutionError(error_type="timeout") 発生時に AgentTimeout が返される。"""
        mock_run_safe.side_effect = CLIExecutionError(
            "SDK query timed out after 60 seconds",
            exit_code=2,
            stderr="Query was cancelled due to timeout",
            error_type="timeout",
        )

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

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_usage_limit_returns_truncated(self, _: MagicMock) -> None:
        """request_limit=1 + ツール呼び出し強制で AgentTruncated が返される。"""
        tool = _make_dummy_tool()
        ctx = _make_context(max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_truncated_has_empty_issues(self, _: MagicMock) -> None:
        """AgentTruncated の issues リストは空（R-003）。"""
        tool = _make_dummy_tool()
        ctx = _make_context(max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)
        assert result.issues == []

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_truncated_turns_consumed(self, _: MagicMock) -> None:
        """AgentTruncated の turns_consumed が max_turns と一致する。"""
        tool = _make_dummy_tool()
        ctx = _make_context(max_turns=1, tools=(tool,))
        result = await run_agent(ctx)
        assert isinstance(result, AgentTruncated)
        assert result.turns_consumed == 1

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_truncated_agent_name(self, _: MagicMock) -> None:
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

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_exception_returns_agent_error(self, _: MagicMock) -> None:
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

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_error_has_agent_name(self, _: MagicMock) -> None:
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

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    async def test_error_message_not_empty(self, _: MagicMock) -> None:
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

    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_validation_error_returns_agent_error(
        self, mock_run_safe: AsyncMock
    ) -> None:
        """出力パース時の ValidationError が AgentError に変換される。"""
        # BaseAgentOutput のバリデーションで実際の ValidationError を生成
        try:
            BaseAgentOutput.model_validate({"bad_field": "data"})
        except ValidationError as real_error:
            validation_error = real_error

        mock_run_safe.side_effect = validation_error

        ctx = _make_context(agent_name="schema-fail-agent")
        result = await run_agent(ctx)

        assert isinstance(result, AgentError)
        assert result.agent_name == "schema-fail-agent"
        assert len(result.error_message) > 0


# =============================================================================
# run_agent — resolve_model 統合
# =============================================================================


class TestRunAgentResolveModel:
    """run_agent が resolve_model を呼び出して Agent を構築するテスト。"""

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model")
    @patch("hachimoku.engine._runner.Agent")
    async def test_resolve_model_called_with_context_values(
        self,
        mock_agent_cls: MagicMock,
        mock_resolve: MagicMock,
        mock_run_safe: AsyncMock,
    ) -> None:
        """resolve_model が context.model で呼ばれる。"""
        mock_resolve.return_value = "resolved-model"
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = _make_context()
        await run_agent(ctx)

        mock_resolve.assert_called_once_with("test", extra_builtin_tools=())

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model")
    @patch("hachimoku.engine._runner.Agent")
    async def test_resolved_model_passed_to_agent(
        self,
        mock_agent_cls: MagicMock,
        mock_resolve: MagicMock,
        mock_run_safe: AsyncMock,
    ) -> None:
        """resolve_model の戻り値が Agent(model=...) に渡される。"""
        mock_resolve.return_value = "resolved-model"
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = _make_context()
        await run_agent(ctx)

        mock_agent_cls.assert_called_once()
        assert mock_agent_cls.call_args.kwargs["model"] == "resolved-model"

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model")
    @patch("hachimoku.engine._runner.Agent")
    async def test_registers_toolsets_for_claudecode_model(
        self,
        mock_agent_cls: MagicMock,
        mock_resolve: MagicMock,
        mock_run_safe: AsyncMock,
    ) -> None:
        """ClaudeCodeModel の場合、set_agent_toolsets が呼ばれる。"""
        mock_model = MagicMock(spec=ClaudeCodeModel)
        mock_resolve.return_value = mock_model
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result
        mock_instance = mock_agent_cls.return_value

        ctx = _make_context()
        await run_agent(ctx)

        mock_model.set_agent_toolsets.assert_called_once_with(
            mock_instance._function_toolset
        )

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.Agent")
    async def test_skips_toolset_registration_for_string_model(
        self, mock_agent_cls: MagicMock, _: MagicMock, mock_run_safe: AsyncMock
    ) -> None:
        """文字列モデルの場合、set_agent_toolsets は呼ばれない。"""
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = _make_context()
        result = await run_agent(ctx)

        assert isinstance(result, AgentSuccess)


# =============================================================================
# run_agent — model_settings 統合
# =============================================================================


class TestRunAgentModelSettings:
    """run_agent が run_agent_safe に model_settings を渡すテスト。"""

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_model_settings_max_turns_passed(
        self, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """run_agent_safe に model_settings={"max_turns": N, "timeout": T} が渡される。"""
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = _make_context(max_turns=10)
        await run_agent(ctx)

        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"] == {"max_turns": 10, "timeout": 300}
        assert call_kwargs["usage_limits"] == UsageLimits(request_limit=10)

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_model_settings_timeout_passed(
        self, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """run_agent_safe に context.timeout_seconds が model_settings["timeout"] に渡される。"""
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = _make_context(timeout_seconds=600)
        await run_agent(ctx)

        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"]["timeout"] == 600


# =============================================================================
# run_agent — CLIExecutionError 診断情報保存
# =============================================================================


class TestRunAgentErrorDiagnostics:
    """run_agent が CLIExecutionError の構造化属性を AgentError に保存するテスト。"""

    @pytest.mark.parametrize(
        ("error_kwargs", "assert_field", "expected_value"),
        [
            (
                {"exit_code": 1, "stderr": "error", "error_type": "unknown"},
                "exit_code",
                1,
            ),
            (
                {
                    "exit_code": 1,
                    "stderr": "detailed error output",
                    "error_type": "unknown",
                },
                "stderr",
                "detailed error output",
            ),
            (
                {"exit_code": 2, "stderr": "", "error_type": "permission"},
                "error_type",
                "permission",
            ),
            (
                {"exit_code": 1, "stderr": "", "error_type": "unknown"},
                "stderr",
                "",
            ),
        ],
    )
    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_cli_execution_error_preserves_field(
        self,
        mock_run_safe: AsyncMock,
        _: MagicMock,
        error_kwargs: dict[str, object],
        assert_field: str,
        expected_value: object,
    ) -> None:
        """CLIExecutionError の各属性が AgentError に保存される。"""
        mock_run_safe.side_effect = CLIExecutionError("CLI failed", **error_kwargs)  # type: ignore[arg-type]
        ctx = _make_context(agent_name="cli-error-agent")
        result = await run_agent(ctx)

        assert isinstance(result, AgentError)
        assert getattr(result, assert_field) == expected_value

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_non_cli_exception_has_none_optional_fields(
        self, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """CLIExecutionError 以外の例外では新規フィールドが None のままである。"""
        mock_run_safe.side_effect = RuntimeError("unexpected")

        ctx = _make_context(agent_name="generic-error-agent")
        result = await run_agent(ctx)

        assert isinstance(result, AgentError)
        assert result.exit_code is None
        assert result.error_type is None
        assert result.stderr is None


# =============================================================================
# run_agent — エラー時ログ出力
# =============================================================================


class TestRunAgentErrorLogging:
    """run_agent がエラー時にログ出力するテスト。"""

    @patch("hachimoku.engine._runner.resolve_model", side_effect=lambda m, **_kw: m)
    @patch("hachimoku.engine._runner.run_agent_safe")
    async def test_exception_is_logged_with_warning(
        self, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """例外発生時に logger.warning が呼ばれる。"""
        mock_run_safe.side_effect = RuntimeError("test error")

        ctx = _make_context(agent_name="log-test-agent")
        with patch("hachimoku.engine._runner.logger") as mock_logger:
            await run_agent(ctx)
            mock_logger.warning.assert_called_once()
            call_args = str(mock_logger.warning.call_args)
            assert "log-test-agent" in call_args
            assert "RuntimeError" in call_args


# =============================================================================
# run_agent — builtin_tools 統合（Issue #222）
# =============================================================================


class TestRunAgentBuiltinTools:
    """run_agent が builtin_tools を Agent に渡すテスト。Issue #222。"""

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model")
    @patch("hachimoku.engine._runner.Agent")
    async def test_builtin_tools_passed_to_agent(
        self,
        mock_agent_cls: MagicMock,
        mock_resolve: MagicMock,
        mock_run_safe: AsyncMock,
    ) -> None:
        """context.builtin_tools が Agent(builtin_tools=...) に渡される。"""
        from pydantic_ai.builtin_tools import WebFetchTool

        mock_resolve.return_value = "resolved-model"
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        wft = WebFetchTool()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="test",
            system_prompt="prompt",
            user_message="msg",
            output_schema=get_schema("scored_issues"),
            tools=(),
            builtin_tools=(wft,),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        await run_agent(ctx)

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["builtin_tools"] == [wft]

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model")
    @patch("hachimoku.engine._runner.Agent")
    async def test_empty_builtin_tools_passed(
        self,
        mock_agent_cls: MagicMock,
        mock_resolve: MagicMock,
        mock_run_safe: AsyncMock,
    ) -> None:
        """builtin_tools=() のとき空リストが Agent に渡される。"""
        mock_resolve.return_value = "resolved-model"
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = _make_context()
        await run_agent(ctx)

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["builtin_tools"] == []

    @patch("hachimoku.engine._runner.run_agent_safe")
    @patch("hachimoku.engine._runner.resolve_model")
    @patch("hachimoku.engine._runner.Agent")
    async def test_claudecode_builtin_names_passed_to_resolve_model(
        self,
        mock_agent_cls: MagicMock,
        mock_resolve: MagicMock,
        mock_run_safe: AsyncMock,
    ) -> None:
        """context.claudecode_builtin_names が resolve_model の extra_builtin_tools に渡される。"""
        mock_resolve.return_value = "resolved-model"
        mock_result = MagicMock()
        mock_result.output.issues = []
        mock_result.usage.return_value = MagicMock(input_tokens=0, output_tokens=0)
        mock_run_safe.return_value = mock_result

        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="test",
            system_prompt="prompt",
            user_message="msg",
            output_schema=get_schema("scored_issues"),
            tools=(),
            claudecode_builtin_names=("WebFetch",),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        await run_agent(ctx)

        mock_resolve.assert_called_once_with("test", extra_builtin_tools=("WebFetch",))
