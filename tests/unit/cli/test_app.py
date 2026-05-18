"""Typer app のテスト。

FR-CLI-001: デュアルコマンド名。
FR-CLI-007: .hachimoku/ ディレクトリ構造の初期化。
FR-CLI-008: 既存ファイルのスキップと --force による上書き。
FR-CLI-012: agents サブコマンド。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。
FR-CLI-015: --version フラグ。

NOTE: Typer の CliRunner は stderr 分離パラメータを公開しないため、
stderr 出力は result.output（stdout + stderr 混合出力）で検証する。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachimoku.agents import LoadError
from hachimoku.cli._app import app
from hachimoku.cli._init_handler import InitError, InitResult
from hachimoku.models.exit_code import ExitCode
from tests.unit.cli.conftest import (
    PATCH_FIND_PROJECT_ROOT,
    PATCH_LOAD_AGENTS,
    PATCH_LOAD_BUILTIN_AGENTS,
    make_agent_definition,
    make_load_result,
)

PATCH_RUN_INIT = "hachimoku.cli._app.run_init"

runner = CliRunner()


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
        mock_run_init.return_value = InitResult(
            created=(Path("/tmp/config.toml"),),
        )
        result = runner.invoke(app, ["init"])
        assert "Created:" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_shows_skipped_files(self, mock_run_init: MagicMock) -> None:
        """既存ファイルのスキップ情報が表示される。"""
        mock_run_init.return_value = InitResult(
            skipped=(Path("/tmp/config.toml"),),
        )
        result = runner.invoke(app, ["init"])
        assert "Skipped" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_all_exist_shows_hint(self, mock_run_init: MagicMock) -> None:
        """全ファイル既存時に --force ヒントが表示される。"""
        mock_run_init.return_value = InitResult(
            skipped=(Path("/tmp/config.toml"),),
        )
        result = runner.invoke(app, ["init"])
        assert "--force" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_passes_flag(self, mock_run_init: MagicMock) -> None:
        """init --upgrade が upgrade=True で run_init を呼ぶ。"""
        mock_run_init.return_value = InitResult()
        runner.invoke(app, ["init", "--upgrade"])
        _, kwargs = mock_run_init.call_args
        assert kwargs["upgrade"] is True

    @patch(PATCH_RUN_INIT)
    def test_init_default_no_upgrade(self, mock_run_init: MagicMock) -> None:
        """--upgrade なしでは upgrade=False。"""
        mock_run_init.return_value = InitResult()
        runner.invoke(app, ["init"])
        _, kwargs = mock_run_init.call_args
        assert kwargs["upgrade"] is False

    def test_init_help_shows_upgrade_option(self) -> None:
        """init --help に --upgrade オプションが表示される。"""
        result = runner.invoke(app, ["init", "--help"])
        assert "--upgrade" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_force_passes_flags(self, mock_run_init: MagicMock) -> None:
        """--upgrade --force が force=True, upgrade=True で run_init を呼ぶ。"""
        mock_run_init.return_value = InitResult()
        runner.invoke(app, ["init", "--upgrade", "--force"])
        _, kwargs = mock_run_init.call_args
        assert kwargs["force"] is True
        assert kwargs["upgrade"] is True

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_shows_added_status(self, mock_run_init: MagicMock) -> None:
        """upgrade 結果で Added: が表示される。"""
        mock_run_init.return_value = InitResult(
            created=(Path("/tmp/new-agent.toml"),),
        )
        result = runner.invoke(app, ["init", "--upgrade"])
        assert "Added:" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_shows_updated_status(self, mock_run_init: MagicMock) -> None:
        """upgrade 結果で Updated: が表示される。"""
        mock_run_init.return_value = InitResult(
            updated=(Path("/tmp/code-reviewer.toml"),),
        )
        result = runner.invoke(app, ["init", "--upgrade"])
        assert "Updated:" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_shows_skipped_customized(
        self, mock_run_init: MagicMock
    ) -> None:
        """upgrade 結果で Skipped (customized): が表示される。"""
        mock_run_init.return_value = InitResult(
            skipped_customized=(Path("/tmp/code-reviewer.toml"),),
        )
        result = runner.invoke(app, ["init", "--upgrade"])
        assert "Skipped (customized):" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_shows_skipped_up_to_date(
        self, mock_run_init: MagicMock
    ) -> None:
        """upgrade 結果で Skipped (up to date): が表示される。"""
        mock_run_init.return_value = InitResult(
            skipped_up_to_date=(Path("/tmp/code-reviewer.toml"),),
        )
        result = runner.invoke(app, ["init", "--upgrade"])
        assert "Skipped (up to date):" in result.output

    @patch(PATCH_RUN_INIT)
    def test_init_upgrade_all_up_to_date_message(
        self, mock_run_init: MagicMock
    ) -> None:
        """全て最新時のメッセージが表示される。"""
        mock_run_init.return_value = InitResult(
            skipped_up_to_date=(Path("/tmp/a.toml"),),
        )
        result = runner.invoke(app, ["init", "--upgrade"])
        assert "up to date" in result.output


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


class TestVersion:
    """--version の動作を検証する。"""

    def test_version_exits_with_zero(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_shows_version_number(self) -> None:
        import importlib.metadata

        expected = importlib.metadata.version("hachimoku")
        result = runner.invoke(app, ["--version"])
        assert expected in result.output


class TestAppReducedSurface:
    def test_no_subcommand_prints_migration_guidance(self) -> None:
        result = CliRunner().invoke(app, [])
        assert result.exit_code == 0
        assert "init" in result.output

    def test_init_command_exists(self) -> None:
        result = CliRunner().invoke(app, ["init", "--help"])
        assert result.exit_code == 0

    def test_agents_command_exists(self) -> None:
        result = CliRunner().invoke(app, ["agents", "--help"])
        assert result.exit_code == 0

    def test_review_positional_args_are_rejected(self) -> None:
        result = CliRunner().invoke(app, ["123"])
        assert result.exit_code != 0
