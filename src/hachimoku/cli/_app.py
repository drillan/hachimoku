"""CliApp — Typer アプリケーション定義。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定。
FR-CLI-003: 終了コード。
FR-CLI-004: stdout/stderr ストリーム分離。
FR-CLI-005: 出力形式選択（--format）。
FR-CLI-006: CLI オプション対応表。
FR-CLI-009: ファイル・ディレクトリ・glob パターンの展開。
FR-CLI-011: max_files_per_review 超過時の確認プロンプト。
FR-CLI-012: agents サブコマンド。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。
FR-CLI-015: --version フラグ。
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Annotated, assert_never

import click
import typer
from pydantic import ValidationError
from typer.core import TyperGroup

from hachimoku.agents import LoadResult, load_agents, load_builtin_agents
from hachimoku.cli._file_resolver import FileResolutionError, resolve_files
from hachimoku.cli._init_handler import InitError, run_init
from hachimoku.cli._markdown_formatter import format_markdown
from hachimoku.cli._input_resolver import (
    DiffInput,
    FileInput,
    InputError,
    PRInput,
    ResolvedInput,
    resolve_input,
)
from hachimoku.config import find_project_root, resolve_config
from hachimoku.engine import run_review
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import HachimokuConfig, OutputFormat
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport

_REVIEW_ARGS_KEY = "_review_args"


_GIT_CHECK_TIMEOUT_SECONDS = 5


def _is_git_repository() -> bool:
    """カレントディレクトリが Git リポジトリ内かどうか判定する。

    サブディレクトリや worktree 環境でも正しく動作するよう
    ``git rev-parse --git-dir`` を使用する。
    """
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            timeout=_GIT_CHECK_TIMEOUT_SECONDS,
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


class _ReviewGroup(TyperGroup):
    """Typer Group のサブコマンド解決をオーバーライドし、位置引数との共存を実現する。

    Click の Group はサブコマンド名にマッチしない引数を UsageError にするが、
    hachimoku CLI ではサブコマンドでない引数を InputResolver に渡す必要がある。
    このクラスは resolve_command が失敗した場合に callback へ引数を渡す。
    """

    # click.Group.invoke の戻り値型が object であり、オーバーライドのため合わせている
    def invoke(self, ctx: click.Context) -> object:
        if not ctx._protected_args:
            if self.invoke_without_command:
                with ctx:
                    return click.Command.invoke(self, ctx)
            ctx.fail("Missing command.")

        args = [*ctx._protected_args, *ctx.args]
        ctx.args = []
        ctx._protected_args = []

        try:
            cmd_name, cmd, remaining = self.resolve_command(ctx, args)
        except click.UsageError as exc:
            if "No such command" not in str(exc):
                raise
            ctx.ensure_object(dict)
            ctx.obj[_REVIEW_ARGS_KEY] = args
            ctx.invoked_subcommand = None
            with ctx:
                return click.Command.invoke(self, ctx)

        if cmd is None:
            ctx.fail(f"Could not resolve command: {args}")
        with ctx:
            ctx.invoked_subcommand = cmd_name
            click.Command.invoke(self, ctx)
            sub_ctx = cmd.make_context(
                cmd_name,  # type: ignore[arg-type]
                remaining,
                parent=ctx,
            )
            with sub_ctx:
                return sub_ctx.command.invoke(sub_ctx)


app = typer.Typer(
    name="8moku",
    cls=_ReviewGroup,
    help=(
        "Multi-agent code review CLI tool.\n\n"
        "Review modes (determined by arguments):\n\n"
        "  (no args)     diff mode - review current branch changes\n\n"
        "  <integer>     PR mode   - review specified GitHub PR\n\n"
        "  <path...>     file mode - review specified files/directories"
    ),
    add_completion=False,
    invoke_without_command=True,
)


def _version_callback(value: bool) -> None:
    """--version 指定時にバージョン番号を出力して終了する。"""
    if value:
        print(importlib.metadata.version("hachimoku"))
        raise typer.Exit()


def main() -> None:
    """CLI エントリポイント。pyproject.toml の [project.scripts] から呼び出される。

    8moku と hachimoku の両方で同一の関数が呼ばれる。
    """
    app()


@app.callback()
def review_callback(
    ctx: typer.Context,
    # --version（FR-CLI-015 相当）
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
    # 設定上書きオプション（FR-CLI-006）
    model: Annotated[str | None, typer.Option(help="LLM model name.")] = None,
    timeout: Annotated[
        int | None, typer.Option(help="Timeout in seconds (positive integer).", min=1)
    ] = None,
    max_turns: Annotated[
        int | None,
        typer.Option("--max-turns", help="Max agent turns (positive integer).", min=1),
    ] = None,
    parallel: Annotated[
        bool | None,
        typer.Option(
            "--parallel/--no-parallel", help="Enable/disable parallel execution."
        ),
    ] = None,
    base_branch: Annotated[
        str | None, typer.Option("--base-branch", help="Base branch for diff mode.")
    ] = None,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option("--format", help="Output format: markdown or json."),
    ] = None,
    save_reviews: Annotated[
        bool | None,
        typer.Option("--save-reviews/--no-save-reviews", help="Save review results."),
    ] = None,
    show_cost: Annotated[
        bool | None,
        typer.Option("--show-cost/--no-show-cost", help="Show cost information."),
    ] = None,
    max_files: Annotated[
        int | None,
        typer.Option(
            "--max-files", help="Max files per review (positive integer).", min=1
        ),
    ] = None,
    # per-invocation オプション
    issue: Annotated[
        int | None,
        typer.Option("--issue", help="GitHub Issue number for context.", min=1),
    ] = None,
    # FR-CLI-011: max_files_per_review 超過時の確認スキップ
    no_confirm: Annotated[
        bool, typer.Option("--no-confirm", help="Skip confirmation prompts.")
    ] = False,
) -> None:
    """Execute a code review (default command).

    Without arguments: diff mode (review current branch changes).
    With an integer: PR mode (review specified PR).
    With file paths: file mode (review specified files).
    """
    if ctx.invoked_subcommand is not None:
        return

    # 1. 入力モード判定
    obj = ctx.ensure_object(dict)
    raw_args: list[str] = obj.get(_REVIEW_ARGS_KEY, [])

    try:
        resolved = resolve_input(raw_args or None)
    except InputError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    # 2. config_overrides 辞書構築
    config_overrides = _build_config_overrides(
        model=model,
        timeout=timeout,
        max_turns=max_turns,
        parallel=parallel,
        base_branch=base_branch,
        output_format=output_format,
        save_reviews=save_reviews,
        show_cost=show_cost,
        max_files=max_files,
    )

    # 3. config 解決（DiffTarget の base_branch 取得用）
    try:
        config = resolve_config(cli_overrides=config_overrides)
    except (ValidationError, tomllib.TOMLDecodeError, TypeError) as e:
        print(
            f"Error: Invalid configuration: {e}\n"
            "Check .hachimoku/config.toml for syntax errors or invalid values.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None
    except PermissionError as e:
        print(
            f"Error: Cannot read configuration file: {e}\n"
            "Check file permissions for .hachimoku/config.toml.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    # 3.5. diff/PR モード: Git リポジトリチェック
    if isinstance(resolved, (DiffInput, PRInput)) and not _is_git_repository():
        mode = "diff" if isinstance(resolved, DiffInput) else "PR"
        print(
            f"Error: {mode} mode requires a Git repository.\n"
            "Run 'git init' to initialize a Git repository, "
            "or use file mode to review specific files.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.INPUT_ERROR)

    # 3.6. file モード: ファイル解決と確認プロンプト（FR-CLI-009, FR-CLI-011）
    if isinstance(resolved, FileInput):
        try:
            resolved_files, file_warnings = resolve_files(resolved.paths)
        except FileResolutionError as e:
            print(f"Error: {e}", file=sys.stderr)
            raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

        for warning in file_warnings:
            print(f"Warning: {warning}", file=sys.stderr)

        if resolved_files is None:
            print(
                "No files found matching the specified paths.",
                file=sys.stderr,
            )
            raise typer.Exit(code=ExitCode.SUCCESS)

        file_count = len(resolved_files.paths)
        if file_count > config.max_files_per_review and not no_confirm:
            confirmed = typer.confirm(
                f"{file_count} files found, exceeding limit of "
                f"{config.max_files_per_review}. Continue?",
                abort=False,
                err=True,
            )
            if not confirmed:
                raise typer.Exit(code=ExitCode.SUCCESS)

        resolved = FileInput(paths=resolved_files.paths)

    # 4. ReviewTarget 構築
    target = _build_target(resolved, config, issue)

    # 4.5. カスタムエージェントディレクトリ解決
    project_root = find_project_root(Path.cwd())
    custom_agents_dir = (
        (project_root / ".hachimoku" / "agents") if project_root else None
    )

    # 5. run_review() 呼び出し
    try:
        result = asyncio.run(
            run_review(
                target=target,
                config_overrides=config_overrides,
                custom_agents_dir=custom_agents_dir,
            )
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(
            f"Error: Review execution failed: {e}\n"
            "Check your configuration and network connection. Use --help for options.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from e

    # 6. stdout にレポート出力
    report_text = _format_report(result.report, config.output_format)
    print(report_text)

    # 6.5. JSONL 蓄積 (FR-025)
    if config.save_reviews:
        _save_review_result(target, result.report)

    # 7. 終了コード
    raise typer.Exit(code=result.exit_code)


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files with defaults.")
    ] = False,
) -> None:
    """Initialize .hachimoku/ directory with default configuration and agent definitions."""
    try:
        result = run_init(Path.cwd(), force=force)
    except InitError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    for path in result.created:
        print(f"  Created: {path}", file=sys.stderr)
    for path in result.skipped:
        print(f"  Skipped (already exists): {path}", file=sys.stderr)

    if result.created:
        print(
            f"\nInitialized .hachimoku/ "
            f"({len(result.created)} created, {len(result.skipped)} skipped).",
            file=sys.stderr,
        )
    else:
        print(
            "\nAll files already exist. Use --force to overwrite.",
            file=sys.stderr,
        )


@app.command()
def agents(
    name: Annotated[
        str | None, typer.Argument(help="Agent name for detailed info.")
    ] = None,
) -> None:
    """List or inspect agent definitions."""
    try:
        project_root = find_project_root(Path.cwd())
        custom_dir = (project_root / ".hachimoku" / "agents") if project_root else None
        result = load_agents(custom_dir=custom_dir)
        builtin_result = load_builtin_agents()
    except Exception as e:
        print(
            f"Error: Failed to load agent definitions: {e}\n"
            "Run '8moku init' to initialize the project, or check directory permissions.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None

    builtin_names = {a.name for a in builtin_result.agents}

    for error in (*builtin_result.errors, *result.errors):
        print(
            f"Warning: Failed to load agent '{error.source}': {error.message}",
            file=sys.stderr,
        )

    if name is None:
        _print_agents_list(result, builtin_names)
    else:
        _print_agent_detail(name, result, builtin_names)


# --- agents サブコマンド表示ヘルパー ---

_LIST_NAME_WIDTH = 28
_LIST_MODEL_WIDTH = 32
_LIST_PHASE_WIDTH = 8

_SYSTEM_PROMPT_SUMMARY_LINES = 3


def _print_agents_list(result: LoadResult, builtin_names: set[str]) -> None:
    """エージェント一覧をテーブル形式で stdout に表示する。"""
    header = (
        f"{'NAME':<{_LIST_NAME_WIDTH}}"
        f"{'MODEL':<{_LIST_MODEL_WIDTH}}"
        f"{'PHASE':<{_LIST_PHASE_WIDTH}}"
        f"{'SCHEMA'}"
    )
    print(header)
    print("-" * len(header))

    for agent in sorted(result.agents, key=lambda a: a.name):
        custom_marker = "  [custom]" if agent.name not in builtin_names else ""
        line = (
            f"{agent.name:<{_LIST_NAME_WIDTH}}"
            f"{agent.model:<{_LIST_MODEL_WIDTH}}"
            f"{agent.phase.value:<{_LIST_PHASE_WIDTH}}"
            f"{agent.output_schema}{custom_marker}"
        )
        print(line)


def _print_agent_detail(name: str, result: LoadResult, builtin_names: set[str]) -> None:
    """エージェント詳細を stdout に表示する。見つからない場合は終了コード 4。"""
    agent = next((a for a in result.agents if a.name == name), None)
    if agent is None:
        available = ", ".join(sorted(a.name for a in result.agents))
        print(
            f"Error: Agent '{name}' not found.\nAvailable agents: {available}",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.INPUT_ERROR)

    custom_marker = " [custom]" if name not in builtin_names else ""
    print(f"Name:             {agent.name}{custom_marker}")
    print(f"Description:      {agent.description}")
    print(f"Model:            {agent.model}")
    print(f"Phase:            {agent.phase.value}")
    print(f"Output Schema:    {agent.output_schema}")

    app_rule = agent.applicability
    if app_rule.always:
        print("Applicability:    always")
    else:
        if app_rule.file_patterns:
            print(f"File Patterns:    {', '.join(app_rule.file_patterns)}")
        if app_rule.content_patterns:
            print(f"Content Patterns: {', '.join(app_rule.content_patterns)}")

    if agent.allowed_tools:
        print(f"Allowed Tools:    {', '.join(agent.allowed_tools)}")
    else:
        print("Allowed Tools:    (none)")

    prompt_lines = agent.system_prompt.strip().splitlines()
    summary = "\n".join(prompt_lines[:_SYSTEM_PROMPT_SUMMARY_LINES])
    if len(prompt_lines) > _SYSTEM_PROMPT_SUMMARY_LINES:
        summary += "\n..."
    print(f"System Prompt:\n{summary}")


@app.command()
def config() -> None:
    """Manage configuration (not implemented in v0.1)."""
    print(
        "Error: 'config' subcommand is not implemented in v0.1. "
        "Edit .hachimoku/config.toml directly to configure settings.",
        file=sys.stderr,
    )
    raise typer.Exit(code=ExitCode.INPUT_ERROR)


def _build_config_overrides(
    *,
    model: str | None,
    timeout: int | None,
    max_turns: int | None,
    parallel: bool | None,
    base_branch: str | None,
    output_format: OutputFormat | None,
    save_reviews: bool | None,
    show_cost: bool | None,
    max_files: int | None,
) -> dict[str, object]:
    """CLI オプションから config_overrides 辞書を構築する。

    None 値は「未指定」として除外する。
    CLI オプション名 --max-files は config キー max_files_per_review に対応する。
    """
    raw: dict[str, object] = {
        "model": model,
        "timeout": timeout,
        "max_turns": max_turns,
        "parallel": parallel,
        "base_branch": base_branch,
        "output_format": output_format,
        "save_reviews": save_reviews,
        "show_cost": show_cost,
        "max_files_per_review": max_files,
    }
    return {k: v for k, v in raw.items() if v is not None}


def _build_target(
    resolved: ResolvedInput,
    config: HachimokuConfig,
    issue: int | None,
) -> DiffTarget | PRTarget | FileTarget:
    """ResolvedInput と config から ReviewTarget を構築する。"""
    if isinstance(resolved, DiffInput):
        return DiffTarget(base_branch=config.base_branch, issue_number=issue)
    if isinstance(resolved, PRInput):
        return PRTarget(pr_number=resolved.pr_number, issue_number=issue)
    if isinstance(resolved, FileInput):
        return FileTarget(paths=resolved.paths, issue_number=issue)
    assert_never(resolved)


def _save_review_result(
    target: DiffTarget | PRTarget | FileTarget,
    report: ReviewReport,
) -> None:
    """レビュー結果を JSONL に保存する。

    FR-025: save_reviews=true のとき、レビュー完了後に呼び出される。
    保存処理のエラーはレビュー結果の終了コードに影響しない。
    """
    from hachimoku.cli._history_writer import (
        GitInfoError,
        HistoryWriteError,
        save_review_history,
    )

    try:
        project_root = find_project_root(Path.cwd())
        if project_root is None:
            print(
                "Warning: Cannot save review history: .hachimoku/ directory not found.",
                file=sys.stderr,
            )
            return

        reviews_dir = project_root / ".hachimoku" / "reviews"
        saved_path = save_review_history(reviews_dir, target, report)
        print(f"Review saved to {saved_path}", file=sys.stderr)
    except (HistoryWriteError, GitInfoError) as e:
        print(f"Warning: Failed to save review history: {e}", file=sys.stderr)
    except Exception as e:
        print(
            f"Warning: Unexpected error saving review history: {type(e).__name__}: {e}",
            file=sys.stderr,
        )


def _format_report(report: ReviewReport, output_format: OutputFormat) -> str:
    """レポートを指定形式の文字列に変換する。"""
    if output_format == OutputFormat.JSON:
        return report.model_dump_json(indent=2)
    if output_format == OutputFormat.MARKDOWN:
        return format_markdown(report)
    assert_never(output_format)
