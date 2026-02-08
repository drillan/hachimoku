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

from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import ValidationError
from typer.testing import CliRunner

from hachimoku.cli._app import app
from hachimoku.cli._file_resolver import FileResolutionError, ResolvedFiles
from hachimoku.cli._init_handler import InitError, InitResult
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.exit_code import ExitCode
from tests.unit.cli.conftest import (
    PATCH_RESOLVE_CONFIG,
    PATCH_RESOLVE_FILES,
    PATCH_RUN_REVIEW,
    make_engine_result,
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


class TestReviewBooleanFlags:
    """boolean フラグペア（--parallel/--no-parallel 等）の三値テスト（R-005）。"""

    # --- parallel ---

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_parallel_flag_true(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--parallel → config_overrides["parallel"] == True。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--parallel"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["parallel"] is True

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_parallel_flag_false(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--no-parallel → config_overrides["parallel"] == False。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--no-parallel"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["parallel"] is False

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_parallel_flag_unset(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """未指定 → config_overrides に "parallel" キーなし。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "parallel" not in overrides

    # --- save_reviews ---

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_save_reviews_flag_true(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--save-reviews → config_overrides["save_reviews"] == True。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--save-reviews"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["save_reviews"] is True

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_save_reviews_flag_false(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--no-save-reviews → config_overrides["save_reviews"] == False。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--no-save-reviews"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["save_reviews"] is False

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_save_reviews_flag_unset(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """未指定 → config_overrides に "save_reviews" キーなし。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "save_reviews" not in overrides

    # --- show_cost ---

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_show_cost_flag_true(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--show-cost → config_overrides["show_cost"] == True。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--show-cost"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["show_cost"] is True

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_show_cost_flag_false(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--no-show-cost → config_overrides["show_cost"] == False。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--no-show-cost"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["show_cost"] is False

    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_show_cost_flag_unset(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """未指定 → config_overrides に "show_cost" キーなし。"""
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "show_cost" not in overrides


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
