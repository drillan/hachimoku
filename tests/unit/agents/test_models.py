"""Phase, PHASE_ORDER, ApplicabilityRule, LoadError, AgentDefinition, LoadResult,
SelectorDefinition のテスト。

T004: Phase StrEnum — 列挙値(early/main/final)、PHASE_ORDER ソート順検証
T005: ApplicabilityRule — デフォルト値、正規表現バリデーション、frozen、extra=forbid
T006: AgentDefinition — 全必須フィールド、name パターン、output_schema 解決、デフォルト値、frozen、extra=forbid
T007: LoadError / LoadResult — フィールドバリデーション、frozen、extra=forbid
T-118-001: SelectorDefinition — 全必須フィールド、name パターン、frozen、extra=forbid
"""

import pytest
from pydantic import ValidationError

from hachimoku.agents.models import (
    AGENT_NAME_PATTERN,
    PHASE_ORDER,
    AgentDefinition,
    ApplicabilityRule,
    LoadError,
    LoadResult,
    Phase,
    SelectorDefinition,
)
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.schemas import BaseAgentOutput, ScoredIssues


# =============================================================================
# Phase StrEnum
# =============================================================================


class TestPhaseEnumValues:
    """Phase 列挙値の定義を検証。"""

    def test_has_three_members(self) -> None:
        """3つの列挙値が定義されている。"""
        assert len(Phase) == 3

    def test_early_value(self) -> None:
        assert Phase.EARLY == "early"
        assert Phase.EARLY.value == "early"

    def test_main_value(self) -> None:
        assert Phase.MAIN == "main"
        assert Phase.MAIN.value == "main"

    def test_final_value(self) -> None:
        assert Phase.FINAL == "final"
        assert Phase.FINAL.value == "final"

    def test_invalid_value_raises_error(self) -> None:
        """定義外の値は ValueError を発生させる。"""
        with pytest.raises(ValueError):
            Phase("invalid")

    def test_is_str_enum(self) -> None:
        """Phase は StrEnum のサブクラスである。"""
        assert isinstance(Phase.EARLY, str)


# =============================================================================
# PHASE_ORDER
# =============================================================================


class TestPhaseOrder:
    """PHASE_ORDER 定数の定義を検証。"""

    def test_order_mapping(self) -> None:
        """EARLY=0 < MAIN=1 < FINAL=2。"""
        assert PHASE_ORDER == {
            Phase.EARLY: 0,
            Phase.MAIN: 1,
            Phase.FINAL: 2,
        }

    def test_early_is_lowest(self) -> None:
        assert PHASE_ORDER[Phase.EARLY] == min(PHASE_ORDER.values())

    def test_final_is_highest(self) -> None:
        assert PHASE_ORDER[Phase.FINAL] == max(PHASE_ORDER.values())

    def test_immutable(self) -> None:
        """PHASE_ORDER は変更不可である。"""
        with pytest.raises(TypeError):
            PHASE_ORDER[Phase.EARLY] = -999  # type: ignore[index]

    def test_all_phase_members_in_order_mapping(self) -> None:
        """全 Phase メンバーが PHASE_ORDER に含まれている。"""
        for member in Phase:
            assert member in PHASE_ORDER

    def test_order_mapping_covers_only_phase_members(self) -> None:
        """PHASE_ORDER のキーは Phase メンバーと完全一致する。"""
        assert set(PHASE_ORDER.keys()) == set(Phase)

    def test_sorted_by_phase_order(self) -> None:
        """PHASE_ORDER でソートすると EARLY, MAIN, FINAL の順になる。"""
        phases = [Phase.FINAL, Phase.EARLY, Phase.MAIN]
        sorted_phases = sorted(phases, key=lambda p: PHASE_ORDER[p])
        assert sorted_phases == [Phase.EARLY, Phase.MAIN, Phase.FINAL]


# =============================================================================
# ApplicabilityRule — 正常系
# =============================================================================


class TestApplicabilityRuleValid:
    """ApplicabilityRule の正常系を検証。"""

    def test_default_values(self) -> None:
        """デフォルト値でインスタンス生成が成功する。"""
        rule = ApplicabilityRule()
        assert rule.always is False
        assert rule.file_patterns == ()
        assert rule.content_patterns == ()

    def test_always_true(self) -> None:
        """always=True でインスタンス生成が成功する。"""
        rule = ApplicabilityRule(always=True)
        assert rule.always is True

    def test_file_patterns(self) -> None:
        """file_patterns 指定でインスタンス生成が成功する。"""
        rule = ApplicabilityRule(file_patterns=("*.py", "*.ts"))
        assert rule.file_patterns == ("*.py", "*.ts")

    def test_content_patterns_valid_regex(self) -> None:
        r"""有効な正規表現の content_patterns でインスタンス生成が成功する。"""
        rule = ApplicabilityRule(content_patterns=(r"class\s+\w+", r"def\s+\w+"))
        assert rule.content_patterns == (r"class\s+\w+", r"def\s+\w+")

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        rule = ApplicabilityRule()
        assert isinstance(rule, HachimokuBaseModel)


# =============================================================================
# ApplicabilityRule — 制約
# =============================================================================


class TestApplicabilityRuleConstraints:
    """ApplicabilityRule の制約を検証。"""

    def test_invalid_regex_rejected(self) -> None:
        """無効な正規表現がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="Invalid regex pattern"):
            ApplicabilityRule(content_patterns=("[invalid",))

    def test_invalid_regex_error_contains_pattern(self) -> None:
        r"""エラーメッセージに無効なパターンが含まれる。"""
        with pytest.raises(ValidationError, match=r"\[invalid"):
            ApplicabilityRule(content_patterns=("[invalid",))

    def test_mixed_valid_and_invalid_regex_rejected(self) -> None:
        """有効と無効が混在する場合もバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="Invalid regex pattern"):
            ApplicabilityRule(content_patterns=(r"valid\d+", "(unclosed"))

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        rule = ApplicabilityRule()
        with pytest.raises(ValidationError, match="frozen"):
            rule.always = True  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ApplicabilityRule(unknown="x")  # type: ignore[call-arg]


# =============================================================================
# LoadError — 正常系
# =============================================================================


class TestLoadErrorValid:
    """LoadError の正常系を検証。"""

    def test_valid_load_error(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        error = LoadError(source="agents/broken.toml", message="TOML parse error")
        assert error.source == "agents/broken.toml"
        assert error.message == "TOML parse error"

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        error = LoadError(source="x", message="y")
        assert isinstance(error, HachimokuBaseModel)


# =============================================================================
# LoadError — 制約
# =============================================================================


class TestLoadErrorConstraints:
    """LoadError の制約を検証。"""

    def test_empty_source_rejected(self) -> None:
        """空文字列の source がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="source"):
            LoadError(source="", message="error")

    def test_empty_message_rejected(self) -> None:
        """空文字列の message がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="message"):
            LoadError(source="file.toml", message="")

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        error = LoadError(source="x", message="y")
        with pytest.raises(ValidationError, match="frozen"):
            error.source = "changed"  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            LoadError(source="x", message="y", extra="z")  # type: ignore[call-arg]


# =============================================================================
# AgentDefinition — ヘルパー
# =============================================================================


def _valid_agent_data(**overrides: object) -> dict[str, object]:
    """AgentDefinition の最小限有効データを返す。"""
    base: dict[str, object] = {
        "name": "test-agent",
        "description": "A test agent",
        "model": "claude-sonnet-4-5-20250929",
        "output_schema": "scored_issues",
        "system_prompt": "You are a test agent.",
    }
    base.update(overrides)
    return base


# =============================================================================
# AgentDefinition — 正常系
# =============================================================================


class TestAgentDefinitionValid:
    """AgentDefinition の正常系を検証。"""

    def test_valid_agent_definition(self) -> None:
        """全必須フィールド指定でインスタンス生成が成功する。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.name == "test-agent"
        assert agent.description == "A test agent"
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.output_schema == "scored_issues"
        assert agent.system_prompt == "You are a test agent."

    def test_resolved_schema_from_registry(self) -> None:
        """output_schema から SCHEMA_REGISTRY のスキーマ型が解決される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.resolved_schema is ScoredIssues
        assert issubclass(agent.resolved_schema, BaseAgentOutput)

    def test_default_allowed_tools(self) -> None:
        """allowed_tools のデフォルト値は空タプル。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.allowed_tools == ()

    def test_default_applicability(self) -> None:
        """applicability のデフォルトは always=True の ApplicabilityRule。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.applicability.always is True
        assert agent.applicability.file_patterns == ()
        assert agent.applicability.content_patterns == ()

    def test_default_phase(self) -> None:
        """phase のデフォルト値は Phase.MAIN。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.phase == Phase.MAIN

    def test_default_max_turns(self) -> None:
        """max_turns のデフォルト値は None。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.max_turns is None

    def test_explicit_max_turns(self) -> None:
        """max_turns を明示指定できる。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(max_turns=20))
        assert agent.max_turns == 20

    def test_default_timeout(self) -> None:
        """timeout のデフォルト値は None。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert agent.timeout is None

    def test_explicit_timeout(self) -> None:
        """timeout を明示指定できる。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(timeout=600))
        assert agent.timeout == 600

    def test_explicit_phase(self) -> None:
        """phase を明示指定できる。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(phase="early"))
        assert agent.phase == Phase.EARLY

    def test_explicit_allowed_tools(self) -> None:
        """allowed_tools を明示指定できる。"""
        agent = AgentDefinition.model_validate(
            _valid_agent_data(allowed_tools=["tool1", "tool2"])
        )
        assert agent.allowed_tools == ("tool1", "tool2")

    def test_resolved_schema_excluded_from_serialization(self) -> None:
        """resolved_schema が model_dump() から除外される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        dump = agent.model_dump()
        assert "resolved_schema" not in dump

    def test_explicit_applicability(self) -> None:
        """applicability を明示指定できる。"""
        agent = AgentDefinition.model_validate(
            _valid_agent_data(applicability={"file_patterns": ["*.py"]})
        )
        assert agent.applicability.always is False
        assert agent.applicability.file_patterns == ("*.py",)

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        assert isinstance(agent, HachimokuBaseModel)


# =============================================================================
# AgentDefinition — 制約
# =============================================================================


class TestAgentDefinitionConstraints:
    """AgentDefinition の制約を検証。"""

    def test_invalid_name_uppercase(self) -> None:
        """大文字を含む name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            AgentDefinition.model_validate(_valid_agent_data(name="Test-Agent"))

    def test_invalid_name_underscore(self) -> None:
        """アンダースコアを含む name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            AgentDefinition.model_validate(_valid_agent_data(name="test_agent"))

    def test_invalid_name_space(self) -> None:
        """スペースを含む name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            AgentDefinition.model_validate(_valid_agent_data(name="test agent"))

    def test_invalid_name_empty(self) -> None:
        """空文字列の name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            AgentDefinition.model_validate(_valid_agent_data(name=""))

    def test_unknown_schema_raises_error(self) -> None:
        """SCHEMA_REGISTRY に未登録の output_schema でエラーとなる。"""
        with pytest.raises(ValidationError, match="not registered"):
            AgentDefinition.model_validate(
                _valid_agent_data(output_schema="nonexistent")
            )

    def test_non_string_output_schema_raises_error(self) -> None:
        """output_schema が文字列以外の場合にバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="output_schema must be a string"):
            AgentDefinition.model_validate(_valid_agent_data(output_schema=123))

    def test_missing_required_field_name(self) -> None:
        """name 欠損で ValidationError。"""
        data = _valid_agent_data()
        del data["name"]
        with pytest.raises(ValidationError, match="name"):
            AgentDefinition.model_validate(data)

    def test_missing_required_field_description(self) -> None:
        """description 欠損で ValidationError。"""
        data = _valid_agent_data()
        del data["description"]
        with pytest.raises(ValidationError, match="description"):
            AgentDefinition.model_validate(data)

    def test_missing_required_field_output_schema(self) -> None:
        """output_schema 欠損で ValidationError。"""
        data = _valid_agent_data()
        del data["output_schema"]
        with pytest.raises(ValidationError, match="output_schema"):
            AgentDefinition.model_validate(data)

    def test_missing_required_field_model(self) -> None:
        """model 欠損で ValidationError。"""
        data = _valid_agent_data()
        del data["model"]
        with pytest.raises(ValidationError, match="model"):
            AgentDefinition.model_validate(data)

    def test_missing_required_field_system_prompt(self) -> None:
        """system_prompt 欠損で ValidationError。"""
        data = _valid_agent_data()
        del data["system_prompt"]
        with pytest.raises(ValidationError, match="system_prompt"):
            AgentDefinition.model_validate(data)

    def test_name_with_leading_hyphen_accepted(self) -> None:
        """ハイフン先頭の name が許可される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(name="-leading"))
        assert agent.name == "-leading"

    def test_name_with_trailing_hyphen_accepted(self) -> None:
        """ハイフン末尾の name が許可される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(name="trailing-"))
        assert agent.name == "trailing-"

    def test_name_digits_only_accepted(self) -> None:
        """数字のみの name が許可される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(name="123"))
        assert agent.name == "123"

    def test_name_single_char_accepted(self) -> None:
        """1文字の name が許可される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data(name="a"))
        assert agent.name == "a"

    def test_max_turns_zero_rejected(self) -> None:
        """max_turns に 0 を渡すと ValidationError が発生する。"""
        with pytest.raises(ValidationError, match="max_turns"):
            AgentDefinition.model_validate(_valid_agent_data(max_turns=0))

    def test_max_turns_negative_rejected(self) -> None:
        """max_turns に負の値を渡すと ValidationError が発生する。"""
        with pytest.raises(ValidationError, match="max_turns"):
            AgentDefinition.model_validate(_valid_agent_data(max_turns=-1))

    def test_timeout_zero_rejected(self) -> None:
        """timeout に 0 を渡すと ValidationError が発生する。"""
        with pytest.raises(ValidationError, match="timeout"):
            AgentDefinition.model_validate(_valid_agent_data(timeout=0))

    def test_timeout_negative_rejected(self) -> None:
        """timeout に負の値を渡すと ValidationError が発生する。"""
        with pytest.raises(ValidationError, match="timeout"):
            AgentDefinition.model_validate(_valid_agent_data(timeout=-1))

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        with pytest.raises(ValidationError, match="frozen"):
            agent.name = "changed"  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AgentDefinition.model_validate(_valid_agent_data(unknown="x"))

    def test_agent_name_pattern_is_exported(self) -> None:
        """AGENT_NAME_PATTERN 定数がエクスポートされている。"""
        assert AGENT_NAME_PATTERN == r"^[a-z0-9-]+$"


# =============================================================================
# LoadResult — 正常系
# =============================================================================


class TestLoadResultValid:
    """LoadResult の正常系を検証。"""

    def test_valid_load_result(self) -> None:
        """agents + errors 指定で正常作成。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        error = LoadError(source="bad.toml", message="parse error")
        result = LoadResult(agents=(agent,), errors=(error,))
        assert len(result.agents) == 1
        assert result.agents[0].name == "test-agent"
        assert len(result.errors) == 1
        assert result.errors[0].source == "bad.toml"

    def test_default_errors_empty_tuple(self) -> None:
        """errors のデフォルト値は空タプル。"""
        agent = AgentDefinition.model_validate(_valid_agent_data())
        result = LoadResult(agents=(agent,))
        assert result.errors == ()

    def test_empty_agents(self) -> None:
        """空の agents タプルで正常作成。"""
        result = LoadResult(agents=())
        assert result.agents == ()
        assert result.errors == ()

    def test_multiple_agents_and_errors(self) -> None:
        """複数の agents と errors を保持できる。"""
        agent1 = AgentDefinition.model_validate(_valid_agent_data(name="agent-1"))
        agent2 = AgentDefinition.model_validate(_valid_agent_data(name="agent-2"))
        err1 = LoadError(source="a.toml", message="err1")
        err2 = LoadError(source="b.toml", message="err2")
        result = LoadResult(agents=(agent1, agent2), errors=(err1, err2))
        assert len(result.agents) == 2
        assert len(result.errors) == 2

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        result = LoadResult(agents=())
        assert isinstance(result, HachimokuBaseModel)


# =============================================================================
# LoadResult — 制約
# =============================================================================


class TestLoadResultConstraints:
    """LoadResult の制約を検証。"""

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        result = LoadResult(agents=())
        with pytest.raises(ValidationError, match="frozen"):
            result.agents = ()  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            LoadResult(agents=(), extra="z")  # type: ignore[call-arg]


# =============================================================================
# SelectorDefinition — ヘルパー
# =============================================================================


def _valid_selector_data(**overrides: object) -> dict[str, object]:
    """SelectorDefinition の最小限有効データを返す。"""
    base: dict[str, object] = {
        "name": "selector",
        "description": "Agent selector for code review",
        "model": "claudecode:claude-sonnet-4-5",
        "system_prompt": "You are an agent selector.",
    }
    base.update(overrides)
    return base


# =============================================================================
# SelectorDefinition — 正常系
# =============================================================================


class TestSelectorDefinitionValid:
    """SelectorDefinition の正常系を検証。"""

    def test_valid_selector_definition(self) -> None:
        """全必須フィールド指定でインスタンス生成が成功する。"""
        selector = SelectorDefinition.model_validate(_valid_selector_data())
        assert selector.name == "selector"
        assert selector.description == "Agent selector for code review"
        assert selector.model == "claudecode:claude-sonnet-4-5"
        assert selector.system_prompt == "You are an agent selector."

    def test_default_allowed_tools(self) -> None:
        """allowed_tools のデフォルト値は空タプル。"""
        selector = SelectorDefinition.model_validate(_valid_selector_data())
        assert selector.allowed_tools == ()

    def test_explicit_allowed_tools(self) -> None:
        """allowed_tools を明示指定できる。"""
        selector = SelectorDefinition.model_validate(
            _valid_selector_data(allowed_tools=["git_read", "file_read"])
        )
        assert selector.allowed_tools == ("git_read", "file_read")

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        selector = SelectorDefinition.model_validate(_valid_selector_data())
        assert isinstance(selector, HachimokuBaseModel)

    def test_name_accepts_lowercase_and_hyphens(self) -> None:
        """小文字・数字・ハイフンの name が許可される。"""
        selector = SelectorDefinition.model_validate(
            _valid_selector_data(name="my-selector-2")
        )
        assert selector.name == "my-selector-2"


# =============================================================================
# SelectorDefinition — 制約
# =============================================================================


class TestSelectorDefinitionConstraints:
    """SelectorDefinition の制約を検証。"""

    def test_invalid_name_uppercase(self) -> None:
        """大文字を含む name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            SelectorDefinition.model_validate(_valid_selector_data(name="Selector"))

    def test_invalid_name_empty(self) -> None:
        """空文字列の name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            SelectorDefinition.model_validate(_valid_selector_data(name=""))

    def test_missing_required_field_name(self) -> None:
        """name 欠損で ValidationError。"""
        data = _valid_selector_data()
        del data["name"]
        with pytest.raises(ValidationError, match="name"):
            SelectorDefinition.model_validate(data)

    def test_missing_required_field_description(self) -> None:
        """description 欠損で ValidationError。"""
        data = _valid_selector_data()
        del data["description"]
        with pytest.raises(ValidationError, match="description"):
            SelectorDefinition.model_validate(data)

    def test_missing_required_field_model(self) -> None:
        """model 欠損で ValidationError。"""
        data = _valid_selector_data()
        del data["model"]
        with pytest.raises(ValidationError, match="model"):
            SelectorDefinition.model_validate(data)

    def test_missing_required_field_system_prompt(self) -> None:
        """system_prompt 欠損で ValidationError。"""
        data = _valid_selector_data()
        del data["system_prompt"]
        with pytest.raises(ValidationError, match="system_prompt"):
            SelectorDefinition.model_validate(data)

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        selector = SelectorDefinition.model_validate(_valid_selector_data())
        with pytest.raises(ValidationError, match="frozen"):
            selector.name = "changed"  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SelectorDefinition.model_validate(_valid_selector_data(unknown="x"))

    def test_output_schema_field_rejected(self) -> None:
        """AgentDefinition 固有の output_schema が extra=forbid で拒否される。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SelectorDefinition.model_validate(
                _valid_selector_data(output_schema="scored_issues")
            )

    def test_applicability_field_rejected(self) -> None:
        """AgentDefinition 固有の applicability が extra=forbid で拒否される。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SelectorDefinition.model_validate(
                _valid_selector_data(applicability={"always": True})
            )

    def test_phase_field_rejected(self) -> None:
        """AgentDefinition 固有の phase が extra=forbid で拒否される。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SelectorDefinition.model_validate(_valid_selector_data(phase="main"))
