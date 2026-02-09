"""ContentResolver のテスト。

Issue #129: エンジンが diff を事前解決して全エージェントのインストラクションに埋め込む。
ターゲットタイプに応じてレビュー対象コンテンツを事前解決する。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hachimoku.engine._resolver import ContentResolveError, resolve_content
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


# =============================================================================
# ContentResolveError
# =============================================================================


class TestContentResolveError:
    """ContentResolveError の型テスト。"""

    def test_inherits_exception(self) -> None:
        """Exception を継承している。"""
        assert issubclass(ContentResolveError, Exception)

    def test_preserves_message(self) -> None:
        """エラーメッセージが保持される。"""
        err = ContentResolveError("git merge-base failed")
        assert str(err) == "git merge-base failed"


# =============================================================================
# resolve_content — DiffTarget
# =============================================================================


class TestResolveContentDiff:
    """resolve_content の DiffTarget テスト。"""

    async def test_returns_diff_text(self) -> None:
        """正常系: git merge-base + git diff の結果を返す。"""
        target = DiffTarget(base_branch="main")
        fake_diff = "diff --git a/file.py b/file.py\n+added line"

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            cmd_args = args
            if "merge-base" in cmd_args:
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"abc123\n", b"")
            else:
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (fake_diff.encode(), b"")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await resolve_content(target)

        assert result == fake_diff

    async def test_empty_diff_returns_empty_string(self) -> None:
        """空 diff は正常値（空文字列）。"""
        target = DiffTarget(base_branch="main")

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            if "merge-base" in args:
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"abc123\n", b"")
            else:
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"", b"")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await resolve_content(target)

        assert result == ""

    async def test_merge_base_failure_raises_error(self) -> None:
        """git merge-base 失敗時に ContentResolveError を送出する。"""
        target = DiffTarget(base_branch="nonexistent-branch")

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate.return_value = (
                b"",
                b"fatal: Not a valid object name",
            )
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="merge-base"):
                await resolve_content(target)

    async def test_diff_failure_raises_error(self) -> None:
        """git diff 失敗時に ContentResolveError を送出する。"""
        target = DiffTarget(base_branch="main")

        call_count = 0

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            mock_proc = AsyncMock()
            if call_count == 1:  # merge-base
                mock_proc.returncode = 0
                mock_proc.communicate.return_value = (b"abc123\n", b"")
            else:  # diff
                mock_proc.returncode = 1
                mock_proc.communicate.return_value = (b"", b"fatal: bad revision")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="diff"):
                await resolve_content(target)

    async def test_git_not_found_raises_error(self) -> None:
        """git コマンド未検出時に ContentResolveError を送出する。"""
        target = DiffTarget(base_branch="main")

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("git not found"),
        ):
            with pytest.raises(ContentResolveError, match="not found"):
                await resolve_content(target)

    async def test_subprocess_timeout_raises_error(self) -> None:
        """subprocess タイムアウト時に ContentResolveError を送出する。"""
        target = DiffTarget(base_branch="main")

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            mock_proc.kill = MagicMock()  # kill() は同期メソッド
            mock_proc.communicate.side_effect = asyncio.TimeoutError()
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="timed out"):
                await resolve_content(target)

    async def test_subprocess_timeout_kills_process(self) -> None:
        """タイムアウト時にプロセスが kill される。"""
        target = DiffTarget(base_branch="main")

        mock_proc = AsyncMock()
        mock_proc.kill = MagicMock()  # kill() は同期メソッド
        mock_proc.communicate.side_effect = asyncio.TimeoutError()

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="timed out"):
                await resolve_content(target)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_called_once()

    async def test_merge_base_empty_output_raises_error(self) -> None:
        """git merge-base が空文字を返した場合 ContentResolveError を送出する。"""
        target = DiffTarget(base_branch="main")

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (b"", b"")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="empty output"):
                await resolve_content(target)

    async def test_merge_base_stripped_value_passed_to_diff(self) -> None:
        """merge-base の strip 済み値が git diff に渡される。"""
        target = DiffTarget(base_branch="main")
        calls: list[tuple[object, ...]] = []

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            calls.append(args)
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            if "merge-base" in args:
                mock_proc.communicate.return_value = (b"abc123\n", b"")
            else:
                mock_proc.communicate.return_value = (b"diff output", b"")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await resolve_content(target)

        assert len(calls) == 2
        diff_call = calls[1]
        assert diff_call == ("git", "diff", "abc123")

    async def test_non_utf8_stdout_raises_error(self) -> None:
        """stdout に非 UTF-8 バイトが含まれる場合 ContentResolveError を送出する。"""
        target = PRTarget(pr_number=42)

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (b"\xff\xfe invalid", b"")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="non-UTF-8"):
                await resolve_content(target)

    async def test_exception_chain_preserved(self) -> None:
        """元の例外が __cause__ として保持される。"""
        target = DiffTarget(base_branch="main")

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("git not found"),
        ):
            with pytest.raises(ContentResolveError) as exc_info:
                await resolve_content(target)

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, FileNotFoundError)


# =============================================================================
# resolve_content — PRTarget
# =============================================================================


class TestResolveContentPR:
    """resolve_content の PRTarget テスト。"""

    async def test_returns_pr_diff(self) -> None:
        """正常系: gh pr diff の結果を返す。"""
        target = PRTarget(pr_number=42)
        fake_diff = "diff --git a/pr.py b/pr.py\n+pr change"

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = (fake_diff.encode(), b"")
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            result = await resolve_content(target)

        assert result == fake_diff

    async def test_gh_failure_raises_error(self) -> None:
        """gh pr diff 失敗時に ContentResolveError を送出する。"""
        target = PRTarget(pr_number=999)

        async def mock_subprocess(*args: object, **kwargs: object) -> AsyncMock:
            mock_proc = AsyncMock()
            mock_proc.returncode = 1
            mock_proc.communicate.return_value = (
                b"",
                b"Could not resolve to a PullRequest",
            )
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="gh pr diff"):
                await resolve_content(target)

    async def test_gh_not_found_raises_error(self) -> None:
        """gh コマンド未検出時に ContentResolveError を送出する。"""
        target = PRTarget(pr_number=42)

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("gh not found"),
        ):
            with pytest.raises(ContentResolveError, match="not found"):
                await resolve_content(target)


# =============================================================================
# resolve_content — FileTarget
# =============================================================================


class TestResolveContentFile:
    """resolve_content の FileTarget テスト。"""

    async def test_single_file(self, tmp_path: Path) -> None:
        """正常系: 単一ファイルの内容を返す。"""
        file = tmp_path / "main.py"
        file.write_text("print('hello')", encoding="utf-8")
        target = FileTarget(paths=(str(file),))

        result = await resolve_content(target)

        assert "print('hello')" in result

    async def test_multiple_files_with_headers(self, tmp_path: Path) -> None:
        """正常系: 複数ファイルがヘッダー付きで結合される。"""
        file_a = tmp_path / "a.py"
        file_a.write_text("content_a", encoding="utf-8")
        file_b = tmp_path / "b.py"
        file_b.write_text("content_b", encoding="utf-8")
        target = FileTarget(paths=(str(file_a), str(file_b)))

        result = await resolve_content(target)

        assert "content_a" in result
        assert "content_b" in result
        assert str(file_a) in result
        assert str(file_b) in result

    async def test_file_not_found_raises_error(self, tmp_path: Path) -> None:
        """存在しないファイルの場合 ContentResolveError を送出する。"""
        target = FileTarget(paths=(str(tmp_path / "nonexistent.py"),))

        with pytest.raises(ContentResolveError, match="Cannot read file"):
            await resolve_content(target)

    async def test_binary_file_raises_error(self, tmp_path: Path) -> None:
        """バイナリファイル（非 UTF-8）の場合 ContentResolveError を送出する。"""
        binary_file = tmp_path / "data.bin"
        binary_file.write_bytes(b"\xff\xfe\x00\x01")
        target = FileTarget(paths=(str(binary_file),))

        with pytest.raises(ContentResolveError, match="not a valid UTF-8"):
            await resolve_content(target)

    async def test_permission_error_raises_content_resolve_error(
        self, tmp_path: Path
    ) -> None:
        """PermissionError の場合 ContentResolveError を送出する。"""
        file = tmp_path / "secret.py"
        file.write_text("secret", encoding="utf-8")
        file.chmod(0o000)
        target = FileTarget(paths=(str(file),))

        try:
            with pytest.raises(ContentResolveError, match="Cannot read file"):
                await resolve_content(target)
        finally:
            file.chmod(0o644)

    async def test_file_exception_chain_preserved(self, tmp_path: Path) -> None:
        """ファイル例外の __cause__ が保持される。"""
        target = FileTarget(paths=(str(tmp_path / "nonexistent.py"),))

        with pytest.raises(ContentResolveError) as exc_info:
            await resolve_content(target)

        assert exc_info.value.__cause__ is not None


# =============================================================================
# resolve_content — 型ガード
# =============================================================================


class TestResolveContentTypeGuard:
    """resolve_content の型ガードテスト。"""

    async def test_unknown_target_type_raises_type_error(self) -> None:
        """未知の target 型で TypeError を送出する。"""
        with pytest.raises(TypeError, match="Unknown target type"):
            await resolve_content("not a target")  # type: ignore[arg-type]
