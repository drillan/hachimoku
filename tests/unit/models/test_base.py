"""HachimokuBaseModel のテスト。

FR-DM-009: 全モデルは extra="forbid" の厳格モードで動作する。
"""

import pytest
from pydantic import ValidationError

from hachimoku.models._base import HachimokuBaseModel


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
