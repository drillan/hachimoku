"""CliApp contract — Typer アプリケーション定義。

FR-CLI-001: デュアルコマンド名。
FR-CLI-004: stdout/stderr ストリーム分離。
FR-CLI-006: CLI オプション対応表。
FR-CLI-012: agents サブコマンド。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。
"""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from hachimoku.models.config import OutputFormat  # 既存の OutputFormat を再利用（DRY）

# Typer app インスタンス。pyproject.toml から参照される。
app = typer.Typer(
    name="8moku",
    help="Multi-agent code review CLI tool.",
    add_completion=False,
)


def main() -> None:
    """CLI エントリポイント。pyproject.toml の [project.scripts] から呼び出される。

    8moku と hachimoku の両方で同一の関数が呼ばれる。
    """
    app()


@app.callback(invoke_without_command=True)
def review_callback(
    ctx: typer.Context,
    # 位置引数（可変長）
    args: Annotated[
        list[str] | None,
        typer.Argument(
            default=None,
            help="Review target: PR number, file paths, or empty for diff mode.",
        ),
    ] = None,
    # 設定上書きオプション
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
    format: Annotated[
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

    # 1. 入力モード判定: resolve_input(args or [])
    # 2. 設定上書き辞書構築（None を除外）
    #    注意: CLI パラメータ名と HachimokuConfig フィールド名の対応:
    #    - format → output_format（キー名変換が必要）
    #    - max_files → max_files_per_review（キー名変換が必要）
    #    - max_turns はハイフンなし（Typer が自動変換）
    # 3. ReviewTarget 構築（ResolvedInput + config.base_branch + --issue）
    # 4. run_review(target, config_overrides) 呼び出し
    # 5. stdout にレポート出力
    # 6. ExitCode で終了
    ...


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files.")
    ] = False,
) -> None:
    """Initialize .hachimoku/ directory with default configuration and agent definitions."""
    ...


@app.command()
def agents(
    name: Annotated[
        str | None, typer.Argument(default=None, help="Agent name for detailed info.")
    ] = None,
) -> None:
    """List or inspect agent definitions."""
    ...


@app.command()
def config() -> None:
    """Manage configuration (not implemented in v0.1)."""
    print(
        "Error: 'config' subcommand is not implemented in v0.1. "
        "Edit .hachimoku/config.toml directly to configure settings.",
        file=sys.stderr,
    )
    raise typer.Exit(code=4)
