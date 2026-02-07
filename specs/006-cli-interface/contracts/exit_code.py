"""ExitCode contract — CLI 終了コードの定義。

FR-CLI-003: レビュー結果と入力状態に応じた終了コード。
"""

from enum import IntEnum


class ExitCode(IntEnum):
    """CLI 終了コード。

    0-3 は EngineResult.exit_code からの直接変換。
    4 は CLI 層で直接判定される入力エラー。
    """

    SUCCESS = 0
    CRITICAL = 1
    IMPORTANT = 2
    EXECUTION_ERROR = 3
    INPUT_ERROR = 4
