"""SelectorAgent のテスト。

T021: pydantic-ai TestModel を使用し、SelectorOutput モデルと
run_selector の正常系・エラー系を検証する。
FR-RE-002 Step 5: セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。
"""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from claudecode_model import ClaudeCodeModel
from claudecode_model.exceptions import CLIExecutionError
from pydantic_ai.usage import UsageLimits

from hachimoku.agents.models import (
    AgentDefinition,
    ApplicabilityRule,
    Phase,
    SelectorDefinition,
)
from hachimoku.engine._selector import (
    ReferencedContent,
    SelectorDeps,
    SelectorError,
    SelectorOutput,
    _prefetch_guardrail,
    run_selector,
)

from hachimoku.engine._target import DiffTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import SelectorConfig

_PASSTHROUGH_RESOLVE = lambda m, **_kw: m  # noqa: E731
"""resolve_model のパススルーモック。keyword 引数（allowed_builtin_tools 等）を無視する。"""


def _make_agent(
    name: str = "test-agent",
    phase: Phase = Phase.MAIN,
) -> AgentDefinition:
    """テスト用 AgentDefinition を生成するヘルパー。"""
    return AgentDefinition(  # type: ignore[call-arg]
        name=name,
        description="Test agent for selection",
        model="test",
        output_schema="scored_issues",
        system_prompt="You are a test agent.",
        applicability=ApplicabilityRule(always=True),
        phase=phase,
    )


def _make_target() -> DiffTarget:
    """テスト用 DiffTarget を生成するヘルパー。"""
    return DiffTarget(base_branch="main")


def _make_selector_config(
    model: str | None = None,
    timeout: int | None = None,
    max_turns: int | None = None,
) -> SelectorConfig:
    """テスト用 SelectorConfig を生成するヘルパー。"""
    return SelectorConfig(
        model=model,
        timeout=timeout,
        max_turns=max_turns,
    )


def _make_selector_definition(
    model: str | None = "anthropic:claude-opus-4-6",
    system_prompt: str = "You are an agent selector.",
    allowed_tools: tuple[str, ...] = ("git_read", "gh_read", "file_read"),
) -> SelectorDefinition:
    """テスト用 SelectorDefinition を生成するヘルパー。"""
    return SelectorDefinition(
        name="selector",
        description="Agent selector",
        model=model,
        system_prompt=system_prompt,
        allowed_tools=allowed_tools,
    )


def _make_mock_agent_run(
    selected_agents: list[str] | None = None,
    reasoning: str = "Test reasoning",
) -> AsyncMock:
    """Agent.run の戻り値をモック化するヘルパー。"""
    if selected_agents is None:
        selected_agents = ["test-agent"]
    output = SelectorOutput(selected_agents=selected_agents, reasoning=reasoning)
    mock_result = MagicMock()
    mock_result.output = output
    return AsyncMock(return_value=mock_result)


def _make_mock_run_safe_result(
    selected_agents: list[str] | None = None,
    reasoning: str = "Test reasoning",
) -> MagicMock:
    """run_agent_safe の戻り値をモック化するヘルパー。

    run_agent_safe は AgentRunResult を返す。
    .output に SelectorOutput 相当のデータを持つ MagicMock を返す。
    """
    if selected_agents is None:
        selected_agents = ["test-agent"]
    output = SelectorOutput(selected_agents=selected_agents, reasoning=reasoning)
    mock_result = MagicMock()
    mock_result.output = output
    return mock_result


# =============================================================================
# SelectorOutput モデル — 正常系
# =============================================================================


class TestSelectorOutputValid:
    """SelectorOutput モデルの正常系テスト。"""

    def test_valid_construction(self) -> None:
        """正常なデータで構築できる。"""
        output = SelectorOutput(
            selected_agents=["agent-a", "agent-b"],
            reasoning="Both agents are applicable.",
        )
        assert output.selected_agents == ["agent-a", "agent-b"]
        assert output.reasoning == "Both agents are applicable."

    def test_inherits_base_model(self) -> None:
        """HachimokuBaseModel を継承している。"""
        assert issubclass(SelectorOutput, HachimokuBaseModel)

    def test_frozen(self) -> None:
        """frozen=True で不変である。"""
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
        )
        with pytest.raises(Exception):
            output.reasoning = "changed"  # type: ignore[misc]

    def test_extra_forbidden(self) -> None:
        """extra="forbid" で未知フィールドを拒否する。"""
        with pytest.raises(Exception):
            SelectorOutput(
                selected_agents=[],
                reasoning="test",
                unknown_field="bad",  # type: ignore[call-arg]
            )

    def test_empty_list_valid(self) -> None:
        """selected_agents が空リストでも有効。"""
        output = SelectorOutput(
            selected_agents=[],
            reasoning="No applicable agents found.",
        )
        assert output.selected_agents == []


# =============================================================================
# SelectorOutput モデル — メタデータフィールド（Issue #148）
# =============================================================================


class TestSelectorOutputMetadataFields:
    """SelectorOutput メタデータフィールドのテスト。

    Issue #148: セレクタ → レビューエージェントのメタデータ伝播。
    """

    def test_default_values_when_fields_omitted(self) -> None:
        """新フィールドが省略された場合、デフォルト値が適用される。"""
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
        )
        assert output.change_intent == ""
        assert output.affected_files == []
        assert output.relevant_conventions == []
        assert output.issue_context == ""

    def test_explicit_values_preserved(self) -> None:
        """明示的に渡した値が保持される。"""
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
            change_intent="Fix authentication bug",
            affected_files=["src/auth.py", "tests/test_auth.py"],
            relevant_conventions=["TDD strict", "Art.4 simplicity"],
            issue_context="Issue #42: Login fails for OAuth users",
        )
        assert output.change_intent == "Fix authentication bug"
        assert output.affected_files == ["src/auth.py", "tests/test_auth.py"]
        assert output.relevant_conventions == ["TDD strict", "Art.4 simplicity"]
        assert output.issue_context == "Issue #42: Login fails for OAuth users"

    def test_frozen_metadata_fields(self) -> None:
        """メタデータフィールドも frozen=True で不変。"""
        output = SelectorOutput(
            selected_agents=["a"],
            reasoning="r",
            change_intent="intent",
        )
        with pytest.raises(Exception):
            output.change_intent = "changed"  # type: ignore[misc]

    def test_partial_metadata(self) -> None:
        """一部のメタデータのみ設定できる。"""
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
            change_intent="Refactor engine",
            # affected_files, relevant_conventions, issue_context はデフォルト
        )
        assert output.change_intent == "Refactor engine"
        assert output.affected_files == []
        assert output.relevant_conventions == []
        assert output.issue_context == ""


# =============================================================================
# ReferencedContent モデル（Issue #159）
# =============================================================================


class TestReferencedContentModel:
    """ReferencedContent モデルのテスト。

    Issue #159: diff 内で参照されている外部リソースの取得結果。
    """

    def test_valid_construction(self) -> None:
        """正常なデータで構築できる。"""
        ref = ReferencedContent(
            reference_type="issue",
            reference_id="#152",
            content="Issue body text here",
        )
        assert ref.reference_type == "issue"
        assert ref.reference_id == "#152"
        assert ref.content == "Issue body text here"

    def test_inherits_base_model(self) -> None:
        """HachimokuBaseModel を継承している。"""
        assert issubclass(ReferencedContent, HachimokuBaseModel)

    def test_frozen(self) -> None:
        """frozen=True で不変である。"""
        ref = ReferencedContent(
            reference_type="file",
            reference_id="src/foo.py",
            content="file content",
        )
        with pytest.raises(Exception):
            ref.content = "changed"  # type: ignore[misc]

    def test_extra_forbidden(self) -> None:
        """extra="forbid" で未知フィールドを拒否する。"""
        with pytest.raises(ValidationError):
            ReferencedContent(
                reference_type="issue",
                reference_id="#1",
                content="text",
                unknown_field="bad",  # type: ignore[call-arg]
            )

    def test_empty_reference_type_rejected(self) -> None:
        """空文字列の reference_type は拒否される。"""
        with pytest.raises(ValidationError, match="reference_type"):
            ReferencedContent(
                reference_type="",
                reference_id="#1",
                content="text",
            )

    def test_empty_reference_id_rejected(self) -> None:
        """空文字列の reference_id は拒否される。"""
        with pytest.raises(ValidationError, match="reference_id"):
            ReferencedContent(
                reference_type="issue",
                reference_id="",
                content="text",
            )

    def test_empty_content_rejected(self) -> None:
        """空文字列の content は拒否される。"""
        with pytest.raises(ValidationError, match="content"):
            ReferencedContent(
                reference_type="issue",
                reference_id="#1",
                content="",
            )


# =============================================================================
# SelectorOutput — referenced_content フィールド（Issue #159）
# =============================================================================


class TestSelectorOutputReferencedContent:
    """SelectorOutput の referenced_content フィールドのテスト。

    Issue #159: セレクターメタデータによる参照先データ伝播。
    """

    def test_default_empty_list(self) -> None:
        """referenced_content 省略時は空リスト。"""
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
        )
        assert output.referenced_content == []

    def test_explicit_referenced_content_preserved(self) -> None:
        """明示的に渡した ReferencedContent リストが保持される。"""
        ref = ReferencedContent(
            reference_type="issue",
            reference_id="#152",
            content="Issue #152 body text",
        )
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
            referenced_content=[ref],
        )
        assert len(output.referenced_content) == 1
        assert output.referenced_content[0].reference_type == "issue"
        assert output.referenced_content[0].reference_id == "#152"
        assert output.referenced_content[0].content == "Issue #152 body text"

    def test_multiple_references(self) -> None:
        """複数の参照を持てる。"""
        refs = [
            ReferencedContent(
                reference_type="issue",
                reference_id="#152",
                content="Issue body",
            ),
            ReferencedContent(
                reference_type="file",
                reference_id="src/foo.py",
                content="def foo(): pass",
            ),
            ReferencedContent(
                reference_type="spec",
                reference_id="specs/005/spec.md",
                content="FR-RE-002: Pipeline spec",
            ),
        ]
        output = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="test",
            referenced_content=refs,
        )
        assert len(output.referenced_content) == 3

    def test_frozen_referenced_content(self) -> None:
        """referenced_content フィールドも frozen=True で不変。"""
        output = SelectorOutput(
            selected_agents=["a"],
            reasoning="r",
            referenced_content=[],
        )
        with pytest.raises(Exception):
            output.referenced_content = []  # type: ignore[misc]


# =============================================================================
# SelectorError 型
# =============================================================================


class TestSelectorError:
    """SelectorError 例外型のテスト。"""

    def test_is_exception(self) -> None:
        """Exception を継承している。"""
        assert issubclass(SelectorError, Exception)

    def test_message_preserved(self) -> None:
        """エラーメッセージが保持される。"""
        err = SelectorError("Selector failed: timeout")
        assert "timeout" in str(err)

    def test_default_fields_are_none(self) -> None:
        """引数なしで構築した場合、診断フィールドは全て None。"""
        err = SelectorError("simple error")
        assert err.exit_code is None
        assert err.error_type is None
        assert err.stderr is None
        assert err.recoverable is None

    def test_fields_preserved(self) -> None:
        """明示的に渡した診断フィールドが保持される。"""
        err = SelectorError(
            "CLI failed",
            exit_code=1,
            error_type="permission",
            stderr="Permission denied",
            recoverable=False,
        )
        assert err.exit_code == 1
        assert err.error_type == "permission"
        assert err.stderr == "Permission denied"
        assert err.recoverable is False
        assert "CLI failed" in str(err)


# =============================================================================
# run_selector — 正常系
# =============================================================================


class TestRunSelectorSuccess:
    """run_selector の正常系テスト。

    run_agent_safe() をモック化し、ツール実行を回避する。
    """

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_returns_selector_output(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """正常完了時に SelectorOutput が返される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result(["agent-a", "agent-b"])

        target = _make_target()
        agents: Sequence[AgentDefinition] = [
            _make_agent("agent-a"),
            _make_agent("agent-b"),
        ]
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )
        assert isinstance(result, SelectorOutput)
        assert result.selected_agents == ["agent-a", "agent-b"]

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_empty_selection_is_valid(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """空リスト返却が正常に完了する。"""
        mock_run_safe.return_value = _make_mock_run_safe_result([], "No match")

        target = _make_target()
        agents: Sequence[AgentDefinition] = []
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )
        assert isinstance(result, SelectorOutput)
        assert result.selected_agents == []

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_reasoning_preserved(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """reasoning が保持される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result(
            ["agent-a"], "Detailed reasoning here"
        )

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )
        assert result.reasoning == "Detailed reasoning here"

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_selector_config_model_override(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """SelectorConfig.model が指定されている場合、Agent に渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(model="custom-model")

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        # Agent コンストラクタに custom-model が渡されたことを確認
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "custom-model"

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_definition_model_used_when_config_none(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """SelectorConfig.model が None の場合、SelectorDefinition.model が使用される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(model=None)

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(model="definition-model"),
            selector_config=config,
            global_model="test-global-model",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "definition-model"


# =============================================================================
# run_selector — エラー系
# =============================================================================


class TestRunSelectorError:
    """run_selector のエラー系テスト。"""

    @pytest.mark.parametrize(
        ("exception", "match_pattern"),
        [
            (RuntimeError("LLM connection failed"), "LLM connection failed"),
            (
                CLIExecutionError(
                    "SDK query timed out",
                    exit_code=2,
                    stderr="Query was cancelled due to timeout",
                    error_type="timeout",
                ),
                "SDK query timed out",
            ),
        ],
    )
    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_exception_raises_selector_error(
        self,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        _: MagicMock,
        exception: Exception,
        match_pattern: str,
    ) -> None:
        """各種例外が SelectorError にラップされる。"""
        mock_run_safe.side_effect = exception

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        with pytest.raises(SelectorError, match=match_pattern):
            await run_selector(
                target=target,
                available_agents=agents,
                selector_definition=_make_selector_definition(),
                selector_config=config,
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
                resolved_content="test diff content",
            )


# =============================================================================
# run_selector — CLIExecutionError 診断情報伝播
# =============================================================================


class TestRunSelectorErrorDiagnostics:
    """run_selector が CLIExecutionError の構造化属性を SelectorError に伝播するテスト。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_cli_execution_error_attributes_propagated(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """CLIExecutionError の exit_code, error_type, stderr が SelectorError に伝播される。"""
        mock_run_safe.side_effect = CLIExecutionError(
            "CLI failed", exit_code=1, stderr="fatal error", error_type="timeout"
        )

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        with pytest.raises(SelectorError) as exc_info:
            await run_selector(
                target=target,
                available_agents=agents,
                selector_definition=_make_selector_definition(),
                selector_config=config,
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
                resolved_content="test diff content",
            )

        err = exc_info.value
        assert err.exit_code == 1
        assert err.error_type == "timeout"
        assert err.stderr == "fatal error"
        assert err.recoverable is False
        assert isinstance(err.__cause__, CLIExecutionError)

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_cli_execution_error_empty_stderr_preserved(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """CLIExecutionError の空 stderr は空文字列として保存される。"""
        mock_run_safe.side_effect = CLIExecutionError(
            "CLI failed", exit_code=1, stderr="", error_type="unknown"
        )

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        with pytest.raises(SelectorError) as exc_info:
            await run_selector(
                target=target,
                available_agents=agents,
                selector_definition=_make_selector_definition(),
                selector_config=config,
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
                resolved_content="test diff content",
            )

        assert exc_info.value.stderr == ""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_non_cli_error_fields_remain_none(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """CLIExecutionError 以外の例外では診断フィールドが None のまま。"""
        mock_run_safe.side_effect = RuntimeError("unexpected")

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        with pytest.raises(SelectorError) as exc_info:
            await run_selector(
                target=target,
                available_agents=agents,
                selector_definition=_make_selector_definition(),
                selector_config=config,
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
                resolved_content="test diff content",
            )

        err = exc_info.value
        assert err.exit_code is None
        assert err.error_type is None
        assert err.stderr is None
        assert err.recoverable is None


# =============================================================================
# run_selector — resolve_model 統合
# =============================================================================


class TestRunSelectorResolveModel:
    """run_selector が resolve_model を呼び出すテスト。"""

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_resolve_model_called(
        self,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        mock_resolve: MagicMock,
    ) -> None:
        """resolve_model が正しく呼ばれ、結果が Agent に渡される。"""
        mock_resolve.return_value = "resolved-model"
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        mock_resolve.assert_called_once_with(
            "anthropic:claude-opus-4-6",
            allowed_builtin_tools=(),
            extra_builtin_tools=(),
        )
        assert mock_agent_cls.call_args.kwargs["model"] == "resolved-model"

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_registers_toolsets_for_claudecode_model(
        self,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        mock_resolve: MagicMock,
    ) -> None:
        """ClaudeCodeModel の場合、set_agent_toolsets が呼ばれる。"""
        mock_model = MagicMock(spec=ClaudeCodeModel)
        mock_resolve.return_value = mock_model
        mock_run_safe.return_value = _make_mock_run_safe_result()
        mock_instance = mock_agent_cls.return_value

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        mock_model.set_agent_toolsets.assert_called_once_with(
            mock_instance._function_toolset
        )

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_skips_toolset_registration_for_string_model(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """文字列モデルの場合、set_agent_toolsets は呼ばれない。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )
        assert isinstance(result, SelectorOutput)


# =============================================================================
# run_selector — model_settings 統合
# =============================================================================


class TestRunSelectorModelSettings:
    """run_selector が run_agent_safe() に model_settings を渡すテスト。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_model_settings_max_turns_passed(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """run_agent_safe() に model_settings={"max_turns": N, "timeout": T} が渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"] == {"max_turns": 10, "timeout": 300}
        assert call_kwargs["usage_limits"] == UsageLimits(request_limit=10)

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_selector_config_max_turns_override(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """SelectorConfig.max_turns が model_settings に反映される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(max_turns=5)

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"] == {"max_turns": 5, "timeout": 300}

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_model_settings_timeout_passed(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """global_timeout が model_settings["timeout"] に渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=600,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"]["timeout"] == 600

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_selector_config_timeout_override(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """SelectorConfig.timeout が model_settings["timeout"] に反映される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(timeout=120)

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=_make_selector_definition(),
            selector_config=config,
            global_model="test",
            global_timeout=600,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_run_safe.call_args.kwargs
        assert call_kwargs["model_settings"]["timeout"] == 120


# =============================================================================
# run_selector — SelectorDefinition 統合
# =============================================================================


class TestRunSelectorDefinitionIntegration:
    """run_selector が SelectorDefinition を使用するテスト。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_system_prompt_from_definition(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """SelectorDefinition.system_prompt が Agent に渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()
        definition = _make_selector_definition(
            system_prompt="Custom system prompt for selector"
        )

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=definition,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_agent_cls.call_args
        assert (
            call_kwargs.kwargs["system_prompt"] == "Custom system prompt for selector"
        )

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_config_model_overrides_definition_model(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """SelectorConfig.model が SelectorDefinition.model より優先される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(model="config-model")
        definition = _make_selector_definition(model="definition-model")

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=definition,
            selector_config=config,
            global_model="global-model",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "config-model"

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_global_model_used_when_config_and_definition_none(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """config.model と definition.model が両方 None の場合、global_model が使用される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(model=None)
        definition = _make_selector_definition(model=None)

        await run_selector(
            target=target,
            available_agents=agents,
            selector_definition=definition,
            selector_config=config,
            global_model="global-model",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff content",
        )

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "global-model"


# =============================================================================
# Issue #187: prefetched_context 伝播テスト
# =============================================================================


class TestRunSelectorPrefetched:
    """run_selector の prefetched_context 伝播テスト。Issue #187。"""

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    @patch(
        "hachimoku.engine._selector.resolve_tools",
        return_value=MagicMock(tools=[], builtin_tools=[], claudecode_builtin_names=()),
    )
    async def test_prefetched_context_passed_to_instruction(
        self,
        _mock_tools: MagicMock,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        _mock_resolve: MagicMock,
    ) -> None:
        """prefetched_context が build_selector_instruction に渡される。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_run_safe.return_value = _make_mock_run_safe_result()
        agents = [_make_agent()]
        definition = _make_selector_definition()
        config = _make_selector_config()
        ctx = PrefetchedContext(issue_context="Prefetched issue body")

        with patch(
            "hachimoku.engine._selector.build_selector_instruction"
        ) as mock_build:
            mock_build.return_value = "test instruction"
            await run_selector(
                target=_make_target(),
                available_agents=agents,
                selector_definition=definition,
                selector_config=config,
                global_model="test-model",
                global_timeout=300,
                global_max_turns=10,
                resolved_content="diff content",
                prefetched_context=ctx,
            )

        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args
        assert call_kwargs.kwargs["prefetched_context"] is ctx

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    @patch(
        "hachimoku.engine._selector.resolve_tools",
        return_value=MagicMock(tools=[], builtin_tools=[], claudecode_builtin_names=()),
    )
    async def test_none_prefetched_backwards_compatible(
        self,
        _mock_tools: MagicMock,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        _mock_resolve: MagicMock,
    ) -> None:
        """prefetched_context=None でも正常に動作する（後方互換）。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()
        agents = [_make_agent()]
        definition = _make_selector_definition()
        config = _make_selector_config()

        result = await run_selector(
            target=_make_target(),
            available_agents=agents,
            selector_definition=definition,
            selector_config=config,
            global_model="test-model",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="diff content",
        )

        assert result.selected_agents == ["test-agent"]


# =============================================================================
# SelectorDeps（Issue #195）
# =============================================================================


class TestSelectorDeps:
    """SelectorDeps データクラスのテスト。Issue #195。"""

    def test_construction_with_prefetched(self) -> None:
        """PrefetchedContext を持つ SelectorDeps を構築できる。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        ctx = PrefetchedContext(issue_context="Issue body")
        deps = SelectorDeps(prefetched=ctx)
        assert deps.prefetched is ctx
        assert deps.prefetched.issue_context == "Issue body"

    def test_construction_with_none(self) -> None:
        """prefetched=None で SelectorDeps を構築できる。"""
        deps = SelectorDeps(prefetched=None)
        assert deps.prefetched is None


# =============================================================================
# _prefetch_guardrail（Issue #195）
# =============================================================================


class TestPrefetchGuardrail:
    """_prefetch_guardrail 関数のテスト。Issue #195。

    事前取得済みデータの存在に応じたガードレール指示の動的生成を検証する。
    """

    def test_none_prefetched_returns_empty(self) -> None:
        """prefetched=None のとき空文字列を返す。"""
        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(prefetched=None)
        assert _prefetch_guardrail(mock_ctx) == ""

    def test_empty_prefetched_returns_empty(self) -> None:
        """全フィールド空の PrefetchedContext のとき空文字列を返す。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(prefetched=PrefetchedContext())
        assert _prefetch_guardrail(mock_ctx) == ""

    def test_issue_context_guardrail(self) -> None:
        """issue_context が非空のとき Issue ガードレールを含む。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(
            prefetched=PrefetchedContext(issue_context="Issue body")
        )
        result = _prefetch_guardrail(mock_ctx)
        assert "Issue context" in result
        assert "Do NOT" in result
        assert "run_gh" in result

    def test_pr_metadata_guardrail(self) -> None:
        """pr_metadata が非空のとき PR ガードレールを含む。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(
            prefetched=PrefetchedContext(pr_metadata="PR #42 details")
        )
        result = _prefetch_guardrail(mock_ctx)
        assert "PR metadata" in result
        assert "Do NOT" in result
        assert "run_gh" in result

    def test_project_conventions_guardrail(self) -> None:
        """project_conventions が非空のとき conventions ガードレールを含む。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(
            prefetched=PrefetchedContext(project_conventions="--- CLAUDE.md ---\nrules")
        )
        result = _prefetch_guardrail(mock_ctx)
        assert "Project conventions" in result
        assert "Do NOT" in result

    def test_all_fields_produces_combined_guardrails(self) -> None:
        """全フィールド非空のとき全ガードレールを含む。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(
            prefetched=PrefetchedContext(
                issue_context="Issue body",
                pr_metadata="PR details",
                project_conventions="Conventions",
            )
        )
        result = _prefetch_guardrail(mock_ctx)
        assert "Issue context" in result
        assert "PR metadata" in result
        assert "Project conventions" in result

    def test_partial_fields_only_include_relevant(self) -> None:
        """一部のフィールドのみ非空のとき、該当するガードレールのみ含む。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_ctx = MagicMock()
        mock_ctx.deps = SelectorDeps(
            prefetched=PrefetchedContext(
                issue_context="Issue body",
                pr_metadata="",
                project_conventions="Conventions",
            )
        )
        result = _prefetch_guardrail(mock_ctx)
        assert "Issue context" in result
        assert "PR metadata" not in result
        assert "Project conventions" in result


# =============================================================================
# run_selector — SelectorDeps 統合（Issue #195）
# =============================================================================


class TestRunSelectorDepsIntegration:
    """run_selector が SelectorDeps と instructions を Agent に渡すテスト。Issue #195。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_agent_constructed_with_deps_type(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """Agent コンストラクタに deps_type=SelectorDeps が渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        await run_selector(
            target=_make_target(),
            available_agents=[_make_agent()],
            selector_definition=_make_selector_definition(),
            selector_config=_make_selector_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff",
        )

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["deps_type"] is SelectorDeps

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_agent_constructed_with_instructions(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """Agent コンストラクタに instructions=_prefetch_guardrail が渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        await run_selector(
            target=_make_target(),
            available_agents=[_make_agent()],
            selector_definition=_make_selector_definition(),
            selector_config=_make_selector_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff",
        )

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["instructions"] is _prefetch_guardrail

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_agent_run_receives_deps(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """run_agent_safe() に deps=SelectorDeps(prefetched=ctx) が渡される。"""
        from hachimoku.engine._prefetch import PrefetchedContext

        mock_run_safe.return_value = _make_mock_run_safe_result()

        ctx = PrefetchedContext(issue_context="Prefetched issue")
        await run_selector(
            target=_make_target(),
            available_agents=[_make_agent()],
            selector_definition=_make_selector_definition(),
            selector_config=_make_selector_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff",
            prefetched_context=ctx,
        )

        call_kwargs = mock_run_safe.call_args.kwargs
        deps = call_kwargs["deps"]
        assert isinstance(deps, SelectorDeps)
        assert deps.prefetched is ctx

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_agent_run_receives_none_deps_when_no_prefetch(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """prefetched_context=None のとき deps.prefetched=None が渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        await run_selector(
            target=_make_target(),
            available_agents=[_make_agent()],
            selector_definition=_make_selector_definition(),
            selector_config=_make_selector_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff",
        )

        call_kwargs = mock_run_safe.call_args.kwargs
        deps = call_kwargs["deps"]
        assert isinstance(deps, SelectorDeps)
        assert deps.prefetched is None


# =============================================================================
# run_selector — builtin_tools 統合（Issue #222）
# =============================================================================


class TestRunSelectorBuiltinTools:
    """run_selector が ResolvedTools を使用し builtin_tools を Agent に渡すテスト。Issue #222。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=_PASSTHROUGH_RESOLVE)
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_builtin_tools_passed_to_agent(
        self, mock_agent_cls: MagicMock, mock_run_safe: AsyncMock, _: MagicMock
    ) -> None:
        """resolve_tools の builtin_tools が Agent(builtin_tools=...) に渡される。"""
        mock_run_safe.return_value = _make_mock_run_safe_result()

        await run_selector(
            target=_make_target(),
            available_agents=[_make_agent()],
            selector_definition=_make_selector_definition(),
            selector_config=_make_selector_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff",
        )

        call_kwargs = mock_agent_cls.call_args.kwargs
        # デフォルトの allowed_tools には web_fetch を含まないため空リスト
        assert call_kwargs["builtin_tools"] == []

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.run_agent_safe")
    @patch("hachimoku.engine._selector.Agent")
    async def test_extra_builtin_tools_passed_to_resolve_model(
        self,
        mock_agent_cls: MagicMock,
        mock_run_safe: AsyncMock,
        mock_resolve: MagicMock,
    ) -> None:
        """claudecode_builtin_names が resolve_model の extra_builtin_tools に渡される。"""
        mock_resolve.return_value = "resolved-model"
        mock_run_safe.return_value = _make_mock_run_safe_result()

        await run_selector(
            target=_make_target(),
            available_agents=[_make_agent()],
            selector_definition=_make_selector_definition(),
            selector_config=_make_selector_config(),
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            resolved_content="test diff",
        )

        # デフォルトの allowed_tools=(git_read, gh_read, file_read) では
        # claudecode_builtin_names=() なので extra_builtin_tools=() が渡される
        mock_resolve.assert_called_once_with(
            "anthropic:claude-opus-4-6",
            allowed_builtin_tools=(),
            extra_builtin_tools=(),
        )
