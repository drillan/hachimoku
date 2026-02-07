"""pydantic-ai ツール関数のテスト。

FR-RE-016: ToolCatalog のツール関数（git_read, gh_read, file_read）。
R-005: ツール関数の設計。
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from hachimoku.engine._tools._file import list_directory, read_file
from hachimoku.engine._tools._gh import run_gh
from hachimoku.engine._tools._git import ALLOWED_GIT_SUBCOMMANDS, run_git


# =============================================================================
# run_git
# =============================================================================


class TestRunGitWhitelist:
    """run_git のホワイトリスト検証。"""

    def test_allowed_subcommand_executes(self) -> None:
        """ホワイトリスト内のサブコマンドが実行される。"""
        with patch("hachimoku.engine._tools._git.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="output")
            result = run_git(["diff", "main"])
            assert result == "output"
            mock_run.assert_called_once()

    def test_disallowed_subcommand_raises_error(self) -> None:
        """ホワイトリスト外のサブコマンドで ValueError を送出する。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_git(["commit", "-m", "test"])

    def test_push_rejected(self) -> None:
        """書き込み系コマンド push が拒否される。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_git(["push"])

    def test_add_rejected(self) -> None:
        """書き込み系コマンド add が拒否される。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_git(["add", "."])

    def test_empty_args_raises_error(self) -> None:
        """空のコマンド引数で ValueError を送出する。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_git([])

    def test_all_whitelisted_subcommands_accepted(self) -> None:
        """全ホワイトリストサブコマンドが許可される。"""
        with patch("hachimoku.engine._tools._git.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="ok")
            for cmd in ALLOWED_GIT_SUBCOMMANDS:
                run_git([cmd])


class TestRunGitExecution:
    """run_git のコマンド実行を検証。"""

    def test_command_failure_raises_runtime_error(self) -> None:
        """コマンド失敗時に RuntimeError を送出する。"""
        with patch("hachimoku.engine._tools._git.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, ["git", "diff"], stderr="fatal error"
            )
            with pytest.raises(RuntimeError, match="git command failed"):
                run_git(["diff", "main"])

    def test_passes_args_to_git_with_timeout(self) -> None:
        """引数が git コマンドに timeout 付きで渡される。"""
        with patch("hachimoku.engine._tools._git.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="")
            run_git(["log", "--oneline", "-5"])
            mock_run.assert_called_once_with(
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

    def test_git_not_found_raises_runtime_error(self) -> None:
        """git が PATH 上にない場合 RuntimeError を送出する。"""
        with patch("hachimoku.engine._tools._git.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("No such file: 'git'")
            with pytest.raises(RuntimeError, match="git command not found"):
                run_git(["status"])


# =============================================================================
# run_gh
# =============================================================================


class TestRunGhWhitelist:
    """run_gh のホワイトリスト検証。"""

    def test_pr_view_allowed(self) -> None:
        """'pr view' パターンが許可される。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="pr output")
            result = run_gh(["pr", "view", "123"])
            assert result == "pr output"

    def test_pr_diff_allowed(self) -> None:
        """'pr diff' パターンが許可される。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="diff output")
            result = run_gh(["pr", "diff", "123"])
            assert result == "diff output"

    def test_issue_view_allowed(self) -> None:
        """'issue view' パターンが許可される。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="issue output")
            result = run_gh(["issue", "view", "42"])
            assert result == "issue output"

    def test_api_allowed(self) -> None:
        """'api' パターンが許可される。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="api output")
            result = run_gh(["api", "repos/owner/repo"])
            assert result == "api output"

    def test_pr_comment_rejected(self) -> None:
        """書き込み系コマンド 'pr comment' が拒否される。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_gh(["pr", "comment", "123", "--body", "test"])

    def test_pr_close_rejected(self) -> None:
        """書き込み系コマンド 'pr close' が拒否される。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_gh(["pr", "close", "123"])

    def test_pr_diff_rejected_was_now_allowed(self) -> None:
        """'pr diff' は読み取り専用なので許可される（C-1 修正確認）。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="diff")
            run_gh(["pr", "diff", "42"])  # 例外が出ないことを確認

    def test_single_pr_arg_rejected(self) -> None:
        """'pr' 単一引数が拒否される（I-5 境界ケース）。"""
        with pytest.raises(ValueError, match="not allowed"):
            run_gh(["pr"])

    def test_empty_args_raises_error(self) -> None:
        """空のコマンド引数で ValueError を送出する。"""
        with pytest.raises(ValueError, match="empty"):
            run_gh([])


class TestRunGhApiMethodValidation:
    """run_gh の api サブコマンド HTTP メソッド検証（C-2 対応）。"""

    def test_api_get_method_allowed(self) -> None:
        """api に -X GET は許可される。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="ok")
            run_gh(["api", "-X", "GET", "repos/owner/repo"])

    def test_api_post_method_rejected(self) -> None:
        """api に -X POST は拒否される。"""
        with pytest.raises(ValueError, match="GET"):
            run_gh(["api", "-X", "POST", "repos/owner/repo"])

    def test_api_delete_method_rejected(self) -> None:
        """api に -X DELETE は拒否される。"""
        with pytest.raises(ValueError, match="GET"):
            run_gh(["api", "-X", "DELETE", "repos/owner/repo"])

    def test_api_method_flag_long_form_rejected(self) -> None:
        """api に --method POST は拒否される。"""
        with pytest.raises(ValueError, match="GET"):
            run_gh(["api", "--method", "PATCH", "repos/owner/repo"])

    def test_api_without_method_flag_allowed(self) -> None:
        """api にメソッドフラグなし（デフォルト GET）は許可される。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.return_value = Mock(stdout="ok")
            run_gh(["api", "repos/owner/repo"])


class TestRunGhExecution:
    """run_gh のコマンド実行を検証。"""

    def test_command_failure_raises_runtime_error(self) -> None:
        """コマンド失敗時に RuntimeError を送出する。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, ["gh", "pr", "view"], stderr="not found"
            )
            with pytest.raises(RuntimeError, match="gh command failed"):
                run_gh(["pr", "view", "999"])

    def test_gh_not_found_raises_runtime_error(self) -> None:
        """gh が PATH 上にない場合 RuntimeError を送出する。"""
        with patch("hachimoku.engine._tools._gh.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("No such file: 'gh'")
            with pytest.raises(RuntimeError, match="gh command not found"):
                run_gh(["pr", "view", "1"])


# =============================================================================
# read_file
# =============================================================================


class TestReadFile:
    """read_file ツール関数のテスト。"""

    def test_reads_existing_file(self, tmp_path: Path) -> None:
        """既存ファイルの内容を読み込む。"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("file content", encoding="utf-8")
        result = read_file(str(test_file))
        assert result == "file content"

    def test_reads_utf8_file(self, tmp_path: Path) -> None:
        """UTF-8 ファイルを正しく読み込む。"""
        test_file = tmp_path / "日本語.txt"
        test_file.write_text("日本語のテスト", encoding="utf-8")
        result = read_file(str(test_file))
        assert result == "日本語のテスト"

    def test_nonexistent_file_raises_error(self) -> None:
        """存在しないファイルで FileNotFoundError を送出する。"""
        with pytest.raises(FileNotFoundError):
            read_file("/nonexistent/file.txt")

    def test_directory_path_raises_error(self, tmp_path: Path) -> None:
        """ディレクトリパスで FileNotFoundError を送出する（S-7）。"""
        with pytest.raises(FileNotFoundError):
            read_file(str(tmp_path))


# =============================================================================
# list_directory
# =============================================================================


class TestListDirectory:
    """list_directory ツール関数のテスト。"""

    def test_lists_files_without_pattern(self, tmp_path: Path) -> None:
        """パターンなしで全ファイルをリストする。"""
        (tmp_path / "file1.py").write_text("")
        (tmp_path / "file2.txt").write_text("")
        result = list_directory(str(tmp_path))
        assert "file1.py" in result
        assert "file2.txt" in result

    def test_filters_by_glob_pattern(self, tmp_path: Path) -> None:
        """glob パターンでフィルタリングする。"""
        (tmp_path / "test.py").write_text("")
        (tmp_path / "README.md").write_text("")
        result = list_directory(str(tmp_path), pattern="*.py")
        assert "test.py" in result
        assert "README.md" not in result

    def test_nonexistent_directory_raises_error(self) -> None:
        """存在しないディレクトリで NotADirectoryError を送出する。"""
        with pytest.raises(NotADirectoryError):
            list_directory("/nonexistent/dir")

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        """空ディレクトリで空文字列を返す。"""
        result = list_directory(str(tmp_path))
        assert result == ""

    def test_excludes_subdirectories(self, tmp_path: Path) -> None:
        """サブディレクトリはリストに含まれない（S-6）。"""
        (tmp_path / "file.py").write_text("")
        (tmp_path / "subdir").mkdir()
        result = list_directory(str(tmp_path))
        assert "file.py" in result
        assert "subdir" not in result
