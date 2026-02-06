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
