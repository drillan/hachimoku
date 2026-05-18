"""block-git-mutations.sh の allow/deny テスト。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hachimoku.security.readonly_allowlist import ALLOWED_GIT_SUBCOMMANDS

_SCRIPT = Path(__file__).parents[3] / "plugin" / "scripts" / "block-git-mutations.sh"


def _run_hook(command: str) -> int:
    """hook スクリプトに PreToolUse 入力を渡し、終了コードを返す。"""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
    )
    return result.returncode


class TestBlockGitMutations:
    @pytest.mark.parametrize(
        "command",
        [
            "git diff",
            "git log --oneline",
            "git show HEAD",
            "git status",
            "gh pr view 123",
            "gh pr diff 123",
            "ls -la",  # git/gh 以外はすべて許可
            "cat file.py",
        ],
    )
    def test_allows_read_only_and_non_git(self, command: str) -> None:
        assert _run_hook(command) == 0

    @pytest.mark.parametrize(
        "command",
        [
            "git push",
            "git commit -m x",
            "git reset --hard",
            "git checkout .",
            "git restore .",
            "git clean -fd",
            "git branch -D feature",
            "gh pr close 1",
            "gh pr merge 1",
            "  git push",  # 先頭スペースで判定をすり抜けさせない
            "\tgit push",  # 先頭タブも同様
            "GIT_AUTHOR_NAME=x git commit -m y",  # env プレフィックスは deny
            "gh api --method DELETE /endpoint",  # 任意 HTTP メソッドは deny
        ],
    )
    def test_denies_git_gh_mutations(self, command: str) -> None:
        assert _run_hook(command) == 2

    @pytest.mark.parametrize(
        "command",
        [
            "git diff && git push",  # パイプ/連結は deny 側に倒す
            "git diff; git commit",
            "bash -c 'git push'",
        ],
    )
    def test_denies_compound_commands(self, command: str) -> None:
        assert _run_hook(command) == 2

    def test_allowlist_matches_python_definition(self) -> None:
        # スクリプト内 git 許可リストが readonly_allowlist.py と一致すること（drift 検出）
        text = _SCRIPT.read_text()
        for sub in ALLOWED_GIT_SUBCOMMANDS:
            assert sub in text, f"script missing allowed subcommand: {sub}"
