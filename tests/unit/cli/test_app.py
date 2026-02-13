"""Typer app のテスト。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定（review_callback 経由）。
FR-CLI-003: 終了コードの検証。
FR-CLI-004: stdout/stderr ストリーム分離。
FR-CLI-006: CLI オプション対応表。
FR-CLI-007: .hachimoku/ ディレクトリ構造の初期化。
FR-CLI-008: 既存ファイルのスキップと --force による上書き。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。

NOTE: Typer の CliRunner は stderr 分離パラメータを公開しないため、
stderr 出力は result.output（stdout + stderr 混合出力）で検証する。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pydantic import ValidationError
from typer.testing import CliRunner

from hachimoku.cli._app import app
from hachimoku.cli._file_resolver import FileResolutionError, ResolvedFiles
from hachimoku.cli._init_handler import InitError, InitResult
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.exit_code import ExitCode
from hachimoku.agents import LoadError
from tests.unit.cli.conftest import (
    PATCH_FIND_PROJECT_ROOT,
    PATCH_LOAD_AGENTS,
    PATCH_LOAD_BUILTIN_AGENTS,
    PATCH_RESOLVE_CONFIG,
    PATCH_RESOLVE_FILES,
    PATCH_RUN_REVIEW,
    PATCH_SAVE_REVIEW_HISTORY,
    make_agent_definition,
    make_engine_result,
    make_load_result,
    setup_mocks,
)

PATCH_RUN_INIT = "hachimoku.cli._app.run_init"

runner = CliRunner()


# --- US1 テスト（既存、run_review モック付きに更新） ---


class TestAppHelp:
    """--help の動作を検証する。"""

    def test_help_exits_with_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_tool_description(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert "Multi-agent code review" in result.output

    def test_help_shows_subcommands(self) -> None:
        """--help にサブコマンド情報が含まれる。"""
        result = runner.invoke(app, ["--help"])
        assert "config" in result.output


class TestReviewCallbackDiffMode:
    """引数なしで diff モード判定を検証する。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_no_args_exits_with_zero(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なし → diff モード → 正常終了。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_no_args_calls_run_review_with_diff_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なし → DiffTarget で run_review が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, DiffTarget)


class TestReviewCallbackPRMode:
    """整数引数で PR モード判定を検証する。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_integer_arg_exits_with_zero(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """整数引数 → PR モード → 正常終了。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, ["123"])
        assert result.exit_code == 0

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_integer_arg_calls_run_review_with_pr_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """整数引数 → PRTarget(pr_number=123) で run_review が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["123"])
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, PRTarget)
        assert target.pr_number == 123


class TestReviewCallbackFileMode:
    """パスライク引数で file モード判定を検証する。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_path_like_arg_exits_with_zero(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """パスライク引数 → file モード → 正常終了。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/src/auth.py",))
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_path_like_arg_calls_run_review_with_file_target(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """パスライク引数 → FileTarget で run_review が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/src/auth.py",))
        runner.invoke(app, ["src/auth.py"])
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert "/abs/src/auth.py" in target.paths


class TestReviewCallbackError:
    """不明文字列で終了コード 4 を検証する。"""

    def test_unknown_string_exits_with_four(self) -> None:
        result = runner.invoke(app, ["unknown_string_that_does_not_exist"])
        assert result.exit_code == 4

    def test_unknown_string_output_contains_error(self) -> None:
        """エラーメッセージが出力に含まれる。"""
        result = runner.invoke(app, ["unknown_string_that_does_not_exist"])
        assert "error" in result.output.lower()

    def test_error_message_contains_hint(self) -> None:
        """エラーメッセージに解決方法のヒントを含む（FR-CLI-014）。"""
        result = runner.invoke(app, ["unknown_string_that_does_not_exist"])
        output_lower = result.output.lower()
        assert "pr number" in output_lower or "file path" in output_lower


class TestConfigSubcommand:
    """config 予約サブコマンドを検証する（R-009）。"""

    def test_config_exits_with_four(self) -> None:
        """config コマンドは未実装エラー（終了コード 4）。"""
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 4

    def test_config_output_contains_not_implemented(self) -> None:
        """出力に未実装メッセージが含まれる。"""
        result = runner.invoke(app, ["config"])
        assert "not implemented" in result.output.lower()

    def test_config_output_contains_edit_hint(self) -> None:
        """出力に設定ファイル直接編集のヒントが含まれる。"""
        result = runner.invoke(app, ["config"])
        assert "config.toml" in result.output


# --- US2 テスト（新規） ---


class TestReviewExecution:
    """レビュー実行フロー（run_review モック）の検証。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_diff_mode_calls_run_review(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なし → DiffTarget で run_review が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, DiffTarget)
        assert target.base_branch == "main"

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_pr_mode_calls_run_review(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """整数引数 → PRTarget(pr_number=123) で run_review が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, ["123"])
        assert result.exit_code == 0
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, PRTarget)
        assert target.pr_number == 123

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_file_mode_calls_run_review(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """パスライク引数 → FileTarget で run_review が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/src/auth.py",))
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert target.paths == ("/abs/src/auth.py",)

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_report_output_to_stdout(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """レポート内容が出力に含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        # 暫定出力は JSON ダンプ。total_issues が含まれることを検証
        assert "total_issues" in result.output


class TestReviewExitCodes:
    """レビュー実行の終了コード検証（FR-CLI-003）。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_exit_code_0_on_success(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.SUCCESS(0) → exit_code 0。"""
        setup_mocks(mock_config, mock_run_review, ExitCode.SUCCESS)
        result = runner.invoke(app)
        assert result.exit_code == 0

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_exit_code_1_on_critical(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.CRITICAL(1) → exit_code 1。"""
        setup_mocks(mock_config, mock_run_review, ExitCode.CRITICAL)
        result = runner.invoke(app)
        assert result.exit_code == 1

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_exit_code_2_on_important(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.IMPORTANT(2) → exit_code 2。"""
        setup_mocks(mock_config, mock_run_review, ExitCode.IMPORTANT)
        result = runner.invoke(app)
        assert result.exit_code == 2

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_exit_code_3_on_execution_error(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.EXECUTION_ERROR(3) → exit_code 3。"""
        setup_mocks(mock_config, mock_run_review, ExitCode.EXECUTION_ERROR)
        result = runner.invoke(app)
        assert result.exit_code == 3


class TestReviewConfigOverrides:
    """CLI オプションから config_overrides 辞書の構築を検証する（FR-CLI-006）。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_model_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--model → config_overrides に "model" キーが含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--model", "gpt-4o"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["model"] == "gpt-4o"

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_timeout_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--timeout → config_overrides に "timeout" キーが含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--timeout", "600"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["timeout"] == 600

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_turns_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--max-turns → config_overrides に "max_turns" キーが含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--max-turns", "5"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["max_turns"] == 5

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_format_option_key_mapping(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--format → config_overrides に "output_format" キーが含まれる（キー名変換）。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--format", "json"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "output_format" in overrides
        assert "format" not in overrides

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_files_option_key_mapping(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--max-files → config_overrides に "max_files_per_review" キーが含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--max-files", "50"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "max_files_per_review" in overrides
        assert "max_files" not in overrides
        assert overrides["max_files_per_review"] == 50

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_base_branch_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--base-branch → config_overrides に "base_branch" キーが含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--base-branch", "develop"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["base_branch"] == "develop"

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_no_options_empty_overrides(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """オプション未指定 → config_overrides に設定キーが含まれない（None 除外）。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        config_keys = {
            "model",
            "timeout",
            "max_turns",
            "parallel",
            "base_branch",
            "output_format",
            "save_reviews",
            "show_cost",
            "max_files_per_review",
        }
        assert not (set(overrides.keys()) & config_keys)

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_multiple_options_combined(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """複数オプション同時指定 → 全てが config_overrides に含まれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--model", "opus", "--timeout", "600", "--format", "json"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["model"] == "opus"
        assert overrides["timeout"] == 600
        assert overrides["output_format"] == "json"

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_resolve_config_receives_overrides(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """resolve_config が config_overrides を受け取る（I-4）。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--model", "opus"])
        mock_config.assert_called_once()
        call_kwargs = mock_config.call_args.kwargs
        assert "cli_overrides" in call_kwargs
        assert call_kwargs["cli_overrides"]["model"] == "opus"


_BOOLEAN_FLAG_CASES: list[tuple[str, str, str]] = [
    ("--parallel", "--no-parallel", "parallel"),
    ("--save-reviews", "--no-save-reviews", "save_reviews"),
    ("--show-cost", "--no-show-cost", "show_cost"),
]


class TestReviewBooleanFlags:
    """boolean フラグペア（--parallel/--no-parallel 等）の三値テスト（R-005）。"""

    @pytest.mark.parametrize(
        ("flag_true", "flag_false", "config_key"),
        _BOOLEAN_FLAG_CASES,
    )
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_flag_true(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        flag_true: str,
        flag_false: str,
        config_key: str,
    ) -> None:
        """--flag → config_overrides[key] == True。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, [flag_true])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides[config_key] is True

    @pytest.mark.parametrize(
        ("flag_true", "flag_false", "config_key"),
        _BOOLEAN_FLAG_CASES,
    )
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_flag_false(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        flag_true: str,
        flag_false: str,
        config_key: str,
    ) -> None:
        """--no-flag → config_overrides[key] == False。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, [flag_false])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides[config_key] is False

    @pytest.mark.parametrize(
        ("flag_true", "flag_false", "config_key"),
        _BOOLEAN_FLAG_CASES,
    )
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_flag_unset(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        flag_true: str,
        flag_false: str,
        config_key: str,
    ) -> None:
        """未指定 → config_overrides に key なし。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert config_key not in overrides


class TestReviewIssueOption:
    """--issue per-invocation オプションの検証。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_issue_passed_to_diff_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """diff モード + --issue → DiffTarget.issue_number に設定される。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--issue", "50"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, DiffTarget)
        assert target.issue_number == 50

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_issue_passed_to_pr_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """PR モード + --issue → PRTarget.issue_number に設定される。"""
        setup_mocks(mock_config, mock_run_review)
        # NOTE: --issue は位置引数より前に配置する。_ReviewGroup が位置引数を
        # 消費する際にオプションも含めて protected_args に格納するため。
        runner.invoke(app, ["--issue", "50", "123"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, PRTarget)
        assert target.issue_number == 50

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_issue_passed_to_file_target(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """file モード + --issue → FileTarget.issue_number に設定される。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/src/auth.py",))
        # NOTE: --issue は位置引数より前に配置する（上記同様の理由）。
        runner.invoke(app, ["--issue", "50", "src/auth.py"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert target.issue_number == 50

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_no_issue_default_none(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--issue 未指定 → target.issue_number == None。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        target = mock_run_review.call_args.kwargs["target"]
        assert target.issue_number is None


class TestReviewRunReviewError:
    """run_review 実行中の例外ハンドリング。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_run_review_exception_exits_with_3(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """run_review が例外送出 → exit_code 3（EXECUTION_ERROR）。"""
        mock_config.return_value = HachimokuConfig()
        mock_run_review.side_effect = RuntimeError("Engine failed")
        result = runner.invoke(app)
        assert result.exit_code == 3

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_run_review_exception_outputs_error_message(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """run_review 例外時にエラーメッセージが出力される。"""
        mock_config.return_value = HachimokuConfig()
        mock_run_review.side_effect = RuntimeError("Engine failed")
        result = runner.invoke(app)
        assert "error" in result.output.lower()
        assert "Engine failed" in result.output

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_run_review_exception_contains_hint(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """run_review 例外のエラーメッセージに解決方法ヒントが含まれる（FR-CLI-014）。"""
        mock_config.return_value = HachimokuConfig()
        mock_run_review.side_effect = RuntimeError("Engine failed")
        result = runner.invoke(app)
        assert "--help" in result.output


class TestReviewConfigError:
    """設定解決エラーのハンドリング（C-2）。"""

    @patch(PATCH_RESOLVE_CONFIG)
    def test_validation_error_exits_with_4(self, mock_config: MagicMock) -> None:
        """resolve_config が ValidationError → exit_code 4（INPUT_ERROR）。"""
        mock_config.side_effect = ValidationError.from_exception_data(
            title="HachimokuConfig",
            line_errors=[],
        )
        result = runner.invoke(app)
        assert result.exit_code == 4

    @patch(PATCH_RESOLVE_CONFIG)
    def test_validation_error_shows_config_hint(self, mock_config: MagicMock) -> None:
        """設定エラー時に config.toml の案内が出力される。"""
        mock_config.side_effect = ValidationError.from_exception_data(
            title="HachimokuConfig",
            line_errors=[],
        )
        result = runner.invoke(app)
        assert "config.toml" in result.output

    @patch(PATCH_RESOLVE_CONFIG)
    def test_permission_error_exits_with_4(self, mock_config: MagicMock) -> None:
        """resolve_config が PermissionError → exit_code 4（INPUT_ERROR）。"""
        mock_config.side_effect = PermissionError("Permission denied")
        result = runner.invoke(app)
        assert result.exit_code == 4


# --- US3 テスト ---


class TestInitSubcommand:
    """init サブコマンドの CLI 統合テスト。FR-CLI-007."""

    def test_init_help_exits_with_zero(self) -> None:
        """init --help が正常終了する。"""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0

    def test_init_help_contains_description(self) -> None:
        """init --help に説明が含まれる。"""
        result = runner.invoke(app, ["init", "--help"])
        assert "Initialize" in result.output

    def test_help_shows_init_subcommand(self) -> None:
        """--help に init サブコマンド情報が含まれる。"""
        result = runner.invoke(app, ["--help"])
        assert "init" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_calls_run_init(self, mock_run_init: MagicMock) -> None:
        """init が run_init を呼び出す。"""
        mock_run_init.return_value = InitResult()
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        mock_run_init.assert_called_once()

    @patch(PATCH_RUN_INIT)
    def test_init_force_passes_flag(self, mock_run_init: MagicMock) -> None:
        """init --force が force=True で run_init を呼ぶ。"""
        mock_run_init.return_value = InitResult()
        runner.invoke(app, ["init", "--force"])
        _, kwargs = mock_run_init.call_args
        assert kwargs["force"] is True

    @patch(PATCH_RUN_INIT)
    def test_init_default_no_force(self, mock_run_init: MagicMock) -> None:
        """--force なしでは force=False。"""
        mock_run_init.return_value = InitResult()
        runner.invoke(app, ["init"])
        _, kwargs = mock_run_init.call_args
        assert kwargs["force"] is False

    @patch(PATCH_RUN_INIT)
    def test_init_error_exits_with_four(self, mock_run_init: MagicMock) -> None:
        """InitError で終了コード 4。"""
        mock_run_init.side_effect = InitError("Not a Git repository")
        result = runner.invoke(app, ["init"])
        assert result.exit_code == ExitCode.INPUT_ERROR

    @patch(PATCH_RUN_INIT)
    def test_init_error_shows_message(self, mock_run_init: MagicMock) -> None:
        """InitError のメッセージが出力される。"""
        mock_run_init.side_effect = InitError("Not a Git repository")
        result = runner.invoke(app, ["init"])
        assert "Not a Git repository" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_shows_created_files(self, mock_run_init: MagicMock) -> None:
        """成功時に作成ファイルが表示される。"""
        from pathlib import Path

        mock_run_init.return_value = InitResult(
            created=(Path("/tmp/config.toml"),),
        )
        result = runner.invoke(app, ["init"])
        assert "Created:" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_shows_skipped_files(self, mock_run_init: MagicMock) -> None:
        """既存ファイルのスキップ情報が表示される。"""
        from pathlib import Path

        mock_run_init.return_value = InitResult(
            skipped=(Path("/tmp/config.toml"),),
        )
        result = runner.invoke(app, ["init"])
        assert "Skipped" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_all_exist_shows_hint(self, mock_run_init: MagicMock) -> None:
        """全ファイル既存時に --force ヒントが表示される。"""
        from pathlib import Path

        mock_run_init.return_value = InitResult(
            skipped=(Path("/tmp/config.toml"),),
        )
        result = runner.invoke(app, ["init"])
        assert "--force" in result.output


# --- US4 テスト（file モード: ファイル解決と確認プロンプト） ---


class TestReviewCallbackFileModeResolution:
    """file モード: resolve_files 呼び出しと確認プロンプト（FR-CLI-009, FR-CLI-011）。"""

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_file_mode_calls_resolve_files(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """file モードで resolve_files が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/tmp/a.py",))
        runner.invoke(app, ["src/auth.py"])
        mock_resolve_files.assert_called_once()

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_resolved_paths_passed_to_file_target(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """resolve_files の結果が FileTarget.paths に渡される。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/src/auth.py",))
        runner.invoke(app, ["src/auth.py"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert target.paths == ("/abs/src/auth.py",)

    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_file_resolution_error_exits_with_4(
        self, mock_config: MagicMock, mock_resolve_files: MagicMock
    ) -> None:
        """FileResolutionError → exit code 4。"""
        mock_config.return_value = HachimokuConfig()
        mock_resolve_files.side_effect = FileResolutionError("Not found")
        result = runner.invoke(app, ["nonexistent.py"])
        assert result.exit_code == ExitCode.INPUT_ERROR

    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_file_resolution_error_shows_message(
        self, mock_config: MagicMock, mock_resolve_files: MagicMock
    ) -> None:
        """FileResolutionError のメッセージが出力される。"""
        mock_config.return_value = HachimokuConfig()
        mock_resolve_files.side_effect = FileResolutionError(
            "File not found: 'x.py'. Check the file path."
        )
        result = runner.invoke(app, ["x.py"])
        assert "File not found" in result.output

    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_empty_result_exits_with_0(
        self, mock_config: MagicMock, mock_resolve_files: MagicMock
    ) -> None:
        """resolve_files が None → exit code 0。"""
        mock_config.return_value = HachimokuConfig()
        mock_resolve_files.return_value = None
        result = runner.invoke(app, ["src/"])
        assert result.exit_code == ExitCode.SUCCESS

    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_empty_result_shows_message(
        self, mock_config: MagicMock, mock_resolve_files: MagicMock
    ) -> None:
        """empty result → "No files found" メッセージ。"""
        mock_config.return_value = HachimokuConfig()
        mock_resolve_files.return_value = None
        result = runner.invoke(app, ["src/"])
        assert "no files found" in result.output.lower()

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_warnings_printed_to_output(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """resolve_files の warnings が出力される。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(
            paths=("/tmp/a.py",),
            warnings=("Skipping symlink cycle: /x -> /y",),
        )
        result = runner.invoke(app, ["src/"])
        assert "Skipping symlink cycle" in result.output

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_files_exceeded_no_confirm_continues(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """--no-confirm + max_files 超過 → 確認なしで続行。"""
        mock_config.return_value = HachimokuConfig(max_files_per_review=1)
        mock_run_review.return_value = make_engine_result()
        mock_resolve_files.return_value = ResolvedFiles(
            paths=("/tmp/a.py", "/tmp/b.py")
        )
        result = runner.invoke(app, ["--no-confirm", "src/"])
        assert result.exit_code == 0
        mock_run_review.assert_called_once()

    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_files_exceeded_user_denies_exits_0(
        self, mock_config: MagicMock, mock_resolve_files: MagicMock
    ) -> None:
        """max_files 超過 + ユーザー拒否 → exit code 0。"""
        mock_config.return_value = HachimokuConfig(max_files_per_review=1)
        mock_resolve_files.return_value = ResolvedFiles(
            paths=("/tmp/a.py", "/tmp/b.py")
        )
        result = runner.invoke(app, ["src/"], input="n\n")
        assert result.exit_code == 0

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_files_exceeded_user_confirms_continues(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """max_files 超過 + ユーザー承認 → レビュー続行。"""
        mock_config.return_value = HachimokuConfig(max_files_per_review=1)
        mock_run_review.return_value = make_engine_result()
        mock_resolve_files.return_value = ResolvedFiles(
            paths=("/tmp/a.py", "/tmp/b.py")
        )
        result = runner.invoke(app, ["src/"], input="y\n")
        assert result.exit_code == 0
        mock_run_review.assert_called_once()

    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_files_exceeded_prompt_contains_counts(
        self, mock_config: MagicMock, mock_resolve_files: MagicMock
    ) -> None:
        """確認プロンプトにファイル数と上限値が含まれる。"""
        mock_config.return_value = HachimokuConfig(max_files_per_review=5)
        mock_resolve_files.return_value = ResolvedFiles(
            paths=tuple(f"/tmp/f{i}.py" for i in range(10))
        )
        result = runner.invoke(app, ["src/"], input="n\n")
        assert "10 files found" in result.output
        assert "5" in result.output

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_max_files_not_exceeded_no_prompt(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """max_files 未超過 → プロンプトなしで続行。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/tmp/a.py",))
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0
        mock_run_review.assert_called_once()
        # 確認プロンプトが表示されていないことを検証
        assert "exceeding limit" not in result.output

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_diff_mode_does_not_call_resolve_files(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """diff モードでは resolve_files が呼ばれない。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        mock_resolve_files.assert_not_called()

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_pr_mode_does_not_call_resolve_files(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """PR モードでは resolve_files が呼ばれない。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["123"])
        mock_resolve_files.assert_not_called()


# --- US5 テスト（agents サブコマンド） ---


class TestAgentsSubcommand:
    """agents サブコマンドのテスト（FR-CLI-012）。"""

    def test_agents_help_exits_with_zero(self) -> None:
        """agents --help → exit 0。"""
        result = runner.invoke(app, ["agents", "--help"])
        assert result.exit_code == 0

    def test_help_shows_agents_subcommand(self) -> None:
        """--help に agents サブコマンド情報が含まれる。"""
        result = runner.invoke(app, ["--help"])
        assert "agents" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_list_shows_builtin_agents(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """引数なし → ビルトインエージェント名が出力に含まれる。"""
        agent = make_agent_definition(name="code-reviewer", model="sonnet")
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents"])
        assert "code-reviewer" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_list_shows_table_headers(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """一覧にテーブルヘッダーが含まれる。"""
        agent = make_agent_definition()
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents"])
        assert "NAME" in result.output
        assert "MODEL" in result.output
        assert "PHASE" in result.output
        assert "SCHEMA" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_list_shows_custom_marker(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """カスタムエージェントに [custom] マーカーが付与される。"""
        builtin = make_agent_definition(name="code-reviewer")
        custom = make_agent_definition(name="my-custom")
        mock_load_agents.return_value = make_load_result(agents=(builtin, custom))
        mock_load_builtin.return_value = make_load_result(agents=(builtin,))
        result = runner.invoke(app, ["agents"])
        # code-reviewer 行には [custom] がない
        for line in result.output.splitlines():
            if "code-reviewer" in line:
                assert "[custom]" not in line
            if "my-custom" in line:
                assert "[custom]" in line

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_list_exits_with_zero(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """一覧表示 → exit 0。"""
        agent = make_agent_definition()
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents"])
        assert result.exit_code == 0

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_agent_info(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """エージェント名指定 → description, model, phase, output_schema が含まれる。"""
        agent = make_agent_definition(
            name="code-reviewer",
            model="sonnet",
            phase="main",
            output_schema="scored_issues",
            description="Code quality review",
        )
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "code-reviewer"])
        assert "Code quality review" in result.output
        assert "sonnet" in result.output
        assert "main" in result.output
        assert "scored_issues" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_applicability(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """詳細表示に applicability 情報が含まれる。"""
        agent = make_agent_definition(name="code-reviewer")
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "code-reviewer"])
        # デフォルトは always=True
        assert "always" in result.output.lower()

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_system_prompt_summary(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """詳細表示に system_prompt 概要が含まれる。"""
        agent = make_agent_definition(name="code-reviewer")
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "code-reviewer"])
        assert "System Prompt" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_exits_with_zero(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """詳細表示 → exit 0。"""
        agent = make_agent_definition(name="code-reviewer")
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "code-reviewer"])
        assert result.exit_code == 0

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_nonexistent_exits_with_four(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """存在しないエージェント → exit 4。"""
        agent = make_agent_definition(name="code-reviewer")
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "nonexistent"])
        assert result.exit_code == ExitCode.INPUT_ERROR

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_nonexistent_shows_error_with_hint(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """エラーに利用可能エージェント名が含まれる（FR-CLI-014）。"""
        agent = make_agent_definition(name="code-reviewer")
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "nonexistent"])
        assert "nonexistent" in result.output
        assert "code-reviewer" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_list_with_load_errors_shows_warnings(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """LoadResult.errors → 出力に警告が含まれる。"""
        agent = make_agent_definition(name="code-reviewer")
        error = LoadError(source="bad-agent.toml", message="Invalid TOML syntax")
        mock_load_agents.return_value = make_load_result(
            agents=(agent,), errors=(error,)
        )
        mock_load_builtin.return_value = make_load_result(agents=(agent,))
        result = runner.invoke(app, ["agents"])
        assert "bad-agent.toml" in result.output
        assert "code-reviewer" in result.output

    # --- S-1: 詳細表示の分岐カバレッジ ---

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_file_patterns(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """applicability.file_patterns が表示される。"""
        agent = make_agent_definition(
            name="typed-agent",
            applicability={"file_patterns": ["*.py", "*.ts"]},
        )
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "typed-agent"])
        assert "*.py" in result.output
        assert "*.ts" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_content_patterns(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """applicability.content_patterns が表示される。"""
        agent = make_agent_definition(
            name="hunt-agent",
            applicability={"content_patterns": [r"try\s*:"]},
        )
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "hunt-agent"])
        assert r"try\s*:" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_allowed_tools(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """allowed_tools が設定されている場合にツール名が表示される。"""
        agent = make_agent_definition(
            name="tooled-agent",
            allowed_tools=("git_read", "file_read"),
        )
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "tooled-agent"])
        assert "git_read" in result.output
        assert "file_read" in result.output

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_truncates_long_system_prompt(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """system_prompt が 4 行以上の場合に '...' で切り詰められる。"""
        long_prompt = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        agent = make_agent_definition(name="verbose-agent", system_prompt=long_prompt)
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents", "verbose-agent"])
        assert "Line 3" in result.output
        assert "..." in result.output
        assert "Line 4" not in result.output

    # --- S-2: 詳細表示での [custom] マーカー ---

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_detail_shows_custom_marker(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """詳細表示でカスタムエージェントに [custom] マーカーが付与される。"""
        builtin = make_agent_definition(name="code-reviewer")
        custom = make_agent_definition(name="my-custom")
        mock_load_agents.return_value = make_load_result(agents=(builtin, custom))
        mock_load_builtin.return_value = make_load_result(agents=(builtin,))
        result = runner.invoke(app, ["agents", "my-custom"])
        assert "[custom]" in result.output

    # --- S-3: find_project_root がパスを返すケース ---

    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    @patch(PATCH_FIND_PROJECT_ROOT)
    def test_agents_passes_custom_dir_when_project_root_found(
        self,
        mock_root: MagicMock,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
    ) -> None:
        """find_project_root がパスを返す場合に custom_dir が正しく渡される。"""
        mock_root.return_value = Path("/home/user/project")
        agent = make_agent_definition()
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        runner.invoke(app, ["agents"])
        call_kwargs = mock_load_agents.call_args.kwargs
        assert call_kwargs["custom_dir"] == Path("/home/user/project/.hachimoku/agents")

    # --- C-2: agents() の例外処理 ---

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_AGENTS, side_effect=OSError("Permission denied"))
    def test_agents_load_exception_exits_with_3(
        self,
        _mock_load: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """load_agents() 例外 → exit 3（EXECUTION_ERROR）。"""
        result = runner.invoke(app, ["agents"])
        assert result.exit_code == ExitCode.EXECUTION_ERROR

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_AGENTS, side_effect=OSError("Permission denied"))
    def test_agents_load_exception_shows_hint(
        self,
        _mock_load: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """load_agents() 例外にヒント付きエラーメッセージが含まれる。"""
        result = runner.invoke(app, ["agents"])
        assert "8moku init" in result.output

    # --- I-1: builtin_result.errors の警告出力 ---

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_list_shows_builtin_load_errors(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """builtin_result.errors も警告として出力される。"""
        agent = make_agent_definition(name="code-reviewer")
        builtin_error = LoadError(
            source="broken-builtin.toml", message="Schema not found"
        )
        mock_load_agents.return_value = make_load_result(agents=(agent,))
        mock_load_builtin.return_value = make_load_result(
            agents=(agent,), errors=(builtin_error,)
        )
        result = runner.invoke(app, ["agents"])
        assert "broken-builtin.toml" in result.output


# --- Polish テスト（エッジケース） ---

PATCH_GIT_EXISTS = "hachimoku.cli._app._is_git_repository"


class TestEdgeCases:
    """全ストーリー横断のエッジケーステスト（T035）。"""

    # --- PR 番号 + ファイルパスの同時指定 ---

    def test_pr_number_and_file_path_mixed_exits_with_error(self) -> None:
        """PR 番号とファイルパスの同時指定 → 終了コード 4。"""
        result = runner.invoke(app, ["123", "src/auth.py"])
        assert result.exit_code == ExitCode.INPUT_ERROR

    def test_pr_number_and_file_path_mixed_shows_error(self) -> None:
        """混在エラーメッセージが出力される。"""
        result = runner.invoke(app, ["123", "src/auth.py"])
        assert "error" in result.output.lower()

    # --- init/agents と同名ファイルの扱い ---

    @patch(PATCH_RUN_INIT)
    def test_init_string_routes_to_subcommand(self, mock_run_init: MagicMock) -> None:
        """'init' 引数はサブコマンドとして解釈される。"""
        mock_run_init.return_value = InitResult()
        result = runner.invoke(app, ["init"])
        mock_run_init.assert_called_once()
        assert result.exit_code == 0

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_dot_slash_init_routes_to_file_mode(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """'./init' 引数はパスライク文字列として file モードになる。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/init",))
        result = runner.invoke(app, ["./init"])
        assert result.exit_code == 0
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_LOAD_BUILTIN_AGENTS)
    @patch(PATCH_LOAD_AGENTS)
    def test_agents_string_routes_to_subcommand(
        self,
        mock_load_agents: MagicMock,
        mock_load_builtin: MagicMock,
        _mock_root: MagicMock,
    ) -> None:
        """'agents' 引数はサブコマンドとして解釈される。"""
        agent = make_agent_definition()
        result_obj = make_load_result(agents=(agent,))
        mock_load_agents.return_value = result_obj
        mock_load_builtin.return_value = result_obj
        result = runner.invoke(app, ["agents"])
        assert result.exit_code == 0
        mock_load_agents.assert_called_once()

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_dot_slash_agents_routes_to_file_mode(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
    ) -> None:
        """'./agents' 引数はパスライク文字列として file モードになる。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/agents",))
        result = runner.invoke(app, ["./agents"])
        assert result.exit_code == 0
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)

    # --- --format 不正値 ---

    def test_invalid_format_exits_with_error(self) -> None:
        """--format に不正な値 → 終了コードが非ゼロ。"""
        result = runner.invoke(app, ["--format", "invalid"])
        assert result.exit_code != 0

    # --- --timeout 不正値 ---

    def test_timeout_zero_exits_with_error(self) -> None:
        """--timeout 0 → min=1 バリデーションエラー。"""
        result = runner.invoke(app, ["--timeout", "0"])
        assert result.exit_code != 0

    def test_timeout_negative_exits_with_error(self) -> None:
        """--timeout -1 → min=1 バリデーションエラー。"""
        result = runner.invoke(app, ["--timeout", "-1"])
        assert result.exit_code != 0

    # --- --issue 不正値 ---

    def test_issue_zero_exits_with_error(self) -> None:
        """--issue 0 → min=1 バリデーションエラー。"""
        result = runner.invoke(app, ["--issue", "0"])
        assert result.exit_code != 0

    # --- Git リポジトリ外での diff/PR モード ---

    @pytest.mark.parametrize("cli_args", [[], ["123"]])
    @patch(PATCH_GIT_EXISTS, return_value=False)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_outside_git_repo_exits_with_4(
        self,
        mock_config: MagicMock,
        _mock_git: MagicMock,
        cli_args: list[str],
    ) -> None:
        """diff/PR モードで Git リポジトリ外 → 終了コード 4。"""
        mock_config.return_value = HachimokuConfig()
        result = runner.invoke(app, cli_args)
        assert result.exit_code == ExitCode.INPUT_ERROR

    @pytest.mark.parametrize("cli_args", [[], ["123"]])
    @patch(PATCH_GIT_EXISTS, return_value=False)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_outside_git_repo_shows_hint(
        self,
        mock_config: MagicMock,
        _mock_git: MagicMock,
        cli_args: list[str],
    ) -> None:
        """diff/PR モード Git 外エラーに解決方法ヒントが含まれる。"""
        mock_config.return_value = HachimokuConfig()
        result = runner.invoke(app, cli_args)
        assert "git" in result.output.lower()

    # --- S-4: file モードは Git リポジトリ外でも動作 ---

    @patch(PATCH_GIT_EXISTS, return_value=False)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_FILES)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_file_mode_works_outside_git_repo(
        self,
        mock_config: MagicMock,
        mock_resolve_files: MagicMock,
        mock_run_review: AsyncMock,
        _mock_git: MagicMock,
    ) -> None:
        """file モードは Git リポジトリ外でも正常終了する。"""
        setup_mocks(mock_config, mock_run_review)
        mock_resolve_files.return_value = ResolvedFiles(paths=("/abs/src/auth.py",))
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0
        mock_run_review.assert_called_once()


# --- _save_review_result テスト (I-1) ---


class TestSaveReviewResult:
    """_save_review_result の動作を review_callback 経由で検証する。"""

    @patch(PATCH_SAVE_REVIEW_HISTORY, return_value=Path("/tmp/diff.jsonl"))
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_save_reviews_true_calls_save(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        mock_save: MagicMock,
    ) -> None:
        """save_reviews=True → save_review_history が呼ばれる。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        mock_save.assert_called_once()

    @patch(PATCH_SAVE_REVIEW_HISTORY)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_save_reviews_false_skips_save(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        mock_save: MagicMock,
    ) -> None:
        """save_reviews=False → save_review_history が呼ばれない。"""
        mock_config.return_value = HachimokuConfig(save_reviews=False)
        mock_run_review.return_value = make_engine_result()
        runner.invoke(app)
        mock_save.assert_not_called()

    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_no_project_root_warns_and_exits_normally(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_root: MagicMock,
    ) -> None:
        """find_project_root=None → 警告出力、終了コード不変。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert ".hachimoku/ directory not found" in result.output

    @patch(
        PATCH_SAVE_REVIEW_HISTORY,
        side_effect=__import__(
            "hachimoku.cli._history_writer", fromlist=["HistoryWriteError"]
        ).HistoryWriteError("dir not found"),
    )
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_history_write_error_warns_and_exits_normally(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_save: MagicMock,
    ) -> None:
        """HistoryWriteError → 警告出力、終了コード不変。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "Failed to save review history" in result.output

    @patch(
        PATCH_SAVE_REVIEW_HISTORY,
        side_effect=__import__(
            "hachimoku.cli._history_writer", fromlist=["GitInfoError"]
        ).GitInfoError("git not found"),
    )
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_git_info_error_warns_and_exits_normally(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_save: MagicMock,
    ) -> None:
        """GitInfoError → 警告出力、終了コード不変。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "Failed to save review history" in result.output

    @patch(
        PATCH_SAVE_REVIEW_HISTORY,
        side_effect=RuntimeError("unexpected"),
    )
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_unexpected_error_warns_and_exits_normally(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_save: MagicMock,
    ) -> None:
        """予期しない例外 → 警告出力、終了コード不変（C-1 修正の検証）。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "Unexpected error saving review history" in result.output
