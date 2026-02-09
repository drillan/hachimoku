"""ContentResolver のテスト。

Issue #129: エンジンが diff を事前解決して全エージェントのインストラクションに埋め込む。
ターゲットタイプに応じてレビュー対象コンテンツを事前解決する。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
            mock_proc.communicate.side_effect = asyncio.TimeoutError()
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            with pytest.raises(ContentResolveError, match="timed out"):
                await resolve_content(target)


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

        with pytest.raises(ContentResolveError, match="not found"):
            await resolve_content(target)


# =============================================================================
# resolve_content — 型ガード
# =============================================================================


class TestResolveContentTypeGuard:
    """resolve_content の型ガードテスト。"""

    async def test_unknown_target_type_raises_type_error(self) -> None:
        """未知の target 型で TypeError を送出する。"""
        with pytest.raises(TypeError, match="Unknown target type"):
            await resolve_content("not a target")  # type: ignore[arg-type]
