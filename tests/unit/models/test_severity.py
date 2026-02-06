"""Severity と SEVERITY_ORDER のテスト。

FR-DM-001: 重大度を4段階で定義し、順序関係を持つ。
"""

import pytest

from hachimoku.models.severity import SEVERITY_ORDER, Severity


class TestSeverityEnumValues:
    """Severity 列挙値の定義を検証。"""

    def test_has_four_members(self) -> None:
        """4つの列挙値が定義されている。"""
        assert len(Severity) == 4

    def test_critical_value(self) -> None:
        assert Severity.CRITICAL == "Critical"
        assert Severity.CRITICAL.value == "Critical"

    def test_important_value(self) -> None:
        assert Severity.IMPORTANT == "Important"
        assert Severity.IMPORTANT.value == "Important"

    def test_suggestion_value(self) -> None:
        assert Severity.SUGGESTION == "Suggestion"
        assert Severity.SUGGESTION.value == "Suggestion"

    def test_nitpick_value(self) -> None:
        assert Severity.NITPICK == "Nitpick"
        assert Severity.NITPICK.value == "Nitpick"

    def test_invalid_value_raises_error(self) -> None:
        """定義外の値は ValueError を発生させる。"""
        with pytest.raises(ValueError):
            Severity("Invalid")

    def test_is_str_enum(self) -> None:
        """Severity は StrEnum のサブクラスである。"""
        assert isinstance(Severity.CRITICAL, str)


class TestSeverityOrder:
    """SEVERITY_ORDER 定数の定義を検証。"""

    def test_order_mapping(self) -> None:
        """Nitpick=0 < Suggestion=1 < Important=2 < Critical=3。"""
        assert SEVERITY_ORDER == {
            "Nitpick": 0,
            "Suggestion": 1,
            "Important": 2,
            "Critical": 3,
        }

    def test_critical_is_highest(self) -> None:
        assert SEVERITY_ORDER["Critical"] == max(SEVERITY_ORDER.values())

    def test_nitpick_is_lowest(self) -> None:
        assert SEVERITY_ORDER["Nitpick"] == min(SEVERITY_ORDER.values())


class TestSeverityComparison:
    """Severity の順序比較（SEVERITY_ORDER 基準）を検証。"""

    def test_critical_gt_important(self) -> None:
        assert Severity.CRITICAL > Severity.IMPORTANT

    def test_critical_gt_suggestion(self) -> None:
        assert Severity.CRITICAL > Severity.SUGGESTION

    def test_critical_gt_nitpick(self) -> None:
        assert Severity.CRITICAL > Severity.NITPICK

    def test_important_gt_suggestion(self) -> None:
        assert Severity.IMPORTANT > Severity.SUGGESTION

    def test_important_gt_nitpick(self) -> None:
        assert Severity.IMPORTANT > Severity.NITPICK

    def test_suggestion_gt_nitpick(self) -> None:
        assert Severity.SUGGESTION > Severity.NITPICK

    def test_nitpick_lt_suggestion(self) -> None:
        assert Severity.NITPICK < Severity.SUGGESTION

    def test_nitpick_lt_important(self) -> None:
        assert Severity.NITPICK < Severity.IMPORTANT

    def test_nitpick_lt_critical(self) -> None:
        assert Severity.NITPICK < Severity.CRITICAL

    def test_le_same_value(self) -> None:
        assert Severity.CRITICAL <= Severity.CRITICAL

    def test_le_lower_value(self) -> None:
        assert Severity.IMPORTANT <= Severity.CRITICAL

    def test_ge_same_value(self) -> None:
        assert Severity.CRITICAL >= Severity.CRITICAL

    def test_ge_higher_value(self) -> None:
        assert Severity.CRITICAL >= Severity.IMPORTANT

    def test_not_gt_same_value(self) -> None:
        assert not (Severity.CRITICAL > Severity.CRITICAL)

    def test_not_lt_same_value(self) -> None:
        assert not (Severity.CRITICAL < Severity.CRITICAL)

    def test_eq_same_value(self) -> None:
        assert Severity.CRITICAL == Severity.CRITICAL

    def test_ne_different_value(self) -> None:
        assert Severity.CRITICAL != Severity.NITPICK


class TestSeverityComparisonWithNonSeverity:
    """非 Severity 型との比較で NotImplemented が返されることを検証。"""

    def test_lt_with_string_returns_not_implemented(self) -> None:
        result = Severity.CRITICAL.__lt__("Critical")
        assert result is NotImplemented

    def test_le_with_string_returns_not_implemented(self) -> None:
        result = Severity.CRITICAL.__le__("Critical")
        assert result is NotImplemented

    def test_gt_with_string_returns_not_implemented(self) -> None:
        result = Severity.CRITICAL.__gt__("Critical")
        assert result is NotImplemented

    def test_ge_with_string_returns_not_implemented(self) -> None:
        result = Severity.CRITICAL.__ge__("Critical")
        assert result is NotImplemented

    def test_lt_with_int_returns_not_implemented(self) -> None:
        result = Severity.CRITICAL.__lt__(3)
        assert result is NotImplemented

    def test_gt_with_int_returns_not_implemented(self) -> None:
        result = Severity.CRITICAL.__gt__(0)
        assert result is NotImplemented
