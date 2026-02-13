"""SelectorContextPrefetch のテスト。

Issue #187: セレクターエージェント向けコンテキスト事前取得。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from hachimoku.models._base import HachimokuBaseModel


# ── Phase 1: モデル定義テスト ──────────────────────────────


class TestPrefetchedContextModel:
    """PrefetchedContext モデルのテスト。"""

    def test_inherits_base_model(self) -> None:
        from hachimoku.engine._prefetch import PrefetchedContext

        assert issubclass(PrefetchedContext, HachimokuBaseModel)

    def test_default_empty_values(self) -> None:
        from hachimoku.engine._prefetch import PrefetchedContext

        ctx = PrefetchedContext()
        assert ctx.issue_context == ""
        assert ctx.pr_metadata == ""
        assert ctx.project_conventions == ""

    def test_with_all_fields(self) -> None:
        from hachimoku.engine._prefetch import PrefetchedContext

        ctx = PrefetchedContext(
            issue_context="Issue #187 details",
            pr_metadata="PR #185 metadata",
            project_conventions="--- CLAUDE.md ---\ncontent",
        )
        assert ctx.issue_context == "Issue #187 details"
        assert ctx.pr_metadata == "PR #185 metadata"
        assert ctx.project_conventions == "--- CLAUDE.md ---\ncontent"

    def test_frozen(self) -> None:
        from hachimoku.engine._prefetch import PrefetchedContext

        ctx = PrefetchedContext()
        with pytest.raises(ValidationError):
            ctx.issue_context = "changed"  # type: ignore[misc]

    def test_extra_forbidden(self) -> None:
        from hachimoku.engine._prefetch import PrefetchedContext

        with pytest.raises(ValidationError, match="extra"):
            PrefetchedContext(unknown="value")  # type: ignore[call-arg]


# ── Phase 3: 個別取得関数テスト ────────────────────────────

_RUN_GH = "hachimoku.engine._prefetch._run_gh"


class TestRunGh:
    """_run_gh 内部関数のテスト。"""

    async def test_success(self) -> None:
        from hachimoku.engine._prefetch import _run_gh

        proc = AsyncMock()
        proc.communicate.return_value = (b"output text", b"")
        proc.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await _run_gh("issue", "view", "187")
        assert result == "output text"

    async def test_command_failure_raises_prefetch_error(self) -> None:
        from hachimoku.engine._prefetch import PrefetchError, _run_gh

        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"not found")
        proc.returncode = 1
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with pytest.raises(PrefetchError, match="gh issue view 187.*failed"):
                await _run_gh("issue", "view", "187")

    async def test_gh_not_found_raises_prefetch_error(self) -> None:
        from hachimoku.engine._prefetch import PrefetchError, _run_gh

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("gh"),
        ):
            with pytest.raises(PrefetchError, match="not found"):
                await _run_gh("issue", "view", "1")

    async def test_timeout_raises_prefetch_error(self) -> None:
        from hachimoku.engine._prefetch import PrefetchError, _run_gh

        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        proc.kill = AsyncMock()
        proc.wait = AsyncMock()
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                with pytest.raises(PrefetchError, match="timed out"):
                    await _run_gh("issue", "view", "1")


class TestFetchIssueContext:
    """_fetch_issue_context のテスト。"""

    async def test_success(self) -> None:
        from hachimoku.engine._prefetch import _fetch_issue_context

        with patch(
            _RUN_GH,
            new_callable=AsyncMock,
            return_value="Issue title\n\nIssue body text",
        ):
            result = await _fetch_issue_context(187)
        assert "Issue title" in result
        assert "Issue body text" in result

    async def test_gh_failure_raises_prefetch_error(self) -> None:
        from hachimoku.engine._prefetch import PrefetchError, _fetch_issue_context

        with patch(
            _RUN_GH,
            new_callable=AsyncMock,
            side_effect=PrefetchError("gh issue view 187 failed"),
        ):
            with pytest.raises(PrefetchError, match="gh issue view.*187"):
                await _fetch_issue_context(187)

    async def test_truncation_applied(self) -> None:
        from hachimoku.engine._prefetch import (
            ISSUE_CONTEXT_MAX_CHARS,
            _fetch_issue_context,
        )

        long_content = "x" * (ISSUE_CONTEXT_MAX_CHARS + 1000)
        with patch(_RUN_GH, new_callable=AsyncMock, return_value=long_content):
            result = await _fetch_issue_context(187)
        assert len(result) <= ISSUE_CONTEXT_MAX_CHARS + 100
        assert "truncated" in result


class TestFetchPrMetadata:
    """_fetch_pr_metadata のテスト。"""

    async def test_success(self) -> None:
        from hachimoku.engine._prefetch import _fetch_pr_metadata

        with patch(_RUN_GH, new_callable=AsyncMock, return_value="PR title\n\nPR body"):
            result = await _fetch_pr_metadata(185)
        assert "PR title" in result

    async def test_failure_raises_prefetch_error(self) -> None:
        from hachimoku.engine._prefetch import PrefetchError, _fetch_pr_metadata

        with patch(
            _RUN_GH,
            new_callable=AsyncMock,
            side_effect=PrefetchError("gh pr view 185 failed"),
        ):
            with pytest.raises(PrefetchError, match="gh pr view.*185"):
                await _fetch_pr_metadata(185)


class TestReadProjectConventions:
    """_read_project_conventions のテスト。"""

    def test_reads_existing_files(self, tmp_path: object) -> None:
        from pathlib import Path

        from hachimoku.engine._prefetch import (
            DEFAULT_CONVENTION_FILES,
            _read_project_conventions,
        )

        import os

        original_cwd = os.getcwd()
        tmp = Path(str(tmp_path))
        try:
            os.chdir(tmp)
            claude_md = tmp / "CLAUDE.md"
            claude_md.write_text("# Project Rules\n- Rule 1")
            hachimoku_dir = tmp / ".hachimoku"
            hachimoku_dir.mkdir()
            config_toml = hachimoku_dir / "config.toml"
            config_toml.write_text('[general]\nmodel = "test"')

            result = _read_project_conventions(DEFAULT_CONVENTION_FILES)
        finally:
            os.chdir(original_cwd)

        assert "CLAUDE.md" in result
        assert "Project Rules" in result
        assert "config.toml" in result

    def test_missing_files_skipped(self, tmp_path: object) -> None:
        from pathlib import Path

        from hachimoku.engine._prefetch import (
            DEFAULT_CONVENTION_FILES,
            _read_project_conventions,
        )

        import os

        original_cwd = os.getcwd()
        tmp = Path(str(tmp_path))
        try:
            os.chdir(tmp)
            result = _read_project_conventions(DEFAULT_CONVENTION_FILES)
        finally:
            os.chdir(original_cwd)

        assert result == ""

    def test_truncation_applied(self, tmp_path: object) -> None:
        from pathlib import Path

        from hachimoku.engine._prefetch import (
            CONVENTIONS_MAX_CHARS,
            _read_project_conventions,
        )

        import os

        original_cwd = os.getcwd()
        tmp = Path(str(tmp_path))
        try:
            os.chdir(tmp)
            claude_md = tmp / "CLAUDE.md"
            claude_md.write_text("x" * (CONVENTIONS_MAX_CHARS + 500))
            result = _read_project_conventions(("CLAUDE.md",))
        finally:
            os.chdir(original_cwd)

        assert "truncated" in result

    def test_custom_convention_files(self, tmp_path: object) -> None:
        """convention_files にカスタムパスを指定できること。Issue #187."""
        from pathlib import Path

        from hachimoku.engine._prefetch import _read_project_conventions

        import os

        original_cwd = os.getcwd()
        tmp = Path(str(tmp_path))
        try:
            os.chdir(tmp)
            custom_file = tmp / "custom-rules.md"
            custom_file.write_text("# Custom Rules")

            result = _read_project_conventions(("custom-rules.md",))
        finally:
            os.chdir(original_cwd)

        assert "custom-rules.md" in result
        assert "Custom Rules" in result

    def test_unreadable_file_raises_prefetch_error(self, tmp_path: object) -> None:
        """存在するが読み込み不能なファイルで PrefetchError が送出されること。"""
        from pathlib import Path

        from hachimoku.engine._prefetch import PrefetchError, _read_project_conventions

        import os

        original_cwd = os.getcwd()
        tmp = Path(str(tmp_path))
        try:
            os.chdir(tmp)
            unreadable = tmp / "unreadable.md"
            unreadable.write_text("content")
            unreadable.chmod(0o000)

            with pytest.raises(PrefetchError, match="Failed to read"):
                _read_project_conventions(("unreadable.md",))
        finally:
            unreadable.chmod(0o644)
            os.chdir(original_cwd)


# ── Phase 4: 統合関数テスト ────────────────────────────────

_FETCH_ISSUE = "hachimoku.engine._prefetch._fetch_issue_context"
_FETCH_PR = "hachimoku.engine._prefetch._fetch_pr_metadata"
_READ_CONVENTIONS = "hachimoku.engine._prefetch._read_project_conventions"


class TestPrefetchSelectorContext:
    """prefetch_selector_context 統合テスト。"""

    async def test_diff_target_with_issue(self) -> None:
        from hachimoku.engine._prefetch import prefetch_selector_context
        from hachimoku.engine._target import DiffTarget

        target = DiffTarget(base_branch="main", issue_number=187)
        with (
            patch(
                _FETCH_ISSUE, new_callable=AsyncMock, return_value="Issue 187 body"
            ) as mock_issue,
            patch(_FETCH_PR, new_callable=AsyncMock) as mock_pr,
            patch(_READ_CONVENTIONS, return_value="conventions text"),
        ):
            result = await prefetch_selector_context(
                target, convention_files=("CLAUDE.md",)
            )

        mock_issue.assert_awaited_once_with(187)
        mock_pr.assert_not_awaited()
        assert result.issue_context == "Issue 187 body"
        assert result.pr_metadata == ""
        assert result.project_conventions == "conventions text"

    async def test_pr_target_fetches_pr_metadata(self) -> None:
        from hachimoku.engine._prefetch import prefetch_selector_context
        from hachimoku.engine._target import PRTarget

        target = PRTarget(pr_number=185, issue_number=187)
        with (
            patch(_FETCH_ISSUE, new_callable=AsyncMock, return_value="Issue body"),
            patch(
                _FETCH_PR, new_callable=AsyncMock, return_value="PR metadata"
            ) as mock_pr,
            patch(_READ_CONVENTIONS, return_value=""),
        ):
            result = await prefetch_selector_context(target, convention_files=())

        mock_pr.assert_awaited_once_with(185)
        assert result.pr_metadata == "PR metadata"

    async def test_file_target_no_pr_metadata(self) -> None:
        from hachimoku.engine._prefetch import prefetch_selector_context
        from hachimoku.engine._target import FileTarget

        target = FileTarget(paths=("src/main.py",))
        with (
            patch(_FETCH_ISSUE, new_callable=AsyncMock) as mock_issue,
            patch(_FETCH_PR, new_callable=AsyncMock) as mock_pr,
            patch(_READ_CONVENTIONS, return_value=""),
        ):
            result = await prefetch_selector_context(target, convention_files=())

        mock_issue.assert_not_awaited()
        mock_pr.assert_not_awaited()
        assert result.issue_context == ""
        assert result.pr_metadata == ""

    async def test_no_issue_number_skips_issue_fetch(self) -> None:
        from hachimoku.engine._prefetch import prefetch_selector_context
        from hachimoku.engine._target import DiffTarget

        target = DiffTarget(base_branch="main")
        with (
            patch(_FETCH_ISSUE, new_callable=AsyncMock) as mock_issue,
            patch(_FETCH_PR, new_callable=AsyncMock),
            patch(_READ_CONVENTIONS, return_value=""),
        ):
            result = await prefetch_selector_context(target, convention_files=())

        mock_issue.assert_not_awaited()
        assert result.issue_context == ""

    async def test_convention_files_passed_to_reader(self) -> None:
        """convention_files が _read_project_conventions に渡されること。Issue #187."""
        from hachimoku.engine._prefetch import prefetch_selector_context
        from hachimoku.engine._target import DiffTarget

        target = DiffTarget(base_branch="main")
        custom_files = ("README.md", "pyproject.toml")
        with (
            patch(_FETCH_ISSUE, new_callable=AsyncMock),
            patch(_FETCH_PR, new_callable=AsyncMock),
            patch(_READ_CONVENTIONS, return_value="custom") as mock_conv,
        ):
            result = await prefetch_selector_context(
                target, convention_files=custom_files
            )

        mock_conv.assert_called_once_with(custom_files)
        assert result.project_conventions == "custom"
