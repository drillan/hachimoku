"""ExitCode IntEnum のテスト。

FR-CLI-003: レビュー結果と入力状態に応じた終了コード。
contracts/exit_code.py の仕様に準拠。
"""

from enum import IntEnum

import pytest

from hachimoku.models.exit_code import ExitCode


class TestExitCodeValues:
    """ExitCode IntEnum の値を検証する。"""

    def test_success_is_zero(self) -> None:
        assert ExitCode.SUCCESS == 0

    def test_critical_is_one(self) -> None:
        assert ExitCode.CRITICAL == 1

    def test_important_is_two(self) -> None:
        assert ExitCode.IMPORTANT == 2

    def test_execution_error_is_three(self) -> None:
        assert ExitCode.EXECUTION_ERROR == 3

    def test_input_error_is_four(self) -> None:
        assert ExitCode.INPUT_ERROR == 4

    def test_has_five_members(self) -> None:
        """5つの列挙値が定義されている。"""
        assert len(ExitCode) == 5


class TestExitCodeIsIntEnum:
    """ExitCode が IntEnum であることを検証する。"""

    def test_is_int_subclass(self) -> None:
        """ExitCode メンバーは int のインスタンスである。"""
        assert isinstance(ExitCode.SUCCESS, int)

    def test_is_int_enum_subclass(self) -> None:
        """ExitCode は IntEnum のサブクラスである。"""
        assert issubclass(ExitCode, IntEnum)

    def test_equality_with_int(self) -> None:
        """int 値との等価比較が可能である。"""
        assert ExitCode.SUCCESS == 0
        assert ExitCode.CRITICAL == 1
        assert ExitCode.EXECUTION_ERROR == 3

    def test_can_be_used_as_process_exit_code(self) -> None:
        """int() で変換可能である（sys.exit() に渡せる）。"""
        assert int(ExitCode.SUCCESS) == 0
        assert int(ExitCode.INPUT_ERROR) == 4


class TestExitCodeFromEngineResult:
    """EngineResult.exit_code (0-3) からの変換を検証する。"""

    def test_engine_result_zero_converts_to_success(self) -> None:
        assert ExitCode(0) is ExitCode.SUCCESS

    def test_engine_result_one_converts_to_critical(self) -> None:
        assert ExitCode(1) is ExitCode.CRITICAL

    def test_engine_result_two_converts_to_important(self) -> None:
        assert ExitCode(2) is ExitCode.IMPORTANT

    def test_engine_result_three_converts_to_execution_error(self) -> None:
        assert ExitCode(3) is ExitCode.EXECUTION_ERROR

    def test_direct_cast_from_int(self) -> None:
        """ExitCode(n) で int から変換可能。"""
        for value in range(5):
            code = ExitCode(value)
            assert isinstance(code, ExitCode)
            assert code == value


class TestExitCodeInvalidValues:
    """無効な値での ExitCode 構築を検証する。"""

    def test_negative_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            ExitCode(-1)

    def test_out_of_range_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            ExitCode(5)

    def test_large_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            ExitCode(999)
