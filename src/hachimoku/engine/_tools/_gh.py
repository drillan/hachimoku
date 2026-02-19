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
        ("pr", "diff"),
        ("issue", "view"),
        ("api",),
    }
)
"""読み取り専用の gh サブコマンドパターン。"""

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120
"""subprocess.run のタイムアウト秒数。"""


def run_gh(args: list[str]) -> str:
    """gh コマンドを読み取り専用で実行する。

    Args:
        args: gh サブコマンドと引数のリスト（例: ["pr", "view", "123"]）。

    Returns:
        gh コマンドの stdout 出力。

    Raises:
        ValueError: コマンドパターンがホワイトリスト外の場合、
            または api サブコマンドで GET 以外の HTTP メソッドが指定された場合。
        RuntimeError: gh コマンドが非ゼロで終了した場合、
            gh が PATH 上に見つからない場合、
            またはタイムアウトした場合。
    """
    if not args:
        raise ValueError("gh command is empty")

    # 2語パターン（"pr view", "pr diff", "issue view"）または 1語パターン（"api"）で検証
    pattern_2 = (args[0], args[1]) if len(args) >= 2 else None
    pattern_1 = (args[0],)

    if pattern_2 not in ALLOWED_GH_PATTERNS and pattern_1 not in ALLOWED_GH_PATTERNS:
        display = " ".join(args[:2]) if len(args) >= 2 else args[0]
        raise ValueError(f"gh command '{display}' is not allowed")

    # api サブコマンドは GET メソッドのみ許可
    if args[0] == "api":
        _validate_api_method(args)

    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "gh command not found. Ensure GitHub CLI is installed and available in PATH."
        ) from None
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"gh command timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s"
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh command failed: {e.stderr}") from e

    return result.stdout


_IMPLICIT_POST_FLAGS: Final[frozenset[str]] = frozenset(
    {"-f", "--field", "-F", "--raw-field", "--input"}
)
"""gh api で暗黙的に POST メソッドを使用するフラグ。"""


def _validate_api_method(args: list[str]) -> None:
    """api サブコマンドの HTTP メソッドが GET であることを検証する。

    Args:
        args: gh サブコマンドと引数のリスト。

    Raises:
        ValueError: GET 以外の HTTP メソッドが指定されている場合、
            -X / --method フラグに値が指定されていない場合、
            または暗黙的に POST を引き起こすフラグが含まれている場合。
    """
    for i, arg in enumerate(args):
        if arg in ("-X", "--method"):
            if i + 1 >= len(args):
                raise ValueError(f"gh api: missing value for {arg}")
            method = args[i + 1].upper()
            if method != "GET":
                raise ValueError(f"gh api only allows GET method, got '{method}'")

        # --method=VALUE 形式の検出
        if arg.startswith("--method="):
            method = arg.split("=", 1)[1].upper()
            if method != "GET":
                raise ValueError(f"gh api only allows GET method, got '{method}'")

        # 暗黙的 POST フラグの検出
        if arg in _IMPLICIT_POST_FLAGS:
            raise ValueError(
                f"gh api: flag '{arg}' causes implicit POST, which is not allowed"
            )
