"""git_read カテゴリのツール関数。

pydantic-ai エージェントが git コマンドを読み取り専用で実行する。
ホワイトリスト検証により書き込み系コマンドを防止する。
"""

from __future__ import annotations

import subprocess
from typing import Final

ALLOWED_GIT_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {
        "diff",
        "log",
        "show",
        "status",
        "merge-base",
        "rev-parse",
        "branch",
        "ls-files",
    }
)
"""読み取り専用の git サブコマンド。"""

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120
"""subprocess.run のタイムアウト秒数。"""


def run_git(args: list[str]) -> str:
    """git コマンドを読み取り専用で実行する。

    Args:
        args: git サブコマンドと引数のリスト（例: ["diff", "main"]）。

    Returns:
        git コマンドの stdout 出力。

    Raises:
        ValueError: args[0] がホワイトリスト外のサブコマンドの場合。
        RuntimeError: git コマンドが非ゼロで終了した場合、
            git が PATH 上に見つからない場合、
            またはタイムアウトした場合。
    """
    if not args or args[0] not in ALLOWED_GIT_SUBCOMMANDS:
        subcmd = args[0] if args else "(empty)"
        raise ValueError(f"git subcommand '{subcmd}' is not allowed")

    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "git command not found. Ensure git is installed and available in PATH."
        ) from None
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"git command timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s"
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git command failed: {e.stderr}") from e

    return result.stdout
