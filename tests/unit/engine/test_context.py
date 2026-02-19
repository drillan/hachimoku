"""AgentExecutionContext のテスト。

FR-RE-007: エージェント定義・設定・レビュー対象から実行コンテキストを構築。
FR-RE-004: タイムアウト・ターン数の優先順解決。
"""

import pytest
from pydantic import ValidationError
from pydantic_ai import Tool

from hachimoku.agents.models import AgentDefinition, ApplicabilityRule, Phase
from hachimoku.engine._context import (
    AgentExecutionContext,
    _resolve_with_agent_def,
    build_execution_context,
)
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import AgentConfig, HachimokuConfig
from hachimoku.models.schemas._base import BaseAgentOutput


def _make_agent(
    name: str = "test-agent",
    phase: Phase = Phase.MAIN,
    max_turns: int | None = None,
    timeout: int | None = None,
    model: str = "test-model",
) -> AgentDefinition:
    """テスト用 AgentDefinition を生成するヘルパー。"""
    return AgentDefinition(  # type: ignore[call-arg]
        name=name,
        description="Test agent",
        model=model,
        output_schema="scored_issues",
        system_prompt="You are a test agent.",
        applicability=ApplicabilityRule(always=True),
        phase=phase,
        max_turns=max_turns,
        timeout=timeout,
    )


def _make_tool() -> Tool[None]:
    """テスト用スタブツールを生成するヘルパー。"""
    return Tool(lambda: "stub", takes_ctx=False)


# =============================================================================
# AgentExecutionContext モデル — 正常系
# =============================================================================


class TestAgentExecutionContextValid:
    """AgentExecutionContext モデルの正常系テスト。"""

    def test_construct_with_all_fields(self) -> None:
        """全フィールド指定でインスタンス生成が成功する。"""
        agent = _make_agent()
        tool = _make_tool()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="You are a test agent.",
            user_message="Review this code.",
            output_schema=agent.resolved_schema,
            tools=(tool,),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert ctx.agent_name == "test-agent"
        assert ctx.model == "sonnet"
        assert ctx.system_prompt == "You are a test agent."
        assert ctx.user_message == "Review this code."
        assert ctx.timeout_seconds == 300
        assert ctx.max_turns == 10
        assert ctx.phase == Phase.MAIN

    def test_inherits_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert isinstance(ctx, HachimokuBaseModel)

    def test_frozen(self) -> None:
        """frozen=True でフィールド変更不可。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        with pytest.raises(ValidationError):
            ctx.model = "haiku"  # type: ignore[misc]

    def test_empty_tools_tuple_accepted(self) -> None:
        """tools=() の空タプルが受け入れられる。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert ctx.tools == ()

    def test_output_schema_stores_class_reference(self) -> None:
        """output_schema が BaseAgentOutput のサブクラスを保持する。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert issubclass(ctx.output_schema, BaseAgentOutput)


# =============================================================================
# AgentExecutionContext モデル — 制約違反
# =============================================================================


class TestAgentExecutionContextConstraints:
    """AgentExecutionContext モデルの制約違反テスト。"""

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドで ValidationError を送出する。"""
        agent = _make_agent()
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AgentExecutionContext(
                agent_name="test-agent",
                model="sonnet",
                system_prompt="prompt",
                user_message="message",
                output_schema=agent.resolved_schema,
                tools=(),
                timeout_seconds=300,
                max_turns=10,
                phase=Phase.MAIN,
                unknown_field="value",  # type: ignore[call-arg]
            )

    def test_arbitrary_types_allowed_for_tool(self) -> None:
        """Tool オブジェクトが arbitrary_types_allowed により受け入れられる。"""
        agent = _make_agent()
        tool = _make_tool()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(tool,),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert len(ctx.tools) == 1

    def test_zero_timeout_rejected(self) -> None:
        """timeout_seconds=0 で ValidationError を送出する。"""
        agent = _make_agent()
        with pytest.raises(ValidationError, match="timeout_seconds"):
            AgentExecutionContext(
                agent_name="test-agent",
                model="sonnet",
                system_prompt="prompt",
                user_message="message",
                output_schema=agent.resolved_schema,
                tools=(),
                timeout_seconds=0,
                max_turns=10,
                phase=Phase.MAIN,
            )

    def test_negative_timeout_rejected(self) -> None:
        """timeout_seconds=-1 で ValidationError を送出する。"""
        agent = _make_agent()
        with pytest.raises(ValidationError, match="timeout_seconds"):
            AgentExecutionContext(
                agent_name="test-agent",
                model="sonnet",
                system_prompt="prompt",
                user_message="message",
                output_schema=agent.resolved_schema,
                tools=(),
                timeout_seconds=-1,
                max_turns=10,
                phase=Phase.MAIN,
            )

    def test_zero_max_turns_rejected(self) -> None:
        """max_turns=0 で ValidationError を送出する。"""
        agent = _make_agent()
        with pytest.raises(ValidationError, match="max_turns"):
            AgentExecutionContext(
                agent_name="test-agent",
                model="sonnet",
                system_prompt="prompt",
                user_message="message",
                output_schema=agent.resolved_schema,
                tools=(),
                timeout_seconds=300,
                max_turns=0,
                phase=Phase.MAIN,
            )

    def test_non_tool_element_in_tools_rejected(self) -> None:
        """tools タプルに Tool 以外の要素を含む場合 ValueError を送出する。"""
        agent = _make_agent()
        with pytest.raises(ValueError, match="Tool"):
            AgentExecutionContext(
                agent_name="test-agent",
                model="sonnet",
                system_prompt="prompt",
                user_message="message",
                output_schema=agent.resolved_schema,
                tools=("not-a-tool",),  # type: ignore[arg-type]
                timeout_seconds=300,
                max_turns=10,
                phase=Phase.MAIN,
            )

    def test_multiple_tools_accepted(self) -> None:
        """複数 Tool 要素のタプルが受け入れられる。"""
        agent = _make_agent()
        tool1 = _make_tool()
        tool2 = _make_tool()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(tool1, tool2),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert len(ctx.tools) == 2


# =============================================================================
# _resolve_with_agent_def — 直接テスト
# =============================================================================


class TestResolveWithAgentDef:
    """_resolve_with_agent_def の3層/2層解決を直接検証。"""

    # --- str 型: 3層解決 ---

    def test_str_agent_config_wins(self) -> None:
        """str 型: agent_config 値が最優先。"""
        result = _resolve_with_agent_def("config-model", "def-model", "global-model")
        assert result == "config-model"

    def test_str_agent_def_wins_when_config_none(self) -> None:
        """str 型: agent_config=None の場合、agent_def が使用される。"""
        result = _resolve_with_agent_def(None, "def-model", "global-model")
        assert result == "def-model"

    def test_str_global_wins_when_both_none(self) -> None:
        """str 型: agent_config=None かつ agent_def=None の場合、global が使用される。"""
        result = _resolve_with_agent_def(None, None, "global-model")
        assert result == "global-model"

    # --- str 型: 2層解決 (agent_def_value=None) ---

    def test_str_two_layer_config_wins(self) -> None:
        """str 型 2層: agent_config 値が最優先。"""
        result = _resolve_with_agent_def("config-model", None, "global-model")
        assert result == "config-model"

    def test_str_two_layer_global_wins(self) -> None:
        """str 型 2層: agent_config=None の場合、global が使用される。"""
        result = _resolve_with_agent_def(None, None, "global-model")
        assert result == "global-model"

    # --- int 型: 3層解決 ---

    def test_int_agent_config_wins(self) -> None:
        """int 型: agent_config 値が最優先。"""
        result = _resolve_with_agent_def(60, 300, 600)
        assert result == 60

    def test_int_agent_def_wins_when_config_none(self) -> None:
        """int 型: agent_config=None の場合、agent_def が使用される。"""
        result = _resolve_with_agent_def(None, 300, 600)
        assert result == 300

    def test_int_global_wins_when_both_none(self) -> None:
        """int 型: agent_config=None かつ agent_def=None の場合、global が使用される。"""
        result = _resolve_with_agent_def(None, None, 600)
        assert result == 600

    # --- int 型: 2層解決 (agent_def_value=None) ---

    def test_int_two_layer_config_wins(self) -> None:
        """int 型 2層: agent_config 値が最優先。"""
        result = _resolve_with_agent_def(60, None, 600)
        assert result == 60

    def test_int_two_layer_global_wins(self) -> None:
        """int 型 2層: agent_config=None の場合、global が使用される。"""
        result = _resolve_with_agent_def(None, None, 600)
        assert result == 600


# =============================================================================
# build_execution_context — 基本動作
# =============================================================================


class TestBuildExecutionContextBasic:
    """build_execution_context の基本的なフィールドマッピングを検証。"""

    def test_agent_name_from_agent_def(self) -> None:
        """agent_name が agent_def.name から設定される。"""
        agent = _make_agent(name="my-agent")
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="Review this.",
            resolved_tools=(),
        )
        assert ctx.agent_name == "my-agent"

    def test_system_prompt_from_agent_def(self) -> None:
        """system_prompt が agent_def.system_prompt から設定される。"""
        agent = _make_agent()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="Review this.",
            resolved_tools=(),
        )
        assert ctx.system_prompt == "You are a test agent."

    def test_user_message_passthrough(self) -> None:
        """user_message がそのまま設定される。"""
        agent = _make_agent()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="Custom review instruction.",
            resolved_tools=(),
        )
        assert ctx.user_message == "Custom review instruction."

    def test_output_schema_from_agent_def(self) -> None:
        """output_schema が agent_def.resolved_schema から設定される。"""
        agent = _make_agent()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="Review this.",
            resolved_tools=(),
        )
        assert ctx.output_schema is agent.resolved_schema

    def test_tools_passthrough(self) -> None:
        """tools がそのまま設定される。"""
        agent = _make_agent()
        tool = _make_tool()
        tools = (tool,)
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="Review this.",
            resolved_tools=tools,
        )
        assert ctx.tools is tools

    def test_phase_from_agent_def(self) -> None:
        """phase が agent_def.phase から設定される。"""
        agent = _make_agent(phase=Phase.EARLY)
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="Review this.",
            resolved_tools=(),
        )
        assert ctx.phase == Phase.EARLY


# =============================================================================
# build_execution_context — model 優先順解決
# =============================================================================


_NO_AGENT_CONFIG = "NO_AGENT_CONFIG"


class TestBuildExecutionContextModelResolution:
    """model フィールドの3段階優先順解決を検証（FR-RE-007, Issue #217）。

    優先順: agent_config > agent_def > global_config。
    """

    @pytest.mark.parametrize(
        ("agent_def_model", "global_model", "agent_cfg_model", "expected"),
        [
            # agent_config なし → agent_def が使用される
            ("def-model", "global-model", _NO_AGENT_CONFIG, "def-model"),
            # agent_def が global を上書き（agent_config なし）
            (
                "anthropic:claude-opus-4-6",
                "global-model",
                _NO_AGENT_CONFIG,
                "anthropic:claude-opus-4-6",
            ),
            # agent_config=None の場合、agent_def が使用される
            ("def-model", "global-model", None, "def-model"),
            # agent_config が agent_def と global を上書き
            ("def-model", "global-model", "config-model", "config-model"),
            # agent_def が global と同じ場合、agent_config が上書き
            ("global-model", "global-model", "config-model", "config-model"),
        ],
    )
    def test_model_priority_resolution(
        self,
        agent_def_model: str,
        global_model: str,
        agent_cfg_model: str | None,
        expected: str,
    ) -> None:
        """model の優先順を検証: agent_config > agent_def > global_config。"""
        agent = _make_agent(model=agent_def_model)
        config = HachimokuConfig(model=global_model)
        agent_cfg = (
            None
            if agent_cfg_model == _NO_AGENT_CONFIG
            else AgentConfig(model=agent_cfg_model)
        )
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=agent_cfg,
            global_config=config,
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.model == expected

    def test_model_from_global_when_no_agent_config_and_no_agent_def_override(
        self,
    ) -> None:
        """agent_config=None かつ agent_def.model と global が同じ場合、global 値が使用される。"""
        agent = _make_agent(model="global-model")
        config = HachimokuConfig(model="global-model")
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=config,
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.model == "global-model"


# =============================================================================
# build_execution_context — timeout 優先順解決
# =============================================================================


class TestBuildExecutionContextTimeoutResolution:
    """timeout_seconds フィールドの優先順解決を検証（FR-RE-004）。"""

    @pytest.mark.parametrize(
        ("agent_def_timeout", "global_timeout", "agent_cfg_timeout", "expected"),
        [
            (None, 600, _NO_AGENT_CONFIG, 600),  # global when no agent_config
            (None, 600, None, 600),  # global when agent timeout is None
            (None, 600, 60, 60),  # agent_config overrides global
            (900, 600, _NO_AGENT_CONFIG, 900),  # agent_def when no agent_config
            (900, 600, None, 900),  # agent_def when agent timeout is None
            (900, 600, 120, 120),  # agent_config overrides agent_def
        ],
    )
    def test_timeout_priority_resolution(
        self,
        agent_def_timeout: int | None,
        global_timeout: int,
        agent_cfg_timeout: int | str | None,
        expected: int,
    ) -> None:
        """timeout の優先順を検証: agent_config > agent_def > global_config。"""
        agent = _make_agent(timeout=agent_def_timeout)
        config = HachimokuConfig(timeout=global_timeout)
        agent_cfg = (
            None
            if agent_cfg_timeout == _NO_AGENT_CONFIG
            else AgentConfig(timeout=agent_cfg_timeout)  # type: ignore[arg-type]
        )
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=agent_cfg,
            global_config=config,
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.timeout_seconds == expected


# =============================================================================
# build_execution_context — max_turns 優先順解決
# =============================================================================


class TestBuildExecutionContextMaxTurnsResolution:
    """max_turns フィールドの優先順解決を検証（FR-RE-004）。"""

    @pytest.mark.parametrize(
        ("agent_def_max_turns", "global_max_turns", "agent_cfg_max_turns", "expected"),
        [
            (None, 20, _NO_AGENT_CONFIG, 20),  # global when no agent_config
            (None, 20, None, 20),  # global when agent max_turns is None
            (None, 20, 5, 5),  # agent_config overrides global
            (25, 20, _NO_AGENT_CONFIG, 25),  # agent_def when no agent_config
            (25, 20, None, 25),  # agent_def when agent max_turns is None
            (25, 20, 5, 5),  # agent_config overrides agent_def
        ],
    )
    def test_max_turns_priority_resolution(
        self,
        agent_def_max_turns: int | None,
        global_max_turns: int,
        agent_cfg_max_turns: int | str | None,
        expected: int,
    ) -> None:
        """max_turns の優先順を検証: agent_config > agent_def > global_config。"""
        agent = _make_agent(max_turns=agent_def_max_turns)
        config = HachimokuConfig(max_turns=global_max_turns)
        agent_cfg = (
            None
            if agent_cfg_max_turns == _NO_AGENT_CONFIG
            else AgentConfig(max_turns=agent_cfg_max_turns)  # type: ignore[arg-type]
        )
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=agent_cfg,
            global_config=config,
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.max_turns == expected


# =============================================================================
# build_execution_context — 部分オーバーライド
# =============================================================================


class TestBuildExecutionContextPartialOverride:
    """agent_config の一部フィールドのみ設定した場合の動作を検証。"""

    def test_partial_agent_config_model_only(self) -> None:
        """model のみ設定し、timeout/max_turns はグローバル値が使用される。"""
        agent = _make_agent()
        config = HachimokuConfig(model="global-model", timeout=600, max_turns=20)
        agent_cfg = AgentConfig(model="agent-model")
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=agent_cfg,
            global_config=config,
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.model == "agent-model"
        assert ctx.timeout_seconds == 600
        assert ctx.max_turns == 20

    def test_partial_agent_config_timeout_and_max_turns_only(self) -> None:
        """timeout と max_turns のみ設定し、model は agent_def 値が使用される。"""
        agent = _make_agent(model="def-model")
        config = HachimokuConfig(model="global-model", timeout=600, max_turns=20)
        agent_cfg = AgentConfig(timeout=60, max_turns=5)
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=agent_cfg,
            global_config=config,
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.model == "def-model"
        assert ctx.timeout_seconds == 60
        assert ctx.max_turns == 5


# =============================================================================
# build_execution_context — Phase バリエーション
# =============================================================================


class TestBuildExecutionContextPhaseVariants:
    """各 Phase が正しく伝播されることを検証。"""

    def test_defaults_from_hachimoku_config(self) -> None:
        """HachimokuConfig のデフォルト値がコンテキストに正しく伝播する。"""
        agent = _make_agent(model="claudecode:claude-opus-4-6")
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.model == "claudecode:claude-opus-4-6"
        assert ctx.timeout_seconds == 600
        assert ctx.max_turns == 30

    def test_early_phase_propagated(self) -> None:
        """Phase.EARLY が正しく設定される。"""
        agent = _make_agent(phase=Phase.EARLY)
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.phase == Phase.EARLY

    def test_final_phase_propagated(self) -> None:
        """Phase.FINAL が正しく設定される。"""
        agent = _make_agent(phase=Phase.FINAL)
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.phase == Phase.FINAL


# =============================================================================
# AgentExecutionContext — builtin_tools / claudecode_builtin_names（Issue #222）
# =============================================================================


class TestAgentExecutionContextBuiltinTools:
    """AgentExecutionContext の builtin_tools / claudecode_builtin_names テスト。Issue #222。"""

    def test_builtin_tools_default_empty(self) -> None:
        """builtin_tools のデフォルトは空タプル。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert ctx.builtin_tools == ()

    def test_builtin_tools_accepts_web_fetch_tool(self) -> None:
        """builtin_tools に WebFetchTool を設定できる。"""
        from pydantic_ai.builtin_tools import WebFetchTool

        agent = _make_agent()
        wft = WebFetchTool()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            builtin_tools=(wft,),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert len(ctx.builtin_tools) == 1
        assert isinstance(ctx.builtin_tools[0], WebFetchTool)

    def test_claudecode_builtin_names_default_empty(self) -> None:
        """claudecode_builtin_names のデフォルトは空タプル。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert ctx.claudecode_builtin_names == ()

    def test_claudecode_builtin_names_preserves_value(self) -> None:
        """claudecode_builtin_names に設定した値が保持される。"""
        agent = _make_agent()
        ctx = AgentExecutionContext(
            agent_name="test-agent",
            model="sonnet",
            system_prompt="prompt",
            user_message="message",
            output_schema=agent.resolved_schema,
            tools=(),
            claudecode_builtin_names=("WebFetch",),
            timeout_seconds=300,
            max_turns=10,
            phase=Phase.MAIN,
        )
        assert ctx.claudecode_builtin_names == ("WebFetch",)

    def test_non_builtin_tool_in_builtin_tools_rejected(self) -> None:
        """builtin_tools に AbstractBuiltinTool 以外の要素を含む場合 ValueError を送出する。"""
        agent = _make_agent()
        with pytest.raises(ValueError, match="AbstractBuiltinTool"):
            AgentExecutionContext(
                agent_name="test-agent",
                model="sonnet",
                system_prompt="prompt",
                user_message="message",
                output_schema=agent.resolved_schema,
                tools=(),
                builtin_tools=("not-a-builtin-tool",),  # type: ignore[arg-type]
                timeout_seconds=300,
                max_turns=10,
                phase=Phase.MAIN,
            )


# =============================================================================
# build_execution_context — builtin_tools パススルー（Issue #222）
# =============================================================================


class TestBuildExecutionContextBuiltinTools:
    """build_execution_context の builtin_tools / claudecode_builtin_names テスト。Issue #222。"""

    def test_builtin_tools_default_empty(self) -> None:
        """resolved_builtin_tools 省略時は空タプル。"""
        agent = _make_agent()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.builtin_tools == ()

    def test_builtin_tools_passthrough(self) -> None:
        """resolved_builtin_tools がそのまま設定される。"""
        from pydantic_ai.builtin_tools import WebFetchTool

        agent = _make_agent()
        wft = WebFetchTool()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
            resolved_builtin_tools=(wft,),
        )
        assert len(ctx.builtin_tools) == 1
        assert ctx.builtin_tools[0] is wft

    def test_claudecode_builtin_names_default_empty(self) -> None:
        """claudecode_builtin_names 省略時は空タプル。"""
        agent = _make_agent()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
        )
        assert ctx.claudecode_builtin_names == ()

    def test_claudecode_builtin_names_passthrough(self) -> None:
        """claudecode_builtin_names がそのまま設定される。"""
        agent = _make_agent()
        ctx = build_execution_context(
            agent_def=agent,
            agent_config=None,
            global_config=HachimokuConfig(),
            user_message="msg",
            resolved_tools=(),
            claudecode_builtin_names=("WebFetch",),
        )
        assert ctx.claudecode_builtin_names == ("WebFetch",)
