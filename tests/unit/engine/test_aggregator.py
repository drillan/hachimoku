"""AggregatedReport モデルと run_aggregator のテスト。

FR-RE-018: AggregatedReport 構造。
Issue #152: LLM ベース結果集約。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claudecode_model.exceptions import CLIExecutionError
from pydantic import ValidationError

from hachimoku.agents.models import AggregatorDefinition
from hachimoku.engine._aggregator import AggregatorError, run_aggregator
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)
from hachimoku.models.config import AggregationConfig
from hachimoku.models.report import AggregatedReport, Priority, RecommendedAction
from hachimoku.models.review import FileLocation, ReviewIssue
from hachimoku.models.severity import Severity


# =============================================================================
# AggregatedReport — 正常系
# =============================================================================


class TestAggregatedReportValid:
    """AggregatedReport の正常系を検証。"""

    def test_valid_full(self) -> None:
        """全フィールド指定でインスタンス生成が成功する。"""
        issue = ReviewIssue(
            agent_name="security-reviewer",
            severity=Severity.CRITICAL,
            description="SQL injection found",
            location=FileLocation(file_path="app.py", line_number=42),
        )
        action = RecommendedAction(
            description="Fix SQL injection",
            priority=Priority.HIGH,
        )
        report = AggregatedReport(
            issues=[issue],
            strengths=["Good test coverage"],
            recommended_actions=[action],
            agent_failures=["timeout-agent"],
        )
        assert len(report.issues) == 1
        assert report.issues[0].description == "SQL injection found"
        assert len(report.strengths) == 1
        assert len(report.recommended_actions) == 1
        assert report.agent_failures == ["timeout-agent"]

    def test_empty_lists_accepted(self) -> None:
        """全リストが空でもインスタンス生成が成功する。"""
        report = AggregatedReport(
            issues=[],
            strengths=[],
            recommended_actions=[],
            agent_failures=[],
        )
        assert report.issues == []
        assert report.strengths == []
        assert report.recommended_actions == []
        assert report.agent_failures == []

    def test_multiple_issues(self) -> None:
        """複数の ReviewIssue を保持できる。"""
        issues = [
            ReviewIssue(
                agent_name="reviewer-a",
                severity=Severity.CRITICAL,
                description="Issue 1",
            ),
            ReviewIssue(
                agent_name="reviewer-b",
                severity=Severity.SUGGESTION,
                description="Issue 2",
            ),
        ]
        report = AggregatedReport(
            issues=issues,
            strengths=[],
            recommended_actions=[],
            agent_failures=[],
        )
        assert len(report.issues) == 2

    def test_multiple_strengths(self) -> None:
        """複数の strengths を保持できる。"""
        report = AggregatedReport(
            issues=[],
            strengths=["Good naming", "Clean architecture", "Well tested"],
            recommended_actions=[],
            agent_failures=[],
        )
        assert len(report.strengths) == 3

    def test_multiple_recommended_actions(self) -> None:
        """複数の RecommendedAction を保持できる。"""
        actions = [
            RecommendedAction(description="Fix critical", priority=Priority.HIGH),
            RecommendedAction(description="Improve docs", priority=Priority.LOW),
        ]
        report = AggregatedReport(
            issues=[],
            strengths=[],
            recommended_actions=actions,
            agent_failures=[],
        )
        assert len(report.recommended_actions) == 2

    def test_multiple_agent_failures(self) -> None:
        """複数の失敗エージェント名を保持できる。"""
        report = AggregatedReport(
            issues=[],
            strengths=[],
            recommended_actions=[],
            agent_failures=["agent-a", "agent-b"],
        )
        assert len(report.agent_failures) == 2


# =============================================================================
# AggregatedReport — 制約違反
# =============================================================================


class TestAggregatedReportConstraints:
    """AggregatedReport の制約違反を検証。"""

    def test_missing_issues_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AggregatedReport(  # type: ignore[call-arg]
                strengths=[],
                recommended_actions=[],
                agent_failures=[],
            )

    def test_missing_strengths_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AggregatedReport(  # type: ignore[call-arg]
                issues=[],
                recommended_actions=[],
                agent_failures=[],
            )

    def test_missing_recommended_actions_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AggregatedReport(  # type: ignore[call-arg]
                issues=[],
                strengths=[],
                agent_failures=[],
            )

    def test_missing_agent_failures_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AggregatedReport(  # type: ignore[call-arg]
                issues=[],
                strengths=[],
                recommended_actions=[],
            )

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AggregatedReport(
                issues=[],
                strengths=[],
                recommended_actions=[],
                agent_failures=[],
                summary="extra",  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        """frozen=True のためフィールド変更が拒否される。"""
        report = AggregatedReport(
            issues=[],
            strengths=[],
            recommended_actions=[],
            agent_failures=[],
        )
        with pytest.raises(ValidationError):
            report.strengths = ["new"]  # type: ignore[misc]


# =============================================================================
# ヘルパー関数
# =============================================================================


def _make_aggregator_definition(
    model: str | None = "anthropic:claude-opus-4-6",
    system_prompt: str = "You are a review aggregator.",
) -> AggregatorDefinition:
    """テスト用 AggregatorDefinition を生成するヘルパー。"""
    return AggregatorDefinition(
        name="aggregator",
        description="Review aggregator",
        model=model,
        system_prompt=system_prompt,
    )


def _make_aggregation_config(
    model: str | None = None,
    timeout: int | None = None,
    max_turns: int | None = None,
) -> AggregationConfig:
    """テスト用 AggregationConfig を生成するヘルパー。"""
    return AggregationConfig(
        model=model,
        timeout=timeout,
        max_turns=max_turns,
    )


def _make_mock_run_safe_result(
    issues: list[ReviewIssue] | None = None,
    strengths: list[str] | None = None,
    recommended_actions: list[RecommendedAction] | None = None,
    agent_failures: list[str] | None = None,
) -> MagicMock:
    """run_agent_safe() の戻り値をモック化するヘルパー。"""
    output = AggregatedReport(
        issues=issues or [],
        strengths=strengths or ["Good code"],
        recommended_actions=recommended_actions or [],
        agent_failures=agent_failures or [],
    )
    mock_result = MagicMock()
    mock_result.output = output
    return mock_result


# =============================================================================
# AggregatorError 型
# =============================================================================


class TestAggregatorError:
    """AggregatorError 例外型のテスト。"""

    def test_is_exception(self) -> None:
        """Exception を継承している。"""
        assert issubclass(AggregatorError, Exception)

    def test_message_preserved(self) -> None:
        """エラーメッセージが保持される。"""
        err = AggregatorError("Aggregator failed: timeout")
        assert "timeout" in str(err)


# =============================================================================
# run_aggregator — 正常系
# =============================================================================


class TestRunAggregatorSuccess:
    """run_aggregator の正常系テスト。

    run_agent_safe() をモック化し、LLM 呼び出しを回避する。
    """

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_returns_aggregated_report(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """正常完了時に AggregatedReport が返される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result(
            strengths=["Clean code"]
        )

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        result = await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        assert isinstance(result, AggregatedReport)
        assert result.strengths == ["Clean code"]

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_filters_success_and_truncated(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """AgentSuccess と AgentTruncated のみをフィルタして集約する。"""
        mock_run_safe.return_value = _make_mock_run_safe_result(
            agent_failures=["reviewer-c", "reviewer-d"]
        )

        mixed_results: list[
            AgentSuccess | AgentTruncated | AgentError | AgentTimeout
        ] = [
            AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0),
            AgentTruncated(
                agent_name="reviewer-b",
                issues=[],
                elapsed_time=2.0,
                turns_consumed=10,
            ),
            AgentError(agent_name="reviewer-c", error_message="fail"),
            AgentTimeout(agent_name="reviewer-d", timeout_seconds=30.0),
        ]
        result = await run_aggregator(
            results=mixed_results,
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        assert isinstance(result, AggregatedReport)

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_system_prompt_from_definition(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """AggregatorDefinition.system_prompt が Agent に渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(
                system_prompt="Custom aggregator prompt"
            ),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["system_prompt"] == "Custom aggregator prompt"

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_no_tools_passed_to_agent(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """Agent にツールが渡されない（空リスト）。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs.get("tools", []) == []

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_output_type_is_aggregated_report(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """Agent の output_type が AggregatedReport である。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["output_type"] is AggregatedReport


# =============================================================================
# run_aggregator — 3層モデル解決
# =============================================================================


class TestRunAggregatorModelResolution:
    """run_aggregator のモデル解決テスト。"""

    @pytest.mark.parametrize(
        ("config_model", "definition_model", "expected_model"),
        [
            ("config-model", "definition-model", "config-model"),
            (None, "definition-model", "definition-model"),
            (None, None, "global-model"),
        ],
    )
    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_model_resolution_priority(
        self,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        _: MagicMock,
        config_model: str | None,
        definition_model: str | None,
        expected_model: str,
    ) -> None:
        """モデル解決の優先順: config > definition > global。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(model=definition_model),
            aggregation_config=_make_aggregation_config(model=config_model),
            global_model="global-model",
            global_timeout=300,
            global_max_turns=10,
        )
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == expected_model


# =============================================================================
# run_aggregator — timeout/max_turns 解決
# =============================================================================


class TestRunAggregatorTimeoutResolution:
    """run_aggregator の timeout/max_turns 解決テスト。"""

    @pytest.mark.parametrize(
        ("config_timeout", "config_max_turns", "assert_field", "expected_value"),
        [
            (120, None, "timeout", 120),
            (None, 5, "max_turns", 5),
        ],
    )
    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_config_overrides_global(
        self,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        _: MagicMock,
        config_timeout: int | None,
        config_max_turns: int | None,
        assert_field: str,
        expected_value: int,
    ) -> None:
        """AggregationConfig の timeout/max_turns がグローバル値より優先される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(
                timeout=config_timeout, max_turns=config_max_turns
            ),
            global_model="test",
            global_timeout=600,
            global_max_turns=10,
        )
        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"][assert_field] == expected_value

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_global_values_used_when_config_none(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """AggregationConfig の timeout/max_turns が None の場合、グローバル値が使用される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"]["timeout"] == 300
        assert call_kwargs["model_settings"]["max_turns"] == 10


# =============================================================================
# run_aggregator — エラー系
# =============================================================================


class TestRunAggregatorError:
    """run_aggregator のエラー系テスト。"""

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_agent_exception_raises_aggregator_error(
        self, _agent: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """run_agent_safe() の例外が AggregatorError にラップされる。"""
        mock_run_safe.side_effect = RuntimeError("LLM connection failed")

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        with pytest.raises(AggregatorError, match="LLM connection failed"):
            await run_aggregator(
                results=[success],
                aggregator_definition=_make_aggregator_definition(),
                aggregation_config=_make_aggregation_config(),
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
            )

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_timeout_raises_aggregator_error(
        self, _agent: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """CLIExecutionError(error_type="timeout") が AggregatorError にラップされる。"""
        mock_run_safe.side_effect = CLIExecutionError(
            "SDK query timed out",
            exit_code=2,
            stderr="Query was cancelled due to timeout",
            error_type="timeout",
        )

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        with pytest.raises(AggregatorError):
            await run_aggregator(
                results=[success],
                aggregator_definition=_make_aggregator_definition(),
                aggregation_config=_make_aggregation_config(),
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
            )

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_original_exception_chained(
        self, _agent: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """AggregatorError.__cause__ に元の例外がチェインされる。"""
        original = RuntimeError("original error")
        mock_run_safe.side_effect = original

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        with pytest.raises(AggregatorError) as exc_info:
            await run_aggregator(
                results=[success],
                aggregator_definition=_make_aggregator_definition(),
                aggregation_config=_make_aggregation_config(),
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
            )
        assert exc_info.value.__cause__ is original


# =============================================================================
# run_aggregator — ユーザーメッセージ構築
# =============================================================================


class TestRunAggregatorUserMessage:
    """run_aggregator がエージェント結果からユーザーメッセージを構築するテスト。"""

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_user_message_contains_issues(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """ユーザーメッセージに issues の情報が含まれる。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        issue = ReviewIssue(
            agent_name="reviewer-a",
            severity=Severity.CRITICAL,
            description="SQL injection vulnerability",
        )
        success = AgentSuccess(
            agent_name="reviewer-a", issues=[issue], elapsed_time=1.0
        )
        await run_aggregator(
            results=[success],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        user_message = mock_run_safe.call_args.kwargs["user_prompt"]
        assert "SQL injection vulnerability" in user_message
        assert "reviewer-a" in user_message

    @patch("hachimoku.engine._aggregator.resolve_model", side_effect=lambda m: m)
    @patch("hachimoku.engine._aggregator.run_agent_safe")
    @patch("hachimoku.engine._aggregator.Agent")
    async def test_user_message_contains_failed_agents(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """ユーザーメッセージに失敗エージェント情報が含まれる。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        success = AgentSuccess(agent_name="reviewer-a", issues=[], elapsed_time=1.0)
        error = AgentError(agent_name="reviewer-b", error_message="fail")
        await run_aggregator(
            results=[success, error],
            aggregator_definition=_make_aggregator_definition(),
            aggregation_config=_make_aggregation_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
        )
        user_message = mock_run_safe.call_args.kwargs["user_prompt"]
        assert "reviewer-b" in user_message
