"""設定モデルのテスト。

T003: OutputFormat enum
T004: AgentConfig model
T005: HachimokuConfig model
T006: SelectorConfig model (US5, FR-CF-010)
"""

import pytest
from pydantic import ValidationError

from hachimoku.models.config import (
    AgentConfig,
    AggregationConfig,
    HachimokuConfig,
    OutputFormat,
    SelectorConfig,
)


# =============================================================================
# T003: OutputFormat
# =============================================================================


class TestOutputFormat:
    """OutputFormat StrEnum のテスト。"""

    def test_markdown_value(self) -> None:
        """MARKDOWN メンバーの値が "markdown" であること。"""
        assert OutputFormat.MARKDOWN == "markdown"
        assert OutputFormat.MARKDOWN.value == "markdown"

    def test_json_value(self) -> None:
        """JSON メンバーの値が "json" であること。"""
        assert OutputFormat.JSON == "json"
        assert OutputFormat.JSON.value == "json"

    def test_from_string_markdown(self) -> None:
        """文字列 "markdown" から OutputFormat を構築できること。"""
        assert OutputFormat("markdown") is OutputFormat.MARKDOWN

    def test_from_string_json(self) -> None:
        """文字列 "json" から OutputFormat を構築できること。"""
        assert OutputFormat("json") is OutputFormat.JSON

    def test_invalid_value_raises(self) -> None:
        """無効な値で ValueError が発生すること。"""
        with pytest.raises(ValueError, match="is not a valid"):
            OutputFormat("xml")

    def test_member_count(self) -> None:
        """メンバーが 2 つであること。"""
        assert len(OutputFormat) == 2


# =============================================================================
# T004: AgentConfig
# =============================================================================


class TestAgentConfigDefaults:
    """AgentConfig のデフォルト値テスト。"""

    def test_default_enabled(self) -> None:
        """enabled のデフォルトが True であること。"""
        config = AgentConfig()
        assert config.enabled is True

    def test_default_model(self) -> None:
        """model のデフォルトが None であること。"""
        config = AgentConfig()
        assert config.model is None

    def test_default_timeout(self) -> None:
        """timeout のデフォルトが None であること。"""
        config = AgentConfig()
        assert config.timeout is None

    def test_default_max_turns(self) -> None:
        """max_turns のデフォルトが None であること。"""
        config = AgentConfig()
        assert config.max_turns is None


class TestAgentConfigValidation:
    """AgentConfig のバリデーションテスト。"""

    def test_model_empty_string_rejected(self) -> None:
        """model に空文字列を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="model"):
            AgentConfig(model="")

    def test_model_valid_string_accepted(self) -> None:
        """model に有効な文字列を渡すと設定されること。"""
        config = AgentConfig(model="haiku")
        assert config.model == "haiku"

    def test_timeout_zero_rejected(self) -> None:
        """timeout に 0 を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="timeout"):
            AgentConfig(timeout=0)

    def test_timeout_negative_rejected(self) -> None:
        """timeout に負の値を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="timeout"):
            AgentConfig(timeout=-1)

    def test_timeout_positive_accepted(self) -> None:
        """timeout に正の値を渡すと設定されること。"""
        config = AgentConfig(timeout=60)
        assert config.timeout == 60

    def test_max_turns_zero_rejected(self) -> None:
        """max_turns に 0 を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="max_turns"):
            AgentConfig(max_turns=0)

    def test_max_turns_negative_rejected(self) -> None:
        """max_turns に負の値を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="max_turns"):
            AgentConfig(max_turns=-1)

    def test_max_turns_positive_accepted(self) -> None:
        """max_turns に正の値を渡すと設定されること。"""
        config = AgentConfig(max_turns=5)
        assert config.max_turns == 5

    def test_extra_field_rejected(self) -> None:
        """未知のキーを渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AgentConfig(unknown_key="value")  # type: ignore[call-arg]

    def test_enabled_string_true_rejected(self) -> None:
        """enabled に文字列 "true" を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="enabled"):
            AgentConfig(enabled="true")  # type: ignore[arg-type]

    def test_enabled_int_one_rejected(self) -> None:
        """enabled に整数 1 を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="enabled"):
            AgentConfig(enabled=1)  # type: ignore[arg-type]


class TestAgentConfigFrozen:
    """AgentConfig の frozen=True テスト。"""

    def test_field_assignment_rejected(self) -> None:
        """構築後のフィールド代入で ValidationError が発生すること。"""
        config = AgentConfig()
        with pytest.raises(ValidationError, match="frozen"):
            config.enabled = False  # type: ignore[misc]


# =============================================================================
# T005: HachimokuConfig
# =============================================================================


class TestHachimokuConfigDefaults:
    """HachimokuConfig のデフォルト値テスト。"""

    def test_construct_with_defaults_only(self) -> None:
        """デフォルト値のみでインスタンス構築できること。"""
        config = HachimokuConfig()
        assert config is not None

    def test_default_model(self) -> None:
        assert HachimokuConfig().model == "claudecode:claude-opus-4-6"

    def test_default_timeout(self) -> None:
        assert HachimokuConfig().timeout == 600

    def test_default_max_turns(self) -> None:
        assert HachimokuConfig().max_turns == 30

    def test_default_parallel(self) -> None:
        """parallel のデフォルトが True であること。"""
        assert HachimokuConfig().parallel is True

    def test_default_base_branch(self) -> None:
        assert HachimokuConfig().base_branch == "main"

    def test_default_output_format(self) -> None:
        assert HachimokuConfig().output_format is OutputFormat.MARKDOWN

    def test_default_save_reviews(self) -> None:
        assert HachimokuConfig().save_reviews is True

    def test_default_show_cost(self) -> None:
        assert HachimokuConfig().show_cost is False

    def test_default_max_files_per_review(self) -> None:
        assert HachimokuConfig().max_files_per_review == 100

    def test_default_agents(self) -> None:
        assert HachimokuConfig().agents == {}


class TestHachimokuConfigValidation:
    """HachimokuConfig のバリデーションテスト。"""

    def test_timeout_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timeout"):
            HachimokuConfig(timeout=0)

    def test_timeout_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timeout"):
            HachimokuConfig(timeout=-1)

    def test_max_turns_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_turns"):
            HachimokuConfig(max_turns=0)

    def test_max_turns_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_turns"):
            HachimokuConfig(max_turns=-1)

    def test_max_files_per_review_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_files_per_review"):
            HachimokuConfig(max_files_per_review=0)

    def test_max_files_per_review_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_files_per_review"):
            HachimokuConfig(max_files_per_review=-1)

    def test_model_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            HachimokuConfig(model="")

    def test_base_branch_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError, match="base_branch"):
            HachimokuConfig(base_branch="")

    def test_output_format_invalid_rejected(self) -> None:
        """output_format に無効な値を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="output_format"):
            HachimokuConfig(output_format="xml")  # type: ignore[arg-type]

    def test_parallel_non_boolean_rejected(self) -> None:
        """parallel に非 boolean 文字列を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="parallel"):
            HachimokuConfig(parallel="abc")  # type: ignore[arg-type]

    def test_parallel_string_true_rejected(self) -> None:
        """parallel に文字列 "true" を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="parallel"):
            HachimokuConfig(parallel="true")  # type: ignore[arg-type]

    def test_parallel_int_one_rejected(self) -> None:
        """parallel に整数 1 を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="parallel"):
            HachimokuConfig(parallel=1)  # type: ignore[arg-type]

    def test_save_reviews_string_rejected(self) -> None:
        """save_reviews に文字列を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="save_reviews"):
            HachimokuConfig(save_reviews="yes")  # type: ignore[arg-type]

    def test_show_cost_int_rejected(self) -> None:
        """show_cost に整数を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="show_cost"):
            HachimokuConfig(show_cost=0)  # type: ignore[arg-type]


class TestHachimokuConfigAgents:
    """HachimokuConfig の agents フィールドテスト。"""

    def test_valid_agent_name(self) -> None:
        """有効なエージェント名が受け入れられること。"""
        config = HachimokuConfig(agents={"code-reviewer": AgentConfig(enabled=False)})
        assert config.agents["code-reviewer"].enabled is False

    def test_valid_agent_name_with_numbers(self) -> None:
        """数字を含むエージェント名が受け入れられること。"""
        config = HachimokuConfig(agents={"agent-v2": AgentConfig(model="haiku")})
        assert config.agents["agent-v2"].model == "haiku"

    def test_invalid_agent_name_uppercase_rejected(self) -> None:
        """大文字を含むエージェント名で ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="CodeReviewer"):
            HachimokuConfig(agents={"CodeReviewer": AgentConfig()})

    def test_invalid_agent_name_underscore_rejected(self) -> None:
        """アンダースコアを含むエージェント名で ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="code_reviewer"):
            HachimokuConfig(agents={"code_reviewer": AgentConfig()})

    def test_invalid_agent_name_space_rejected(self) -> None:
        """スペースを含むエージェント名で ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="code reviewer"):
            HachimokuConfig(agents={"code reviewer": AgentConfig()})


class TestHachimokuConfigExtraForbid:
    """HachimokuConfig の extra="forbid" テスト。"""

    def test_unknown_key_rejected(self) -> None:
        """未知のキーを渡すと ValidationError が発生し、キー名を含むこと。"""
        with pytest.raises(ValidationError, match="unknown_field"):
            HachimokuConfig(unknown_field="value")  # type: ignore[call-arg]


class TestHachimokuConfigFrozen:
    """HachimokuConfig の frozen=True テスト。"""

    def test_field_assignment_rejected(self) -> None:
        """構築後のフィールド代入で ValidationError が発生すること。"""
        config = HachimokuConfig()
        with pytest.raises(ValidationError, match="frozen"):
            config.model = "opus"  # type: ignore[misc]


# =============================================================================
# T006: SelectorConfig (US5, FR-CF-010)
# =============================================================================


class TestSelectorConfigDefaults:
    """SelectorConfig のデフォルト値テスト。"""

    def test_default_model(self) -> None:
        """model のデフォルトが None であること。"""
        assert SelectorConfig().model is None

    def test_default_timeout(self) -> None:
        """timeout のデフォルトが None であること。"""
        assert SelectorConfig().timeout is None

    def test_default_max_turns(self) -> None:
        """max_turns のデフォルトが None であること。"""
        assert SelectorConfig().max_turns is None

    def test_default_referenced_content_max_chars(self) -> None:
        """referenced_content_max_chars のデフォルトが 5000 であること。"""
        assert SelectorConfig().referenced_content_max_chars == 5000

    def test_default_convention_files(self) -> None:
        """convention_files のデフォルトが CLAUDE.md と config.toml であること。Issue #187."""
        config = SelectorConfig()
        assert config.convention_files == ("CLAUDE.md", ".hachimoku/config.toml")

    def test_default_convention_files_matches_prefetch(self) -> None:
        """convention_files のデフォルトが _prefetch.DEFAULT_CONVENTION_FILES と同値であること。"""
        from hachimoku.engine._prefetch import DEFAULT_CONVENTION_FILES

        assert SelectorConfig().convention_files == DEFAULT_CONVENTION_FILES


class TestSelectorConfigValidation:
    """SelectorConfig のバリデーションテスト (FR-CF-004)。"""

    def test_model_empty_string_rejected(self) -> None:
        """model に空文字列を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="model"):
            SelectorConfig(model="")

    def test_model_valid_string_accepted(self) -> None:
        """model に有効な文字列を渡すと設定されること。"""
        assert SelectorConfig(model="haiku").model == "haiku"

    def test_timeout_zero_rejected(self) -> None:
        """timeout に 0 を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="timeout"):
            SelectorConfig(timeout=0)

    def test_timeout_negative_rejected(self) -> None:
        """timeout に負の値を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="timeout"):
            SelectorConfig(timeout=-1)

    def test_timeout_positive_accepted(self) -> None:
        """timeout に正の値を渡すと設定されること。"""
        assert SelectorConfig(timeout=60).timeout == 60

    def test_max_turns_zero_rejected(self) -> None:
        """max_turns に 0 を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="max_turns"):
            SelectorConfig(max_turns=0)

    def test_max_turns_negative_rejected(self) -> None:
        """max_turns に負の値を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="max_turns"):
            SelectorConfig(max_turns=-1)

    def test_max_turns_positive_accepted(self) -> None:
        """max_turns に正の値を渡すと設定されること。"""
        assert SelectorConfig(max_turns=5).max_turns == 5

    def test_referenced_content_max_chars_zero_rejected(self) -> None:
        """referenced_content_max_chars に 0 を渡すと ValidationError。"""
        with pytest.raises(ValidationError, match="referenced_content_max_chars"):
            SelectorConfig(referenced_content_max_chars=0)

    def test_referenced_content_max_chars_negative_rejected(self) -> None:
        """referenced_content_max_chars に負の値を渡すと ValidationError。"""
        with pytest.raises(ValidationError, match="referenced_content_max_chars"):
            SelectorConfig(referenced_content_max_chars=-1)

    def test_referenced_content_max_chars_positive_accepted(self) -> None:
        """referenced_content_max_chars に正の値を渡すと設定されること。"""
        assert (
            SelectorConfig(
                referenced_content_max_chars=8000
            ).referenced_content_max_chars
            == 8000
        )

    def test_convention_files_custom(self) -> None:
        """convention_files にカスタム値を渡すと設定されること。Issue #187."""
        custom = ("README.md", "pyproject.toml")
        config = SelectorConfig(convention_files=custom)
        assert config.convention_files == custom

    def test_convention_files_empty_accepted(self) -> None:
        """convention_files に空タプルを渡すと設定されること。Issue #187."""
        config = SelectorConfig(convention_files=())
        assert config.convention_files == ()

    def test_convention_files_empty_string_element_rejected(self) -> None:
        """convention_files に空文字列の要素を含むと ValidationError が発生すること。Issue #187."""
        with pytest.raises(ValidationError, match="convention_files"):
            SelectorConfig(convention_files=("CLAUDE.md", ""))

    def test_extra_field_rejected(self) -> None:
        """未知のキーを渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SelectorConfig(unknown_key="value")  # type: ignore[call-arg]


class TestSelectorConfigFrozen:
    """SelectorConfig の frozen=True テスト。"""

    def test_field_assignment_rejected(self) -> None:
        """構築後のフィールド代入で ValidationError が発生すること。"""
        config = SelectorConfig()
        with pytest.raises(ValidationError, match="frozen"):
            config.model = "opus"  # type: ignore[misc]


class TestHachimokuConfigSelector:
    """HachimokuConfig の selector フィールドテスト。"""

    def test_default_selector(self) -> None:
        """selector のデフォルトが SelectorConfig() であること。"""
        config = HachimokuConfig()
        assert config.selector == SelectorConfig()

    def test_selector_from_dict(self) -> None:
        """辞書から selector を構築できること。"""
        config = HachimokuConfig(selector={"model": "haiku"})  # type: ignore[arg-type]
        assert config.selector.model == "haiku"


# =============================================================================
# AggregationConfig (Issue #152)
# =============================================================================


class TestAggregationConfigDefaults:
    """AggregationConfig のデフォルト値テスト。"""

    def test_default_enabled(self) -> None:
        """enabled のデフォルトが True であること。"""
        assert AggregationConfig().enabled is True

    def test_default_model(self) -> None:
        """model のデフォルトが None であること。"""
        assert AggregationConfig().model is None

    def test_default_timeout(self) -> None:
        """timeout のデフォルトが None であること。"""
        assert AggregationConfig().timeout is None

    def test_default_max_turns(self) -> None:
        """max_turns のデフォルトが None であること。"""
        assert AggregationConfig().max_turns is None


class TestAggregationConfigValidation:
    """AggregationConfig のバリデーションテスト。"""

    def test_enabled_true_accepted(self) -> None:
        assert AggregationConfig(enabled=True).enabled is True

    def test_enabled_false_accepted(self) -> None:
        assert AggregationConfig(enabled=False).enabled is False

    def test_enabled_non_bool_rejected(self) -> None:
        """StrictBool のため文字列 "true" は拒否される。"""
        with pytest.raises(ValidationError, match="enabled"):
            AggregationConfig(enabled="true")  # type: ignore[arg-type]

    def test_model_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError, match="model"):
            AggregationConfig(model="")

    def test_model_valid_string_accepted(self) -> None:
        assert AggregationConfig(model="haiku").model == "haiku"

    def test_timeout_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timeout"):
            AggregationConfig(timeout=0)

    def test_timeout_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timeout"):
            AggregationConfig(timeout=-1)

    def test_timeout_positive_accepted(self) -> None:
        assert AggregationConfig(timeout=60).timeout == 60

    def test_max_turns_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_turns"):
            AggregationConfig(max_turns=0)

    def test_max_turns_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_turns"):
            AggregationConfig(max_turns=-1)

    def test_max_turns_positive_accepted(self) -> None:
        assert AggregationConfig(max_turns=5).max_turns == 5

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AggregationConfig(unknown_key="value")  # type: ignore[call-arg]


class TestAggregationConfigFrozen:
    """AggregationConfig の frozen=True テスト。"""

    def test_field_assignment_rejected(self) -> None:
        config = AggregationConfig()
        with pytest.raises(ValidationError, match="frozen"):
            config.enabled = False  # type: ignore[misc]


class TestHachimokuConfigAggregation:
    """HachimokuConfig の aggregation フィールドテスト。"""

    def test_default_aggregation(self) -> None:
        """aggregation のデフォルトが AggregationConfig() であること。"""
        config = HachimokuConfig()
        assert config.aggregation == AggregationConfig()

    def test_aggregation_from_dict(self) -> None:
        """辞書から aggregation を構築できること。"""
        config = HachimokuConfig(aggregation={"enabled": False})  # type: ignore[arg-type]
        assert config.aggregation.enabled is False

    def test_aggregation_with_model(self) -> None:
        """aggregation.model を指定できること。"""
        config = HachimokuConfig(aggregation={"model": "opus"})  # type: ignore[arg-type]
        assert config.aggregation.model == "opus"
