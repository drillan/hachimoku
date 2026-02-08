"""Typer app のテスト。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定（review_callback 経由）。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。

NOTE: Typer の CliRunner は mix_stderr をサポートしないため、
stderr 出力は result.output（混合出力）で検証する。
"""

from __future__ import annotations

from typer.testing import CliRunner

from hachimoku.cli._app import app

runner = CliRunner()


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

    def test_no_args_exits_with_zero(self) -> None:
        """引数なし → diff モード → 正常終了（スタブ段階）。"""
        result = runner.invoke(app)
        assert result.exit_code == 0

    def test_no_args_output_contains_diff_mode(self) -> None:
        """スタブ段階では diff モードであることを出力する。"""
        result = runner.invoke(app)
        assert "diff" in result.output.lower()


class TestReviewCallbackPRMode:
    """整数引数で PR モード判定を検証する。"""

    def test_integer_arg_exits_with_zero(self) -> None:
        """整数引数 → PR モード → 正常終了（スタブ段階）。"""
        result = runner.invoke(app, ["123"])
        assert result.exit_code == 0

    def test_integer_arg_output_contains_pr_mode(self) -> None:
        """スタブ段階では PR モードであることを出力する。"""
        result = runner.invoke(app, ["123"])
        assert "pr" in result.output.lower()


class TestReviewCallbackFileMode:
    """パスライク引数で file モード判定を検証する。"""

    def test_path_like_arg_exits_with_zero(self) -> None:
        """パスライク引数 → file モード → 正常終了（スタブ段階）。"""
        result = runner.invoke(app, ["src/auth.py"])
        assert result.exit_code == 0

    def test_path_like_arg_output_contains_file_mode(self) -> None:
        """スタブ段階では file モードであることを出力する。"""
        result = runner.invoke(app, ["src/auth.py"])
        assert "file" in result.output.lower()


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
