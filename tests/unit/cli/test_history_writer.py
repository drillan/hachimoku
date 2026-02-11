"""_history_writer モジュールのテスト。

FR-025: レビュー結果の JSONL 自動蓄積。
FR-026: JSONL レコード形式。
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hachimoku.cli._history_writer import (
    GitInfoError,
    HistoryWriteError,
    _build_record,
    _resolve_jsonl_path,
    get_branch_name,
    get_commit_hash,
    save_review_history,
)
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.history import (
    DiffReviewRecord,
    FileReviewRecord,
    PRReviewRecord,
)
from hachimoku.models.report import ReviewReport, ReviewSummary

VALID_COMMIT_HASH = "a" * 40
VALID_BRANCH_NAME = "feature/test"
VALID_REVIEWED_AT = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)
VALID_SUMMARY = ReviewSummary(
    total_issues=0,
    max_severity=None,
    total_elapsed_time=0.0,
)


def _make_report() -> ReviewReport:
    """テスト用の空 ReviewReport を生成。"""
    return ReviewReport(
        results=[],
        summary=VALID_SUMMARY,
    )


# =============================================================================
# _resolve_jsonl_path
# =============================================================================


class TestResolveJsonlPath:
    """_resolve_jsonl_path のファイルパス解決テスト。"""

    def test_diff_target_returns_diff_jsonl(self, tmp_path: Path) -> None:
        """DiffTarget → diff.jsonl。"""
        target = DiffTarget(base_branch="main")
        result = _resolve_jsonl_path(tmp_path, target)
        assert result == tmp_path / "diff.jsonl"

    def test_pr_target_returns_pr_number_jsonl(self, tmp_path: Path) -> None:
        """PRTarget(pr_number=123) → pr-123.jsonl。"""
        target = PRTarget(pr_number=123)
        result = _resolve_jsonl_path(tmp_path, target)
        assert result == tmp_path / "pr-123.jsonl"

    def test_file_target_returns_files_jsonl(self, tmp_path: Path) -> None:
        """FileTarget → files.jsonl。"""
        target = FileTarget(paths=("src/main.py",))
        result = _resolve_jsonl_path(tmp_path, target)
        assert result == tmp_path / "files.jsonl"


# =============================================================================
# _build_record
# =============================================================================


class TestBuildRecord:
    """_build_record の ReviewHistoryRecord 構築テスト。"""

    def test_diff_target_builds_diff_record(self) -> None:
        """DiffTarget → DiffReviewRecord が構築される。"""
        target = DiffTarget(base_branch="main")
        report = _make_report()
        record = _build_record(
            target, report, VALID_COMMIT_HASH, VALID_BRANCH_NAME, VALID_REVIEWED_AT
        )
        assert isinstance(record, DiffReviewRecord)
        assert record.review_mode == "diff"
        assert record.commit_hash == VALID_COMMIT_HASH
        assert record.branch_name == VALID_BRANCH_NAME
        assert record.reviewed_at == VALID_REVIEWED_AT
        assert record.results == report.results
        assert record.summary == report.summary

    def test_pr_target_builds_pr_record(self) -> None:
        """PRTarget → PRReviewRecord が構築される。"""
        target = PRTarget(pr_number=42)
        report = _make_report()
        record = _build_record(
            target, report, VALID_COMMIT_HASH, VALID_BRANCH_NAME, VALID_REVIEWED_AT
        )
        assert isinstance(record, PRReviewRecord)
        assert record.review_mode == "pr"
        assert record.pr_number == 42
        assert record.commit_hash == VALID_COMMIT_HASH
        assert record.branch_name == VALID_BRANCH_NAME

    def test_file_target_builds_file_record(self) -> None:
        """FileTarget → FileReviewRecord が構築される。"""
        target = FileTarget(paths=("src/a.py", "src/b.py"))
        report = _make_report()
        record = _build_record(target, report, "", "", VALID_REVIEWED_AT)
        assert isinstance(record, FileReviewRecord)
        assert record.review_mode == "file"
        assert record.file_paths == frozenset({"src/a.py", "src/b.py"})
        assert record.reviewed_at == VALID_REVIEWED_AT

    def test_file_target_working_directory_is_absolute(self) -> None:
        """FileReviewRecord の working_directory は絶対パス。"""
        target = FileTarget(paths=("src/a.py",))
        report = _make_report()
        record = _build_record(target, report, "", "", VALID_REVIEWED_AT)
        assert isinstance(record, FileReviewRecord)
        assert record.working_directory.startswith("/")


# =============================================================================
# get_commit_hash
# =============================================================================


class TestGetCommitHash:
    """get_commit_hash の git コマンド実行テスト。"""

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_returns_40char_hex_hash(self, mock_run: MagicMock) -> None:
        """正常時に40文字のコミットハッシュを返す。"""
        mock_run.return_value.stdout = VALID_COMMIT_HASH + "\n"
        result = get_commit_hash()
        assert result == VALID_COMMIT_HASH

    @patch(
        "hachimoku.cli._history_writer.subprocess.run", side_effect=FileNotFoundError
    )
    def test_git_not_found_raises_git_info_error(self, _mock: object) -> None:
        """git 未インストール時に GitInfoError。"""
        with pytest.raises(GitInfoError, match="git command not found"):
            get_commit_hash()

    @patch(
        "hachimoku.cli._history_writer.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
    )
    def test_git_timeout_raises_git_info_error(self, _mock: object) -> None:
        """git タイムアウト時に GitInfoError。"""
        with pytest.raises(GitInfoError, match="timed out"):
            get_commit_hash()

    @patch(
        "hachimoku.cli._history_writer.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=128, cmd="git", stderr="fatal: not a git repository"
        ),
    )
    def test_git_failure_raises_git_info_error(self, _mock: object) -> None:
        """git コマンド失敗時に GitInfoError。"""
        with pytest.raises(GitInfoError, match="git rev-parse HEAD failed"):
            get_commit_hash()


# =============================================================================
# get_branch_name
# =============================================================================


class TestGetBranchName:
    """get_branch_name の git コマンド実行テスト。"""

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_returns_branch_name(self, mock_run: MagicMock) -> None:
        """正常時にブランチ名を返す。"""
        mock_run.return_value.stdout = "feature/auth\n"
        result = get_branch_name()
        assert result == "feature/auth"

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_detached_head_returns_HEAD(self, mock_run: MagicMock) -> None:
        """detached HEAD 時に 'HEAD' を返す。"""
        mock_run.return_value.stdout = "HEAD\n"
        result = get_branch_name()
        assert result == "HEAD"

    @patch(
        "hachimoku.cli._history_writer.subprocess.run", side_effect=FileNotFoundError
    )
    def test_git_not_found_raises_git_info_error(self, _mock: object) -> None:
        """git 未インストール時に GitInfoError。"""
        with pytest.raises(GitInfoError, match="git command not found"):
            get_branch_name()

    @patch(
        "hachimoku.cli._history_writer.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
    )
    def test_git_timeout_raises_git_info_error(self, _mock: object) -> None:
        """git タイムアウト時に GitInfoError。"""
        with pytest.raises(GitInfoError, match="timed out"):
            get_branch_name()

    @patch(
        "hachimoku.cli._history_writer.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=128, cmd="git", stderr="fatal: not a git repository"
        ),
    )
    def test_git_failure_raises_git_info_error(self, _mock: object) -> None:
        """git コマンド失敗時に GitInfoError。"""
        with pytest.raises(
            GitInfoError, match="git rev-parse --abbrev-ref HEAD failed"
        ):
            get_branch_name()


# =============================================================================
# save_review_history
# =============================================================================


def _mock_git_subprocess(mock_run: MagicMock) -> None:
    """subprocess.run モックに git コマンドの応答を設定する。"""

    def _side_effect(
        cmd: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if cmd == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=VALID_COMMIT_HASH + "\n", stderr=""
            )
        if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=VALID_BRANCH_NAME + "\n", stderr=""
            )
        raise ValueError(f"Unexpected git command: {cmd}")

    mock_run.side_effect = _side_effect


class TestSaveReviewHistory:
    """save_review_history の統合テスト。"""

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_diff_appends_to_diff_jsonl(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """diff モードで diff.jsonl に追記される。"""
        _mock_git_subprocess(mock_run)
        target = DiffTarget(base_branch="main")
        report = _make_report()

        result = save_review_history(tmp_path, target, report)

        assert result == tmp_path / "diff.jsonl"
        assert result.exists()
        lines = result.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["review_mode"] == "diff"
        assert data["commit_hash"] == VALID_COMMIT_HASH
        assert data["branch_name"] == VALID_BRANCH_NAME

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_pr_appends_to_pr_number_jsonl(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """PR モードで pr-{number}.jsonl に追記される。"""
        _mock_git_subprocess(mock_run)
        target = PRTarget(pr_number=42)
        report = _make_report()

        result = save_review_history(tmp_path, target, report)

        assert result == tmp_path / "pr-42.jsonl"
        data = json.loads(result.read_text().strip())
        assert data["review_mode"] == "pr"
        assert data["pr_number"] == 42

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_file_appends_to_files_jsonl(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """file モードで files.jsonl に追記される。"""
        target = FileTarget(paths=("src/a.py",))
        report = _make_report()

        result = save_review_history(tmp_path, target, report)

        assert result == tmp_path / "files.jsonl"
        data = json.loads(result.read_text().strip())
        assert data["review_mode"] == "file"
        # file モードでは git コマンドが呼ばれないことを検証
        mock_run.assert_not_called()

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_appends_to_existing_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """2回呼び出しで2行追記される。"""
        _mock_git_subprocess(mock_run)
        target = DiffTarget(base_branch="main")
        report = _make_report()

        save_review_history(tmp_path, target, report)
        save_review_history(tmp_path, target, report)

        lines = (tmp_path / "diff.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert data["review_mode"] == "diff"

    def test_reviews_dir_not_exist_raises_history_write_error(
        self, tmp_path: Path
    ) -> None:
        """reviews/ ディレクトリ不在で HistoryWriteError。"""
        target = FileTarget(paths=("src/a.py",))
        report = _make_report()
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(HistoryWriteError, match="does not exist"):
            save_review_history(nonexistent, target, report)

    @patch("hachimoku.cli._history_writer.subprocess.run")
    def test_jsonl_is_valid_json_per_line(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """JSONL の各行が独立した有効な JSON オブジェクト。"""
        _mock_git_subprocess(mock_run)
        target = DiffTarget(base_branch="main")
        report = _make_report()

        save_review_history(tmp_path, target, report)

        content = (tmp_path / "diff.jsonl").read_text()
        # 末尾に改行がある
        assert content.endswith("\n")
        for line in content.strip().splitlines():
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
            assert "review_mode" in parsed
            assert "reviewed_at" in parsed

    def test_io_error_raises_history_write_error(self, tmp_path: Path) -> None:
        """ファイル書き込み時の OSError が HistoryWriteError に変換される。"""
        target = FileTarget(paths=("src/a.py",))
        report = _make_report()

        # 書き込み先を読み取り専用ディレクトリにして OSError を誘発
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        with pytest.raises(HistoryWriteError, match="Failed to write review history"):
            save_review_history(readonly_dir, target, report)

        # クリーンアップ
        readonly_dir.chmod(0o755)
