"""git / gh の読取専用許可リスト。

旧 engine/_tools/_git.py・_gh.py から抽出した中立モジュール。
SP3 のサブエージェント frontmatter hook（block-git-mutations.sh）が
この定義を唯一の正として参照する。
"""

from __future__ import annotations

from typing import Final

ALLOWED_GIT_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {
        "diff",
        "grep",
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

ALLOWED_GH_PATTERNS: Final[frozenset[tuple[str, ...]]] = frozenset(
    {
        ("pr", "view"),
        ("pr", "diff"),
        ("issue", "view"),
        ("api",),
    }
)
"""読み取り専用の gh サブコマンドパターン。"""

IMPLICIT_POST_FLAGS: Final[frozenset[str]] = frozenset(
    {"-f", "--field", "-F", "--raw-field", "--input"}
)
"""gh api で暗黙的に POST メソッドを使用するフラグ。GET 限定検証で deny する。"""
