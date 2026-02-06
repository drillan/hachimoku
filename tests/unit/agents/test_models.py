"""Phase, PHASE_ORDER, ApplicabilityRule, LoadError のテスト。

T004: Phase StrEnum — 列挙値(early/main/final)、PHASE_ORDER ソート順検証
T005: ApplicabilityRule — デフォルト値、正規表現バリデーション、frozen、extra=forbid
T007: LoadError — フィールドバリデーション、frozen、extra=forbid

NOTE: T006 (AgentDefinition) / T007 の LoadResult は AgentDefinition と密結合のため次 Issue で実装。
"""

import pytest
from pydantic import ValidationError

from hachimoku.agents.models import (
    PHASE_ORDER,
    ApplicabilityRule,
    LoadError,
    Phase,
)
from hachimoku.models._base import HachimokuBaseModel


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
