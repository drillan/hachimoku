"""ExitCode — 終了コードの定義。

FR-CLI-003: レビュー結果と入力状態に応じた終了コード。
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """プロセス終了コード。

    0-3 はレビューエンジンの結果に対応し、4 は CLI 層固有の入力エラー。
    """

    SUCCESS = 0
    CRITICAL = 1
    IMPORTANT = 2
    EXECUTION_ERROR = 3
    INPUT_ERROR = 4
