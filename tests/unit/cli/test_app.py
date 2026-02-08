"""Typer app のテスト。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定（review_callback 経由）。
FR-CLI-003: 終了コードの検証。
FR-CLI-004: stdout/stderr ストリーム分離。
FR-CLI-006: CLI オプション対応表。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。

NOTE: Typer の CliRunner は stderr 分離パラメータを公開しないため、
stderr 出力は result.output（stdout + stderr 混合出力）で検証する。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from hachimoku.cli._app import app
from hachimoku.engine._engine import EngineResult
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport, ReviewSummary

runner = CliRunner()

# --- テストヘルパー ---

_PATCH_RUN_REVIEW = "hachimoku.cli._app.run_review"
_PATCH_RESOLVE_CONFIG = "hachimoku.cli._app.resolve_config"


def _make_engine_result(exit_code: ExitCode = ExitCode.SUCCESS) -> EngineResult:
    """テスト用の最小 EngineResult を生成する。"""
    return EngineResult(
        report=ReviewReport(
            results=[],
            summary=ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
            ),
        ),
        exit_code=exit_code,
    )


def _setup_mocks(
    mock_config: MagicMock,
    mock_run_review: AsyncMock,
    exit_code: ExitCode = ExitCode.SUCCESS,
) -> None:
    """共通のモックセットアップ。"""
    mock_config.return_value = HachimokuConfig()
    mock_run_review.return_value = _make_engine_result(exit_code)


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

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_no_args_exits_with_zero(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なし → diff モード → 正常終了。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_no_args_calls_run_review_with_diff_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なし → DiffTarget で run_review が呼ばれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, DiffTarget)


class TestReviewCallbackPRMode:
    """整数引数で PR モード判定を検証する。"""

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_integer_arg_exits_with_zero(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """整数引数 → PR モード → 正常終了。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, ["123"])
        assert result.exit_code == 0

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_integer_arg_calls_run_review_with_pr_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """整数引数 → PRTarget(pr_number=123) で run_review が呼ばれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["123"])
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, PRTarget)
        assert target.pr_number == 123


class TestReviewCallbackFileMode:
    """パスライク引数で file モード判定を検証する。"""

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_path_like_arg_exits_with_zero(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """パスライク引数 → file モード → 正常終了。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_path_like_arg_calls_run_review_with_file_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """パスライク引数 → FileTarget で run_review が呼ばれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["src/auth.py"])
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert "src/auth.py" in target.paths


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

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_diff_mode_calls_run_review(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なし → DiffTarget で run_review が呼ばれる。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        mock_run_review.assert_called_once()
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, DiffTarget)
        assert target.base_branch == "main"

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_pr_mode_calls_run_review(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """整数引数 → PRTarget(pr_number=123) で run_review が呼ばれる。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, ["123"])
        assert result.exit_code == 0
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, PRTarget)
        assert target.pr_number == 123

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_file_mode_calls_run_review(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """パスライク引数 → FileTarget で run_review が呼ばれる。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert target.paths == ("src/auth.py",)

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_report_output_to_stdout(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """レポート内容が出力に含まれる。"""
        _setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        # 暫定出力は JSON ダンプ。total_issues が含まれることを検証
        assert "total_issues" in result.output


class TestReviewExitCodes:
    """レビュー実行の終了コード検証（FR-CLI-003）。"""

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_exit_code_0_on_success(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.SUCCESS(0) → exit_code 0。"""
        _setup_mocks(mock_config, mock_run_review, ExitCode.SUCCESS)
        result = runner.invoke(app)
        assert result.exit_code == 0

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_exit_code_1_on_critical(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.CRITICAL(1) → exit_code 1。"""
        _setup_mocks(mock_config, mock_run_review, ExitCode.CRITICAL)
        result = runner.invoke(app)
        assert result.exit_code == 1

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_exit_code_2_on_important(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.IMPORTANT(2) → exit_code 2。"""
        _setup_mocks(mock_config, mock_run_review, ExitCode.IMPORTANT)
        result = runner.invoke(app)
        assert result.exit_code == 2

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_exit_code_3_on_execution_error(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """ExitCode.EXECUTION_ERROR(3) → exit_code 3。"""
        _setup_mocks(mock_config, mock_run_review, ExitCode.EXECUTION_ERROR)
        result = runner.invoke(app)
        assert result.exit_code == 3


class TestReviewConfigOverrides:
    """CLI オプションから config_overrides 辞書の構築を検証する（FR-CLI-006）。"""

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_model_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--model → config_overrides に "model" キーが含まれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--model", "gpt-4o"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["model"] == "gpt-4o"

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_timeout_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--timeout → config_overrides に "timeout" キーが含まれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--timeout", "600"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["timeout"] == 600

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_max_turns_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--max-turns → config_overrides に "max_turns" キーが含まれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--max-turns", "5"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["max_turns"] == 5

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_format_option_key_mapping(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--format → config_overrides に "output_format" キーが含まれる（キー名変換）。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--format", "json"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "output_format" in overrides
        assert "format" not in overrides

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_max_files_option_key_mapping(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--max-files → config_overrides に "max_files_per_review" キーが含まれる（キー名変換）。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--max-files", "50"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "max_files_per_review" in overrides
        assert "max_files" not in overrides
        assert overrides["max_files_per_review"] == 50

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_base_branch_option(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--base-branch → config_overrides に "base_branch" キーが含まれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--base-branch", "develop"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["base_branch"] == "develop"

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_no_options_empty_overrides(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """オプション未指定 → config_overrides に設定キーが含まれない（None 除外）。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        # 設定上書きオプションは全て None → 空辞書
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

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_multiple_options_combined(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """複数オプション同時指定 → 全てが config_overrides に含まれる。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--model", "opus", "--timeout", "600", "--format", "json"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["model"] == "opus"
        assert overrides["timeout"] == 600
        assert overrides["output_format"] == "json"


class TestReviewBooleanFlags:
    """boolean フラグペア（--parallel/--no-parallel 等）の三値テスト（R-005）。"""

    # --- parallel ---

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_parallel_flag_true(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--parallel → config_overrides["parallel"] == True。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--parallel"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["parallel"] is True

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_parallel_flag_false(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--no-parallel → config_overrides["parallel"] == False。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--no-parallel"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["parallel"] is False

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_parallel_flag_unset(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """未指定 → config_overrides に "parallel" キーなし。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "parallel" not in overrides

    # --- save_reviews ---

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_save_reviews_flag_true(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--save-reviews → config_overrides["save_reviews"] == True。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--save-reviews"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["save_reviews"] is True

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_save_reviews_flag_false(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--no-save-reviews → config_overrides["save_reviews"] == False。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--no-save-reviews"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["save_reviews"] is False

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_save_reviews_flag_unset(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """未指定 → config_overrides に "save_reviews" キーなし。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "save_reviews" not in overrides

    # --- show_cost ---

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_show_cost_flag_true(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--show-cost → config_overrides["show_cost"] == True。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--show-cost"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["show_cost"] is True

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_show_cost_flag_false(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--no-show-cost → config_overrides["show_cost"] == False。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--no-show-cost"])
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert overrides["show_cost"] is False

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_show_cost_flag_unset(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """未指定 → config_overrides に "show_cost" キーなし。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        overrides = mock_run_review.call_args.kwargs["config_overrides"]
        assert "show_cost" not in overrides


class TestReviewIssueOption:
    """--issue per-invocation オプションの検証。"""

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_issue_passed_to_diff_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """diff モード + --issue → DiffTarget.issue_number に設定される。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, ["--issue", "50"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, DiffTarget)
        assert target.issue_number == 50

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_issue_passed_to_pr_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """PR モード + --issue → PRTarget.issue_number に設定される。"""
        _setup_mocks(mock_config, mock_run_review)
        # NOTE: --issue は位置引数より前に配置する。_ReviewGroup が位置引数を
        # 消費する際にオプションも含めて protected_args に格納するため。
        runner.invoke(app, ["--issue", "50", "123"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, PRTarget)
        assert target.issue_number == 50

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_issue_passed_to_file_target(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """file モード + --issue → FileTarget.issue_number に設定される。"""
        _setup_mocks(mock_config, mock_run_review)
        # NOTE: --issue は位置引数より前に配置する（上記同様の理由）。
        runner.invoke(app, ["--issue", "50", "src/auth.py"])
        target = mock_run_review.call_args.kwargs["target"]
        assert isinstance(target, FileTarget)
        assert target.issue_number == 50

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_no_issue_default_none(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """--issue 未指定 → target.issue_number == None。"""
        _setup_mocks(mock_config, mock_run_review)
        runner.invoke(app)
        target = mock_run_review.call_args.kwargs["target"]
        assert target.issue_number is None


class TestReviewRunReviewError:
    """run_review 実行中の例外ハンドリング。"""

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_run_review_exception_exits_with_3(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """run_review が例外送出 → exit_code 3（EXECUTION_ERROR）。"""
        mock_config.return_value = HachimokuConfig()
        mock_run_review.side_effect = RuntimeError("Engine failed")
        result = runner.invoke(app)
        assert result.exit_code == 3

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_run_review_exception_outputs_error_message(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """run_review 例外時にエラーメッセージが出力される。"""
        mock_config.return_value = HachimokuConfig()
        mock_run_review.side_effect = RuntimeError("Engine failed")
        result = runner.invoke(app)
        assert "error" in result.output.lower()
