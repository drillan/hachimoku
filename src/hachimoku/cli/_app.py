"""CliApp — Typer アプリケーション定義。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定。
FR-CLI-003: 終了コード。
FR-CLI-004: stdout/stderr ストリーム分離。
FR-CLI-006: CLI オプション対応表。
FR-CLI-009: ファイル・ディレクトリ・glob パターンの展開。
FR-CLI-011: max_files_per_review 超過時の確認プロンプト。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。
"""

from __future__ import annotations

import asyncio
import sys
import tomllib
from typing import Annotated

import click
import typer
from pydantic import ValidationError
from typer.core import TyperGroup

from hachimoku.cli._file_resolver import FileResolutionError, resolve_files
from hachimoku.cli._init_handler import InitError, run_init
from hachimoku.cli._input_resolver import (
    DiffInput,
    FileInput,
    InputError,
    PRInput,
    ResolvedInput,
    resolve_input,
)
from hachimoku.config import resolve_config
from hachimoku.engine import run_review
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import HachimokuConfig, OutputFormat
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport

_REVIEW_ARGS_KEY = "_review_args"


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
    help="Multi-agent code review CLI tool.",
    add_completion=False,
    invoke_without_command=True,
)


def main() -> None:
    """CLI エントリポイント。pyproject.toml の [project.scripts] から呼び出される。

    8moku と hachimoku の両方で同一の関数が呼ばれる。
    """
    app()


@app.callback()
def review_callback(
    ctx: typer.Context,
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
    except (ValidationError, tomllib.TOMLDecodeError) as e:
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

    # 3.5. file モード: ファイル解決と確認プロンプト（FR-CLI-009, FR-CLI-011）
    if isinstance(resolved, FileInput):
        try:
            resolved_files = resolve_files(resolved.paths)
        except FileResolutionError as e:
            print(f"Error: {e}", file=sys.stderr)
            raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

        if resolved_files is None:
            print(
                "No files found matching the specified paths.",
                file=sys.stderr,
            )
            raise typer.Exit(code=ExitCode.SUCCESS)

        for warning in resolved_files.warnings:
            print(f"Warning: {warning}", file=sys.stderr)

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

    # 5. run_review() 呼び出し
    try:
        result = asyncio.run(
            run_review(target=target, config_overrides=config_overrides)
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        print(f"Error: Review execution failed: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from e

    # 6. stdout にレポート出力
    # 007-output-format 未実装のため、暫定的に JSON のみサポート
    effective_format = (
        config.output_format
        if config.output_format == OutputFormat.JSON
        else OutputFormat.JSON
    )
    report_text = _format_report(result.report, effective_format)
    print(report_text)

    # 7. 終了コード
    raise typer.Exit(code=result.exit_code)


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files with defaults.")
    ] = False,
) -> None:
    """Initialize .hachimoku/ directory with default configuration and agent definitions."""
    from pathlib import Path

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
    # FileInput
    return FileTarget(paths=resolved.paths, issue_number=issue)


def _format_report(report: ReviewReport, output_format: OutputFormat) -> str:
    """レポートを文字列に変換する。

    JSON 形式のみサポート。Markdown 形式は 007-output-format で実装予定。
    """
    if output_format == OutputFormat.JSON:
        return report.model_dump_json(indent=2)
    raise NotImplementedError(
        "Markdown format is not yet implemented (see 007-output-format). "
        "Use --format json."
    )
