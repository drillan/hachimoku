"""重大度（Severity）の定義。

FR-DM-001: Critical > Important > Suggestion > Nitpick の4段階順序。
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


SEVERITY_ORDER: Final[Mapping[str, int]] = MappingProxyType(
    {
        "Nitpick": 0,
        "Suggestion": 1,
        "Important": 2,
        "Critical": 3,
    }
)

EXIT_CODE_SUCCESS: Final[int] = 0
EXIT_CODE_CRITICAL: Final[int] = 1
EXIT_CODE_IMPORTANT: Final[int] = 2


class Severity(StrEnum):
    """レビュー問題の重大度。PascalCase で内部保持。

    順序関係: Critical > Important > Suggestion > Nitpick
    比較演算は SEVERITY_ORDER に基づくカスタム実装を提供する。
    非 Severity 型との比較は TypeError を送出する。
    """

    CRITICAL = "Critical"
    IMPORTANT = "Important"
    SUGGESTION = "Suggestion"
    NITPICK = "Nitpick"

    def _order(self) -> int:
        """SEVERITY_ORDER から重大度の順序値を取得する。"""
        return SEVERITY_ORDER[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            raise TypeError(
                f"'<' not supported between instances of 'Severity' and '{type(other).__name__}'"
            )
        return self._order() < other._order()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            raise TypeError(
                f"'<=' not supported between instances of 'Severity' and '{type(other).__name__}'"
            )
        return self._order() <= other._order()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            raise TypeError(
                f"'>' not supported between instances of 'Severity' and '{type(other).__name__}'"
            )
        return self._order() > other._order()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            raise TypeError(
                f"'>=' not supported between instances of 'Severity' and '{type(other).__name__}'"
            )
        return self._order() >= other._order()


def determine_exit_code(max_severity: Severity | None) -> int:
    """最大重大度から終了コードを決定する。

    Args:
        max_severity: レビュー結果の最大重大度。問題なしの場合は None。

    Returns:
        終了コード (0, 1, 2)。

    Raises:
        ValueError: 未知の Severity 値が渡された場合。
    """
    if max_severity is None:
        return EXIT_CODE_SUCCESS

    severity_to_exit_code: dict[Severity, int] = {
        Severity.CRITICAL: EXIT_CODE_CRITICAL,
        Severity.IMPORTANT: EXIT_CODE_IMPORTANT,
        Severity.SUGGESTION: EXIT_CODE_SUCCESS,
        Severity.NITPICK: EXIT_CODE_SUCCESS,
    }

    if max_severity not in severity_to_exit_code:
        raise ValueError(f"Unknown Severity value: {max_severity}")

    return severity_to_exit_code[max_severity]
