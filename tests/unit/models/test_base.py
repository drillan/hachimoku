"""HachimokuBaseModel と共通ユーティリティのテスト。

FR-DM-009: 全モデルは extra="forbid" の厳格モードで動作する。
FR-DM-010: normalize_enum_value による StrEnum ケース正規化。
"""

import pytest
from pydantic import ValidationError

from hachimoku.models._base import HachimokuBaseModel, normalize_enum_value
from hachimoku.models.severity import Severity


class SampleModel(HachimokuBaseModel):
    """テスト用のサブクラス。"""

    name: str
    value: int


class TestHachimokuBaseModelExtraForbid:
    """extra="forbid" により未定義フィールドが拒否されることを検証。"""

    def test_valid_fields_accepted(self) -> None:
        """定義済みフィールドのみでインスタンス生成が成功する。"""
        model = SampleModel(name="test", value=42)
        assert model.name == "test"
        assert model.value == 42

    def test_extra_field_rejected(self) -> None:
        """未定義フィールドを渡すと ValidationError が発生する。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            SampleModel(name="test", value=42, unknown_field="should fail")  # type: ignore[call-arg]

    def test_multiple_extra_fields_rejected(self) -> None:
        """複数の未定義フィールドでも ValidationError が発生する。"""
        with pytest.raises(ValidationError):
            SampleModel(name="test", value=42, extra1="a", extra2="b")  # type: ignore[call-arg]


class TestHachimokuBaseModelFrozen:
    """frozen=True により構築後のフィールド変更が禁止されることを検証。"""

    def test_field_assignment_rejected(self) -> None:
        """構築後のフィールド代入で ValidationError が発生する。"""
        model = SampleModel(name="test", value=42)
        with pytest.raises(ValidationError, match="frozen"):
            model.name = "changed"

    def test_field_assignment_with_invalid_value_rejected(self) -> None:
        """不正な値での代入も ValidationError が発生する。"""
        model = SampleModel(name="test", value=42)
        with pytest.raises(ValidationError, match="frozen"):
            model.value = -999  # type: ignore[assignment]


class TestNormalizeEnumValue:
    """normalize_enum_value の動作を検証。

    FR-DM-010: StrEnum のケース非依存正規化。
    """

    def test_lowercase_normalized_to_pascalcase(self) -> None:
        """小文字入力が PascalCase に正規化される。"""
        assert normalize_enum_value("critical", Severity) == "Critical"

    def test_uppercase_normalized_to_pascalcase(self) -> None:
        """大文字入力が PascalCase に正規化される。"""
        assert normalize_enum_value("IMPORTANT", Severity) == "Important"

    def test_mixed_case_normalized(self) -> None:
        """混合ケースが正規化される。"""
        assert normalize_enum_value("sUgGeStIoN", Severity) == "Suggestion"

    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("critical", "Critical"),
            ("important", "Important"),
            ("suggestion", "Suggestion"),
            ("nitpick", "Nitpick"),
        ],
    )
    def test_all_severity_values(self, input_str: str, expected: str) -> None:
        """全 Severity 値について正規化を検証。"""
        assert normalize_enum_value(input_str, Severity) == expected

    def test_already_correct_case_passthrough(self) -> None:
        """既に正しいケースの値はそのまま返される。"""
        assert normalize_enum_value("Critical", Severity) == "Critical"

    def test_invalid_string_passthrough(self) -> None:
        """マッチしない文字列はそのまま返される。"""
        assert normalize_enum_value("invalid", Severity) == "invalid"

    def test_non_string_passthrough(self) -> None:
        """非 str 型はそのまま返される。"""
        assert normalize_enum_value(42, Severity) == 42

    def test_none_passthrough(self) -> None:
        """None はそのまま返される。"""
        assert normalize_enum_value(None, Severity) is None
