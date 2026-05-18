"""readonly_allowlist の構造テスト。SP3 の git/gh 書き込み禁止 hook が消費する。"""

from __future__ import annotations

from hachimoku.security.readonly_allowlist import (
    ALLOWED_GH_PATTERNS,
    ALLOWED_GIT_SUBCOMMANDS,
    IMPLICIT_POST_FLAGS,
)


class TestReadonlyAllowlist:
    def test_git_subcommands_are_read_only(self) -> None:
        assert ALLOWED_GIT_SUBCOMMANDS == frozenset(
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

    def test_git_allowlist_excludes_mutating_subcommands(self) -> None:
        for mutating in ("push", "commit", "reset", "checkout", "restore", "clean"):
            assert mutating not in ALLOWED_GIT_SUBCOMMANDS

    def test_gh_patterns_are_read_only(self) -> None:
        assert ALLOWED_GH_PATTERNS == frozenset(
            {("pr", "view"), ("pr", "diff"), ("issue", "view"), ("api",)}
        )

    def test_implicit_post_flags(self) -> None:
        assert IMPLICIT_POST_FLAGS == frozenset(
            {"-f", "--field", "-F", "--raw-field", "--input"}
        )
