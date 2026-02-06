"""重大度（Severity）の定義。

FR-DM-001: Critical > Important > Suggestion > Nitpick の4段階順序。
"""

from __future__ import annotations

from enum import StrEnum


SEVERITY_ORDER: dict[str, int] = {
    "Nitpick": 0,
    "Suggestion": 1,
    "Important": 2,
    "Critical": 3,
}


class Severity(StrEnum):
    """レビュー問題の重大度。PascalCase で内部保持。

    順序関係: Critical > Important > Suggestion > Nitpick
    比較演算は SEVERITY_ORDER に基づくカスタム実装を提供する。
    """

    CRITICAL = "Critical"
    IMPORTANT = "Important"
    SUGGESTION = "Suggestion"
    NITPICK = "Nitpick"

    def _order(self) -> int:
        return SEVERITY_ORDER[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order() < other._order()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order() <= other._order()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order() > other._order()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order() >= other._order()
