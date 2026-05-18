"""changeset 計算のテスト。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hachimoku.review.changeset import ChangeSet, ChangeSetError, compute_changeset
from hachimoku.review.target import CommitTarget, DiffTarget, FileTarget


def _init_repo(path: Path) -> None:
    """テスト用 git リポジトリを初期化する。"""
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=path, check=True, capture_output=True
    )


def _commit_all(path: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message], cwd=path, check=True, capture_output=True
    )
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return rev.stdout.strip()


class TestComputeChangesetDiff:
    def test_diff_mode_collects_changed_basenames_and_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "base.py").write_text("x = 1\n")
        _commit_all(tmp_path, "base")
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "feature.py").write_text("y = 2  # NEWLINE\n")
        _commit_all(tmp_path, "feature")
        monkeypatch.chdir(tmp_path)

        result = compute_changeset(DiffTarget(base_branch="main"))

        assert isinstance(result, ChangeSet)
        assert "feature.py" in result.changed_basenames
        assert "NEWLINE" in result.content


class TestComputeChangesetCommit:
    def test_commit_mode_uses_ref_range(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "a.py").write_text("a = 1\n")
        first = _commit_all(tmp_path, "first")
        (tmp_path / "b.py").write_text("b = 2\n")
        second = _commit_all(tmp_path, "second")
        monkeypatch.chdir(tmp_path)

        result = compute_changeset(CommitTarget(from_ref=first, to_ref=second))

        assert "b.py" in result.changed_basenames
        assert "a.py" not in result.changed_basenames


class TestComputeChangesetFile:
    def test_file_mode_reads_file_contents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "target.py").write_text("z = 3  # MARKER\n")
        monkeypatch.chdir(tmp_path)

        result = compute_changeset(FileTarget(paths=("target.py",)))

        assert "target.py" in result.changed_basenames
        assert "MARKER" in result.content


class TestComputeChangesetErrors:
    def test_diff_mode_outside_git_repo_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)  # git リポジトリではない
        with pytest.raises(ChangeSetError):
            compute_changeset(DiffTarget(base_branch="main"))
