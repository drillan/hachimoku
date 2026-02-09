"""エージェントローダーのテスト。

T013: _load_single_agent — 正常 TOML, 不正 TOML 構文, 必須フィールド欠損
T014: load_builtin_agents — 6エージェント全件, 各名前存在, errors 空,
      エラー収集パスの検証
T015: builtin agent validation — output_schema, phase, applicability
T030: load_custom_agents — カスタム定義読み込み, ディレクトリ不在, 部分失敗
T031: load_agents — ビルトイン+カスタム統合, 同名上書き, エラー統合
T-118-002: load_builtin_selector / load_selector — セレクター定義の読み込み
T-118-003: load_builtin_agents / load_custom_agents — selector.toml 除外

タスク参照: specs/003-agent-definition/tasks.md Phase 3, Phase 5
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hachimoku.agents.loader import (
    _load_single_agent,
    load_agents,
    load_builtin_agents,
    load_builtin_selector,
    load_custom_agents,
    load_selector,
)
from hachimoku.agents.models import (
    AgentDefinition,
    LoadResult,
    Phase,
    SelectorDefinition,
)


# =============================================================================
# ヘルパー
# =============================================================================

VALID_TOML = """\
name = "test-agent"
description = "A test agent"
model = "anthropic:claude-sonnet-4-5"
output_schema = "scored_issues"
system_prompt = "You are a test agent."
"""

BUILTIN_AGENT_NAMES = frozenset(
    {
        "code-reviewer",
        "silent-failure-hunter",
        "pr-test-analyzer",
        "type-design-analyzer",
        "comment-analyzer",
        "code-simplifier",
    }
)


def _write_toml(tmp_path: Path, filename: str, content: str) -> Path:
    """tmp_path に TOML ファイルを書き出す。"""
    toml_path = tmp_path / filename
    toml_path.write_text(content, encoding="utf-8")
    return toml_path


def _find_agent(agents: tuple[AgentDefinition, ...], name: str) -> AgentDefinition:
    """名前でエージェントを検索する。見つからなければ AssertionError。"""
    for agent in agents:
        if agent.name == name:
            return agent
    raise AssertionError(f"Agent '{name}' not found in {[a.name for a in agents]}")


# =============================================================================
# Fixtures（T014, T015 用）
# =============================================================================


@pytest.fixture(scope="module")
def builtin_result() -> LoadResult:
    """ビルトインエージェントの読み込み結果。モジュール内で1回だけ実行。"""
    return load_builtin_agents()


@pytest.fixture(scope="module")
def builtin_agents(builtin_result: LoadResult) -> tuple[AgentDefinition, ...]:
    """ビルトインエージェントのタプル。"""
    return builtin_result.agents


# =============================================================================
# T013: _load_single_agent — 正常系
# =============================================================================


class TestLoadSingleAgentValid:
    """_load_single_agent の正常系を検証。"""

    def test_returns_agent_definition(self, tmp_path: Path) -> None:
        """正常な TOML から AgentDefinition が返される。"""
        path = _write_toml(tmp_path, "test-agent.toml", VALID_TOML)
        result = _load_single_agent(path)
        assert isinstance(result, AgentDefinition)

    def test_fields_match_toml_content(self, tmp_path: Path) -> None:
        """返された AgentDefinition の各フィールドが TOML の値と一致する。"""
        path = _write_toml(tmp_path, "test-agent.toml", VALID_TOML)
        agent = _load_single_agent(path)
        assert agent.name == "test-agent"
        assert agent.description == "A test agent"
        assert agent.model == "anthropic:claude-sonnet-4-5"
        assert agent.output_schema == "scored_issues"
        assert agent.system_prompt == "You are a test agent."

    def test_applicability_section_parsed(self, tmp_path: Path) -> None:
        """[applicability] セクション付き TOML が正しくパースされる。"""
        toml_content = (
            VALID_TOML
            + """\

[applicability]
file_patterns = ["*.py", "*.ts"]
content_patterns = ["class\\\\s+\\\\w+"]
"""
        )
        path = _write_toml(tmp_path, "with-applicability.toml", toml_content)
        agent = _load_single_agent(path)
        assert agent.applicability.file_patterns == ("*.py", "*.ts")
        assert agent.applicability.content_patterns == (r"class\s+\w+",)

    def test_allowed_tools_parsed(self, tmp_path: Path) -> None:
        """allowed_tools がタプルとして保持される。"""
        toml_content = VALID_TOML.replace(
            'system_prompt = "You are a test agent."',
            'system_prompt = "You are a test agent."\nallowed_tools = ["tool1", "tool2"]',
        )
        path = _write_toml(tmp_path, "with-tools.toml", toml_content)
        agent = _load_single_agent(path)
        assert agent.allowed_tools == ("tool1", "tool2")

    def test_default_applicability_always_true(self, tmp_path: Path) -> None:
        """applicability 未指定時はデフォルトで always=True。"""
        path = _write_toml(tmp_path, "default-app.toml", VALID_TOML)
        agent = _load_single_agent(path)
        assert agent.applicability.always is True

    def test_default_phase_main(self, tmp_path: Path) -> None:
        """phase 未指定時はデフォルトで main。"""
        path = _write_toml(tmp_path, "default-phase.toml", VALID_TOML)
        agent = _load_single_agent(path)
        assert agent.phase == Phase.MAIN

    def test_explicit_phase_parsed(self, tmp_path: Path) -> None:
        """phase 指定が正しくパースされる。"""
        toml_content = VALID_TOML + 'phase = "early"\n'
        path = _write_toml(tmp_path, "with-phase.toml", toml_content)
        agent = _load_single_agent(path)
        assert agent.phase == Phase.EARLY


# =============================================================================
# T013: _load_single_agent — エラー系
# =============================================================================


class TestLoadSingleAgentErrors:
    """_load_single_agent のエラー系を検証。"""

    def test_invalid_toml_syntax_raises(self, tmp_path: Path) -> None:
        """不正な TOML 構文で TOMLDecodeError が送出される。"""
        path = _write_toml(tmp_path, "bad-syntax.toml", 'name = "unclosed')
        with pytest.raises(tomllib.TOMLDecodeError):
            _load_single_agent(path)

    def test_missing_required_field_raises_validation_error(
        self, tmp_path: Path
    ) -> None:
        """必須フィールド欠損で ValidationError が送出される。"""
        incomplete_toml = """\
name = "test-agent"
description = "A test agent"
"""
        path = _write_toml(tmp_path, "incomplete.toml", incomplete_toml)
        with pytest.raises(ValidationError):
            _load_single_agent(path)

    def test_unknown_schema_raises_validation_error(self, tmp_path: Path) -> None:
        """存在しない output_schema で ValidationError が送出される。"""
        bad_schema_toml = VALID_TOML.replace("scored_issues", "nonexistent")
        path = _write_toml(tmp_path, "bad-schema.toml", bad_schema_toml)
        with pytest.raises(ValidationError, match="not registered"):
            _load_single_agent(path)

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """存在しないパスで FileNotFoundError が送出される。"""
        with pytest.raises(FileNotFoundError):
            _load_single_agent(tmp_path / "nonexistent.toml")


# =============================================================================
# T014: load_builtin_agents
# =============================================================================


class TestLoadBuiltinAgents:
    """load_builtin_agents のテストを検証。"""

    def test_returns_load_result(self, builtin_result: LoadResult) -> None:
        """戻り値が LoadResult インスタンスである。"""
        assert isinstance(builtin_result, LoadResult)

    def test_loads_six_agents(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        """6つのエージェントが読み込まれる。"""
        assert len(builtin_agents) == 6

    def test_all_agent_names_present(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        """6つの名前が全て存在する。"""
        loaded_names = {agent.name for agent in builtin_agents}
        assert loaded_names == BUILTIN_AGENT_NAMES

    def test_no_errors(self, builtin_result: LoadResult) -> None:
        """errors が空タプルである。"""
        assert builtin_result.errors == ()

    def test_all_agents_are_agent_definition(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        """全要素が AgentDefinition インスタンスである。"""
        for agent in builtin_agents:
            assert isinstance(agent, AgentDefinition)


# =============================================================================
# T014: load_builtin_agents — エラー収集パスの検証
# =============================================================================


class TestLoadBuiltinAgentsErrorCollection:
    """load_builtin_agents のエラー収集パスを検証。"""

    @staticmethod
    def _load_builtin_with_failure(target_name: str, error: Exception) -> LoadResult:
        """指定名のエージェント読み込み時に例外を発生させてビルトインを読み込む。"""
        original = _load_single_agent

        def _failing_loader(path: Path) -> AgentDefinition:
            if target_name in str(path):
                raise error
            return original(path)

        with patch(
            "hachimoku.agents.loader._load_single_agent",
            side_effect=_failing_loader,
        ):
            return load_builtin_agents()

    def test_error_collected_in_load_result(self) -> None:
        """_load_single_agent の例外が LoadResult.errors に収集される。"""
        result = self._load_builtin_with_failure(
            "code-reviewer",
            ValidationError.from_exception_data(
                title="AgentDefinition", line_errors=[]
            ),
        )
        assert len(result.errors) == 1
        assert "code-reviewer.toml" in result.errors[0].source

    def test_error_source_contains_filename(self) -> None:
        """LoadError.source にファイル名が設定される。"""
        result = self._load_builtin_with_failure(
            "pr-test-analyzer", OSError("mock file error")
        )
        assert len(result.errors) == 1
        assert result.errors[0].source == "pr-test-analyzer.toml"

    def test_error_message_includes_type_name(self) -> None:
        """LoadError.message に例外型名が含まれる。"""
        result = self._load_builtin_with_failure(
            "comment-analyzer", OSError("bad file access")
        )
        assert len(result.errors) == 1
        assert "OSError" in result.errors[0].message

    def test_one_error_does_not_block_others(self) -> None:
        """1ファイルの失敗が他ファイルの読み込みを妨げない。"""
        result = self._load_builtin_with_failure(
            "code-reviewer",
            ValidationError.from_exception_data(
                title="AgentDefinition", line_errors=[]
            ),
        )
        assert len(result.agents) == 5
        assert len(result.errors) == 1
        loaded_names = {agent.name for agent in result.agents}
        assert "code-reviewer" not in loaded_names


# =============================================================================
# T015: ビルトインエージェント — output_schema 検証
# =============================================================================


class TestBuiltinAgentSchemas:
    """各ビルトインエージェントの output_schema を検証。"""

    @pytest.mark.parametrize(
        ("agent_name", "expected_schema"),
        [
            ("code-reviewer", "scored_issues"),
            ("silent-failure-hunter", "severity_classified"),
            ("pr-test-analyzer", "test_gap_assessment"),
            ("type-design-analyzer", "multi_dimensional_analysis"),
            ("comment-analyzer", "category_classification"),
            ("code-simplifier", "improvement_suggestions"),
        ],
    )
    def test_output_schema(
        self,
        builtin_agents: tuple[AgentDefinition, ...],
        agent_name: str,
        expected_schema: str,
    ) -> None:
        agent = _find_agent(builtin_agents, agent_name)
        assert agent.output_schema == expected_schema


# =============================================================================
# T015: ビルトインエージェント — phase 検証
# =============================================================================


class TestBuiltinAgentPhases:
    """各ビルトインエージェントの phase を検証。"""

    @pytest.mark.parametrize(
        ("agent_name", "expected_phase"),
        [
            ("code-reviewer", Phase.MAIN),
            ("silent-failure-hunter", Phase.MAIN),
            ("pr-test-analyzer", Phase.MAIN),
            ("type-design-analyzer", Phase.MAIN),
            ("comment-analyzer", Phase.FINAL),
            ("code-simplifier", Phase.FINAL),
        ],
    )
    def test_phase(
        self,
        builtin_agents: tuple[AgentDefinition, ...],
        agent_name: str,
        expected_phase: Phase,
    ) -> None:
        agent = _find_agent(builtin_agents, agent_name)
        assert agent.phase == expected_phase


# =============================================================================
# T015: ビルトインエージェント — applicability 検証
# =============================================================================


class TestBuiltinAgentApplicability:
    """各ビルトインエージェントの applicability を検証。"""

    def test_code_reviewer_always_true(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        agent = _find_agent(builtin_agents, "code-reviewer")
        assert agent.applicability.always is True

    def test_silent_failure_hunter_has_content_patterns(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        agent = _find_agent(builtin_agents, "silent-failure-hunter")
        assert len(agent.applicability.content_patterns) > 0

    def test_pr_test_analyzer_has_file_patterns(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        agent = _find_agent(builtin_agents, "pr-test-analyzer")
        assert len(agent.applicability.file_patterns) > 0

    def test_type_design_analyzer_has_file_and_content_patterns(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        agent = _find_agent(builtin_agents, "type-design-analyzer")
        assert len(agent.applicability.file_patterns) > 0
        assert len(agent.applicability.content_patterns) > 0

    def test_comment_analyzer_has_content_patterns(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        agent = _find_agent(builtin_agents, "comment-analyzer")
        assert len(agent.applicability.content_patterns) > 0

    def test_code_simplifier_always_true(
        self, builtin_agents: tuple[AgentDefinition, ...]
    ) -> None:
        agent = _find_agent(builtin_agents, "code-simplifier")
        assert agent.applicability.always is True


# =============================================================================
# T030: load_custom_agents
# =============================================================================


class TestLoadCustomAgents:
    """load_custom_agents のテストを検証。"""

    def test_loads_valid_custom_agent(self, tmp_path: Path) -> None:
        """正常なカスタム定義が読み込まれる。"""
        _write_toml(tmp_path, "custom-agent.toml", VALID_TOML)
        result = load_custom_agents(tmp_path)
        assert len(result.agents) == 1
        assert result.agents[0].name == "test-agent"

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        """存在しないディレクトリで空 LoadResult が返される。"""
        result = load_custom_agents(tmp_path / "nonexistent")
        assert result.agents == ()
        assert result.errors == ()

    def test_ignores_non_toml_files(self, tmp_path: Path) -> None:
        """.toml 以外のファイルは無視される。"""
        _write_toml(tmp_path, "custom-agent.toml", VALID_TOML)
        (tmp_path / "readme.txt").write_text("not a toml file")
        (tmp_path / "script.py").write_text("print('hello')")
        result = load_custom_agents(tmp_path)
        assert len(result.agents) == 1
        assert result.errors == ()

    def test_partial_failure_collects_error(self, tmp_path: Path) -> None:
        """不正な TOML がある場合、他の正常定義は読み込まれエラーが収集される。"""
        _write_toml(tmp_path, "good-agent.toml", VALID_TOML)
        _write_toml(tmp_path, "bad-agent.toml", 'name = "unclosed')
        result = load_custom_agents(tmp_path)
        assert len(result.agents) == 1
        assert len(result.errors) == 1

    def test_error_source_contains_filename(self, tmp_path: Path) -> None:
        """LoadError.source にファイル名が設定される。"""
        _write_toml(tmp_path, "broken.toml", 'name = "unclosed')
        result = load_custom_agents(tmp_path)
        assert result.errors[0].source == "broken.toml"

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        """存在するが空のディレクトリで空 LoadResult が返される。"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = load_custom_agents(empty_dir)
        assert result.agents == ()
        assert result.errors == ()

    def test_file_path_raises_not_a_directory_error(self, tmp_path: Path) -> None:
        """ファイルパスを渡すと NotADirectoryError が送出される。"""
        file_path = tmp_path / "not-a-dir.toml"
        file_path.write_text("dummy")
        with pytest.raises(NotADirectoryError, match="ディレクトリではありません"):
            load_custom_agents(file_path)

    def test_validation_error_collected(self, tmp_path: Path) -> None:
        """必須フィールド欠損による ValidationError がエラーとして収集される。"""
        incomplete_toml = 'name = "test-agent"\ndescription = "incomplete"\n'
        _write_toml(tmp_path, "incomplete.toml", incomplete_toml)
        result = load_custom_agents(tmp_path)
        assert len(result.agents) == 0
        assert len(result.errors) == 1
        assert "ValidationError" in result.errors[0].message

    def test_error_message_includes_type_name(self, tmp_path: Path) -> None:
        """LoadError.message に例外型名が含まれる。"""
        _write_toml(tmp_path, "broken.toml", 'name = "unclosed')
        result = load_custom_agents(tmp_path)
        assert "TOMLDecodeError" in result.errors[0].message

    def test_multiple_valid_custom_agents(self, tmp_path: Path) -> None:
        """複数の正常カスタム定義が全件読み込まれる。"""
        agent1 = VALID_TOML.replace("test-agent", "custom-one")
        agent2 = VALID_TOML.replace("test-agent", "custom-two")
        _write_toml(tmp_path, "custom-one.toml", agent1)
        _write_toml(tmp_path, "custom-two.toml", agent2)
        result = load_custom_agents(tmp_path)
        assert len(result.agents) == 2
        loaded_names = {a.name for a in result.agents}
        assert loaded_names == {"custom-one", "custom-two"}


# =============================================================================
# T031: load_agents — 統合テスト
# =============================================================================


class TestLoadAgents:
    """load_agents の統合テストを検証。"""

    def test_builtin_only_when_no_custom_dir(self) -> None:
        """custom_dir=None でビルトインのみが読み込まれる。"""
        result = load_agents(custom_dir=None)
        assert len(result.agents) == 6
        loaded_names = {a.name for a in result.agents}
        assert loaded_names == BUILTIN_AGENT_NAMES

    def test_custom_added_to_builtin(self, tmp_path: Path) -> None:
        """新名前のカスタムがビルトインに追加される。"""
        _write_toml(tmp_path, "my-custom.toml", VALID_TOML)
        result = load_agents(custom_dir=tmp_path)
        assert len(result.agents) == 7
        loaded_names = {a.name for a in result.agents}
        assert "test-agent" in loaded_names
        assert BUILTIN_AGENT_NAMES.issubset(loaded_names)

    def test_custom_overrides_builtin(self, tmp_path: Path) -> None:
        """同名のカスタムがビルトインを上書きする。"""
        override_toml = VALID_TOML.replace("test-agent", "code-reviewer").replace(
            "A test agent", "Custom code reviewer"
        )
        _write_toml(tmp_path, "code-reviewer.toml", override_toml)
        result = load_agents(custom_dir=tmp_path)
        agent = _find_agent(result.agents, "code-reviewer")
        assert agent.description == "Custom code reviewer"
        assert len(result.agents) == 6

    def test_invalid_custom_does_not_override_builtin(self, tmp_path: Path) -> None:
        """不正なカスタムが同名ビルトインを上書きしない。"""
        _write_toml(tmp_path, "code-reviewer.toml", 'name = "unclosed')
        result = load_agents(custom_dir=tmp_path)
        agent = _find_agent(result.agents, "code-reviewer")
        assert agent.description == "コード品質・バグ・ベストプラクティスの総合レビュー"
        assert len(result.errors) == 1

    def test_errors_merged(self, tmp_path: Path) -> None:
        """ビルトインとカスタムのエラーが統合される。"""
        _write_toml(tmp_path, "bad.toml", 'name = "unclosed')
        result = load_agents(custom_dir=tmp_path)
        assert len(result.errors) == 1
        assert result.errors[0].source == "bad.toml"


# =============================================================================
# ビルトインエージェント — allowed_tools 検証
# =============================================================================


class TestBuiltinAgentAllowedTools:
    """各ビルトインエージェントの allowed_tools を検証。"""

    @pytest.mark.parametrize(
        "agent_name",
        sorted(BUILTIN_AGENT_NAMES),
    )
    def test_allowed_tools(
        self,
        builtin_agents: tuple[AgentDefinition, ...],
        agent_name: str,
    ) -> None:
        """全ビルトインエージェントが git_read, gh_read, file_read を持つ。"""
        agent = _find_agent(builtin_agents, agent_name)
        assert agent.allowed_tools == ("git_read", "gh_read", "file_read")


# =============================================================================
# ビルトインエージェント — system_prompt 構造検証
# =============================================================================


class TestBuiltinAgentSystemPromptStructure:
    """各ビルトインエージェントの system_prompt の構造的制約を検証。"""

    @pytest.mark.parametrize(
        "agent_name",
        sorted(BUILTIN_AGENT_NAMES),
    )
    def test_system_prompt_line_count_within_range(
        self,
        builtin_agents: tuple[AgentDefinition, ...],
        agent_name: str,
    ) -> None:
        """system_prompt が 30-50 行の範囲内である。"""
        agent = _find_agent(builtin_agents, agent_name)
        lines = agent.system_prompt.strip().splitlines()
        assert 30 <= len(lines) <= 50, (
            f"{agent_name}: expected 30-50 lines, got {len(lines)}"
        )

    @pytest.mark.parametrize(
        "agent_name",
        sorted(BUILTIN_AGENT_NAMES),
    )
    def test_system_prompt_contains_agent_name_reference(
        self,
        builtin_agents: tuple[AgentDefinition, ...],
        agent_name: str,
    ) -> None:
        """system_prompt にエージェント名への言及を含む。"""
        agent = _find_agent(builtin_agents, agent_name)
        prompt_lower = agent.system_prompt.lower()
        assert agent_name in prompt_lower, (
            f"{agent_name}: system_prompt does not reference agent name"
        )

    @pytest.mark.parametrize(
        "agent_name",
        sorted(BUILTIN_AGENT_NAMES),
    )
    def test_system_prompt_no_backslash(
        self,
        builtin_agents: tuple[AgentDefinition, ...],
        agent_name: str,
    ) -> None:
        r"""system_prompt にバックスラッシュを含まない（TOML パース安全性）。"""
        agent = _find_agent(builtin_agents, agent_name)
        assert "\\" not in agent.system_prompt, (
            f"{agent_name}: system_prompt contains backslash"
        )


# =============================================================================
# ヘルパー（セレクター用）
# =============================================================================

VALID_SELECTOR_TOML = """\
name = "selector"
description = "Agent selector for code review"
model = "claudecode:claude-sonnet-4-5"
allowed_tools = ["git_read", "gh_read", "file_read"]
system_prompt = "You are an agent selector."
"""


# =============================================================================
# T-118-002: load_builtin_selector
# =============================================================================


class TestLoadBuiltinSelector:
    """load_builtin_selector のテストを検証。"""

    def test_returns_selector_definition(self) -> None:
        """戻り値が SelectorDefinition インスタンスである。"""
        result = load_builtin_selector()
        assert isinstance(result, SelectorDefinition)

    def test_name_is_selector(self) -> None:
        """ビルトインセレクターの name が "selector" である。"""
        result = load_builtin_selector()
        assert result.name == "selector"

    def test_system_prompt_non_empty(self) -> None:
        """ビルトインセレクターの system_prompt が空でない。"""
        result = load_builtin_selector()
        assert len(result.system_prompt.strip()) > 0

    def test_allowed_tools_non_empty(self) -> None:
        """ビルトインセレクターの allowed_tools が空でない。"""
        result = load_builtin_selector()
        assert len(result.allowed_tools) > 0

    def test_model_non_empty(self) -> None:
        """ビルトインセレクターの model が空でない。"""
        result = load_builtin_selector()
        assert len(result.model) > 0


# =============================================================================
# T-118-002: load_selector
# =============================================================================


class TestLoadSelector:
    """load_selector のテストを検証。"""

    def test_builtin_only_when_no_custom_dir(self) -> None:
        """custom_dir=None でビルトインセレクターが返される。"""
        result = load_selector(custom_dir=None)
        assert isinstance(result, SelectorDefinition)
        assert result.name == "selector"

    def test_custom_override(self, tmp_path: Path) -> None:
        """カスタム selector.toml がビルトインを上書きする。"""
        custom_toml = VALID_SELECTOR_TOML.replace(
            "Agent selector for code review", "Custom selector"
        )
        _write_toml(tmp_path, "selector.toml", custom_toml)
        result = load_selector(custom_dir=tmp_path)
        assert result.description == "Custom selector"

    def test_builtin_used_when_no_custom_selector(self, tmp_path: Path) -> None:
        """カスタムディレクトリに selector.toml がない場合はビルトインが使用される。"""
        _write_toml(tmp_path, "other-agent.toml", VALID_TOML)
        result = load_selector(custom_dir=tmp_path)
        assert result.name == "selector"
        assert result.description != "A test agent"

    def test_invalid_custom_raises_error(self, tmp_path: Path) -> None:
        """不正なカスタム selector.toml で例外が送出される。"""
        _write_toml(tmp_path, "selector.toml", 'name = "unclosed')
        with pytest.raises(Exception):
            load_selector(custom_dir=tmp_path)

    def test_nonexistent_custom_dir_returns_builtin(self, tmp_path: Path) -> None:
        """存在しないカスタムディレクトリでビルトインが返される。"""
        result = load_selector(custom_dir=tmp_path / "nonexistent")
        assert result.name == "selector"


# =============================================================================
# T-118-003: load_builtin_agents はセレクターを除外
# =============================================================================


class TestLoadBuiltinAgentsExcludesSelector:
    """load_builtin_agents の結果にセレクターが含まれないことを検証。"""

    def test_selector_not_in_builtin_agents(self) -> None:
        """ビルトインエージェントリストに "selector" が含まれない。"""
        result = load_builtin_agents()
        agent_names = {a.name for a in result.agents}
        assert "selector" not in agent_names


class TestLoadCustomAgentsExcludesSelector:
    """load_custom_agents の結果にセレクターが含まれないことを検証。"""

    def test_selector_excluded_from_custom_agents(self, tmp_path: Path) -> None:
        """カスタムディレクトリの selector.toml がエージェントリストに含まれない。"""
        _write_toml(tmp_path, "selector.toml", VALID_SELECTOR_TOML)
        _write_toml(tmp_path, "custom-agent.toml", VALID_TOML)
        result = load_custom_agents(tmp_path)
        agent_names = {a.name for a in result.agents}
        assert "selector" not in agent_names
        assert "test-agent" in agent_names


class TestLoadAgentsExcludesSelector:
    """load_agents の結果にセレクターが含まれないことを検証。"""

    def test_selector_excluded_from_merged_agents(self, tmp_path: Path) -> None:
        """統合結果にセレクターが含まれない。"""
        _write_toml(tmp_path, "selector.toml", VALID_SELECTOR_TOML)
        result = load_agents(custom_dir=tmp_path)
        agent_names = {a.name for a in result.agents}
        assert "selector" not in agent_names
