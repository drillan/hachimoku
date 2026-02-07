"""gh_read カテゴリのツール関数。

pydantic-ai エージェントが gh CLI を読み取り専用で実行する。
ホワイトリスト検証により書き込み系コマンドを防止する。
"""

from __future__ import annotations

import subprocess
from typing import Final

ALLOWED_GH_PATTERNS: Final[frozenset[tuple[str, ...]]] = frozenset(
    {
        ("pr", "view"),
        ("issue", "view"),
        ("api",),
    }
)
"""読み取り専用の gh サブコマンドパターン。"""


def run_gh(args: list[str]) -> str:
    """gh コマンドを読み取り専用で実行する。

    Args:
        args: gh サブコマンドと引数のリスト（例: ["pr", "view", "123"]）。

    Returns:
        gh コマンドの stdout 出力。

    Raises:
        ValueError: コマンドパターンがホワイトリスト外の場合。
        RuntimeError: gh コマンドが非ゼロで終了した場合。
    """
    if not args:
        raise ValueError("gh command is empty")

    # 2語パターン（"pr view", "issue view"）または 1語パターン（"api"）で検証
    pattern_2 = (args[0], args[1]) if len(args) >= 2 else None
    pattern_1 = (args[0],)

    if pattern_2 not in ALLOWED_GH_PATTERNS and pattern_1 not in ALLOWED_GH_PATTERNS:
        display = " ".join(args[:2]) if len(args) >= 2 else args[0]
        raise ValueError(f"gh command '{display}' is not allowed")

    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh command failed: {e.stderr}") from e

    return result.stdout
