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

from claudecode_model import ClaudeCodeModel

from hachimoku.agents.models import AgentDefinition, ApplicabilityRule, Phase
from hachimoku.engine._selector import SelectorError, SelectorOutput, run_selector
from hachimoku.engine._target import DiffTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import Provider, SelectorConfig
from hachimoku.models.tool_category import ToolCategory


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
        allowed_tools=[
            ToolCategory.GIT_READ,
            ToolCategory.GH_READ,
            ToolCategory.FILE_READ,
        ],
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


# =============================================================================
# run_selector — 正常系
# =============================================================================


class TestRunSelectorSuccess:
    """run_selector の正常系テスト。

    Agent.run() をモック化し、ツール実行を回避する。
    """

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_returns_selector_output(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """正常完了時に SelectorOutput が返される。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run(["agent-a", "agent-b"])
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [
            _make_agent("agent-a"),
            _make_agent("agent-b"),
        ]
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )
        assert isinstance(result, SelectorOutput)
        assert result.selected_agents == ["agent-a", "agent-b"]

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_empty_selection_is_valid(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """空リスト返却が正常に完了する。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run([], "No match")
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = []
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )
        assert isinstance(result, SelectorOutput)
        assert result.selected_agents == []

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_reasoning_preserved(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """reasoning が保持される。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run(["agent-a"], "Detailed reasoning here")
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )
        assert result.reasoning == "Detailed reasoning here"

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_selector_config_model_override(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """SelectorConfig.model が指定されている場合、Agent に渡される。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(model="custom-model")

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        # Agent コンストラクタに custom-model が渡されたことを確認
        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "custom-model"

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_global_model_used_when_config_none(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """SelectorConfig.model が None の場合、global_model が使用される。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(model=None)

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test-global-model",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        call_kwargs = mock_agent_cls.call_args
        assert call_kwargs.kwargs["model"] == "test-global-model"


# =============================================================================
# run_selector — エラー系
# =============================================================================


class TestRunSelectorError:
    """run_selector のエラー系テスト。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_agent_exception_raises_selector_error(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """Agent.run() の例外が SelectorError にラップされる。"""
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(side_effect=RuntimeError("LLM connection failed"))
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        with pytest.raises(SelectorError, match="LLM connection failed"):
            await run_selector(
                target=target,
                available_agents=agents,
                selector_config=config,
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
                global_provider=Provider.CLAUDECODE,
            )

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_timeout_raises_selector_error(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """TimeoutError が SelectorError にラップされる。"""
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(side_effect=TimeoutError("timed out"))
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        with pytest.raises(SelectorError):
            await run_selector(
                target=target,
                available_agents=agents,
                selector_config=config,
                global_model="test",
                global_timeout=300,
                global_max_turns=10,
                global_provider=Provider.CLAUDECODE,
            )


# =============================================================================
# run_selector — resolve_model 統合
# =============================================================================


class TestRunSelectorResolveModel:
    """run_selector が resolve_model を呼び出すテスト。"""

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.Agent")
    async def test_resolve_model_called(
        self, mock_agent_cls: MagicMock, mock_resolve: MagicMock
    ) -> None:
        """resolve_model が正しく呼ばれ、結果が Agent に渡される。"""
        mock_resolve.return_value = "resolved-model"
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        mock_resolve.assert_called_once_with("test", Provider.CLAUDECODE)
        assert mock_agent_cls.call_args.kwargs["model"] == "resolved-model"

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.Agent")
    async def test_selector_config_provider_override(
        self, mock_agent_cls: MagicMock, mock_resolve: MagicMock
    ) -> None:
        """SelectorConfig.provider が global_provider を上書きする。"""
        mock_resolve.return_value = "resolved-model"
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = SelectorConfig(
            provider="anthropic",  # type: ignore[arg-type]
            allowed_tools=["git_read", "gh_read", "file_read"],  # type: ignore[list-item]
        )

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        mock_resolve.assert_called_once_with("test", Provider.ANTHROPIC)

    @patch("hachimoku.engine._selector.resolve_model")
    @patch("hachimoku.engine._selector.Agent")
    async def test_registers_toolsets_for_claudecode_model(
        self, mock_agent_cls: MagicMock, mock_resolve: MagicMock
    ) -> None:
        """ClaudeCodeModel の場合、set_agent_toolsets が呼ばれる。"""
        mock_model = MagicMock(spec=ClaudeCodeModel)
        mock_resolve.return_value = mock_model
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        mock_model.set_agent_toolsets.assert_called_once_with(
            mock_instance._function_toolset
        )

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_skips_toolset_registration_for_string_model(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """文字列モデルの場合、set_agent_toolsets は呼ばれない。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        result = await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )
        assert isinstance(result, SelectorOutput)


# =============================================================================
# run_selector — model_settings 統合
# =============================================================================


class TestRunSelectorModelSettings:
    """run_selector が agent.run() に model_settings を渡すテスト。"""

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_model_settings_max_turns_passed(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """agent.run() に model_settings={"max_turns": N} が渡される。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config()

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        call_kwargs = mock_instance.run.call_args.kwargs
        assert call_kwargs["model_settings"] == {"max_turns": 10}

    @patch("hachimoku.engine._selector.resolve_model", side_effect=lambda m, p: m)
    @patch("hachimoku.engine._selector.Agent")
    async def test_selector_config_max_turns_override(
        self, mock_agent_cls: MagicMock, _: MagicMock
    ) -> None:
        """SelectorConfig.max_turns が model_settings に反映される。"""
        mock_instance = MagicMock()
        mock_instance.run = _make_mock_agent_run()
        mock_agent_cls.return_value = mock_instance

        target = _make_target()
        agents: Sequence[AgentDefinition] = [_make_agent()]
        config = _make_selector_config(max_turns=5)

        await run_selector(
            target=target,
            available_agents=agents,
            selector_config=config,
            global_model="test",
            global_timeout=300,
            global_max_turns=10,
            global_provider=Provider.CLAUDECODE,
        )

        call_kwargs = mock_instance.run.call_args.kwargs
        assert call_kwargs["model_settings"] == {"max_turns": 5}
