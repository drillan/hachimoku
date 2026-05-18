# SP1-1: 移行前タグ・旧エンジン撤去 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `claude -p` を起動する pydantic-ai ベースのレビューエンジンを撤去し、薄い CLI の土台（`init` / `agents` のみ）まで縮小する。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` の SP1 のうち「エンジン撤去」フェーズ。再利用対象（`_target` / `_diff_filter` / git・gh 読取専用許可リスト）を `engine/` 外の中立モジュールへ退避してから `engine/` を削除する。モデル再形成・`select` / `aggregate` 実装は後続計画。

**Tech Stack:** Python 3.13+ / Typer / pydantic v2 / uv / pytest / ruff / mypy

---

## 順序チェック（各タスク完了後に何がビルド可能か）

| 完了タスク | 状態 |
|---|---|
| Task 1 | コード変更なし。`v0.0.41` タグと Release が存在 |
| Task 2 | `hachimoku.security` 追加。既存コードは無変更でビルド・全テスト通過 |
| Task 3 | `_target` / `_diff_filter` を移設。参照元を更新済みでビルド・全テスト通過 |
| Task 4 | `engine/` 削除。`cli/_app.py` がまだ engine を import するため**ビルド不可**（Task 5 とセットで完成させる） |
| Task 5 | `cli/_app.py` 再形成。ビルド可能・`8moku` 系コマンド動作 |
| Task 6 | pydantic-ai / claudecode-model 依存削除。`uv sync` 後に全テスト通過 |

**重要:** Task 4 と Task 5 はコミット境界を分けるが、Task 4 単独ではリポジトリがビルド不可状態になる。Task 4・Task 5 を連続実行し、ビルド可能な状態は Task 5 のコミットで回復させること。

## File Structure

**新規作成:**
- `src/hachimoku/security/__init__.py` — security サブパッケージ
- `src/hachimoku/security/readonly_allowlist.py` — git/gh 読取専用許可リスト（SP3 の hook が消費）
- `src/hachimoku/review/__init__.py` — review サブパッケージ
- `src/hachimoku/review/target.py` — `engine/_target.py` の移設先
- `src/hachimoku/review/diff_filter.py` — `engine/_diff_filter.py` の移設先
- `tests/unit/security/__init__.py`, `tests/unit/security/test_readonly_allowlist.py`
- `tests/unit/review/__init__.py`

**移動:**
- `tests/unit/engine/test_target.py` → `tests/unit/review/test_target.py`
- `tests/unit/engine/test_diff_filter.py` → `tests/unit/review/test_diff_filter.py`
- `tests/unit/engine/test_diff_filter_integration.py` → `tests/unit/review/test_diff_filter_integration.py`

**削除:** `src/hachimoku/engine/` 配下の以下（`_target.py` / `_diff_filter.py` を除く全ファイル）と、対応するテスト。
`_aggregator.py` `_cancel_scope_guard.py` `_catalog.py` `_context.py` `_engine.py` `_executor.py` `_instruction.py` `_live_progress.py` `_model_resolver.py` `_prefetch.py` `_progress.py` `_resolver.py` `_runner.py` `_selector.py` `_signal.py` `__init__.py` `_tools/`（`_file.py` `_gh.py` `_git.py` `__init__.py`）

> `_selector.py`（applicability 評価）と `_aggregator.py`（非 LLM 集約）のロジックは後続計画（`select` / `aggregate`）で必要になるが、Task 1 のタグ `v0.0.41` から復元できるため本計画で削除してよい。

**変更:** `src/hachimoku/cli/_app.py`、`src/hachimoku/cli/_history_writer.py`、`pyproject.toml`

---

## Task 1: 移行前タグと軽量 Release

**Files:** なし（git / GitHub 操作のみ）

- [ ] **Step 1: ユーザーに確認する**

外部公開を伴うため、実行前に必ずユーザーへ確認すること。確認事項:
- タグ名（既定案: `v0.0.41`）
- 軽量 Release を作成してよいか
- タグ対象コミット（既定: `main` の現在の HEAD）

ユーザーが承認するまで Step 2 以降に進まない。

- [ ] **Step 2: 注釈付きタグを作成する**

Run:
```bash
git tag -a v0.0.41 -m "Last claude -p based release before Agent Skills migration"
```

- [ ] **Step 3: タグを push する（ユーザー確認後）**

Run: `git push origin v0.0.41`
Expected: `* [new tag] v0.0.41 -> v0.0.41`

- [ ] **Step 4: 軽量 Release を作成する（ユーザー確認後）**

Run:
```bash
gh release create v0.0.41 \
  --title "v0.0.41 — last claude -p based version" \
  --notes "Agent Skills 移行前の最終版。これ以降は Claude Code プラグイン構成へ移行します。設計: docs/superpowers/specs/2026-05-18-skill-migration-design.md"
```
Expected: Release の URL が出力される。

---

## Task 2: 読取専用許可リストを security モジュールへ抽出

**Files:**
- Create: `src/hachimoku/security/__init__.py`
- Create: `src/hachimoku/security/readonly_allowlist.py`
- Test: `tests/unit/security/__init__.py`, `tests/unit/security/test_readonly_allowlist.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/security/__init__.py` を空ファイルで作成し、`tests/unit/security/test_readonly_allowlist.py` を作成:

```python
"""readonly_allowlist の構造テスト。SP3 の git/gh 書き込み禁止 hook が消費する。"""

from __future__ import annotations

from hachimoku.security.readonly_allowlist import (
    ALLOWED_GH_PATTERNS,
    ALLOWED_GIT_SUBCOMMANDS,
    IMPLICIT_POST_FLAGS,
)


class TestReadonlyAllowlist:
    def test_git_subcommands_are_read_only(self) -> None:
        assert ALLOWED_GIT_SUBCOMMANDS == frozenset(
            {
                "diff",
                "grep",
                "log",
                "show",
                "status",
                "merge-base",
                "rev-parse",
                "branch",
                "ls-files",
            }
        )

    def test_git_allowlist_excludes_mutating_subcommands(self) -> None:
        for mutating in ("push", "commit", "reset", "checkout", "restore", "clean"):
            assert mutating not in ALLOWED_GIT_SUBCOMMANDS

    def test_gh_patterns_are_read_only(self) -> None:
        assert ALLOWED_GH_PATTERNS == frozenset(
            {("pr", "view"), ("pr", "diff"), ("issue", "view"), ("api",)}
        )

    def test_implicit_post_flags(self) -> None:
        assert IMPLICIT_POST_FLAGS == frozenset(
            {"-f", "--field", "-F", "--raw-field", "--input"}
        )
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv --directory $PWD run pytest tests/unit/security/test_readonly_allowlist.py -v`
Expected: FAIL（`ModuleNotFoundError: hachimoku.security`）

- [ ] **Step 3: security モジュールを実装する**

`src/hachimoku/security/__init__.py` を空ファイルで作成。`src/hachimoku/security/readonly_allowlist.py` を作成:

```python
"""git / gh の読取専用許可リスト。

旧 engine/_tools/_git.py・_gh.py から抽出した中立モジュール。
SP3 のサブエージェント frontmatter hook（block-git-mutations.sh）が
この定義を唯一の正として参照する。
"""

from __future__ import annotations

from typing import Final

ALLOWED_GIT_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {
        "diff",
        "grep",
        "log",
        "show",
        "status",
        "merge-base",
        "rev-parse",
        "branch",
        "ls-files",
    }
)
"""読み取り専用の git サブコマンド。"""

ALLOWED_GH_PATTERNS: Final[frozenset[tuple[str, ...]]] = frozenset(
    {
        ("pr", "view"),
        ("pr", "diff"),
        ("issue", "view"),
        ("api",),
    }
)
"""読み取り専用の gh サブコマンドパターン。"""

IMPLICIT_POST_FLAGS: Final[frozenset[str]] = frozenset(
    {"-f", "--field", "-F", "--raw-field", "--input"}
)
"""gh api で暗黙的に POST メソッドを使用するフラグ。GET 限定検証で deny する。"""
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv --directory $PWD run pytest tests/unit/security/test_readonly_allowlist.py -v`
Expected: PASS（4 件）

- [ ] **Step 5: コミット**

```bash
git add src/hachimoku/security/ tests/unit/security/
git commit -m "feat: extract read-only git/gh allowlist to security module"
```

---

## Task 3: 再利用モジュール（target / diff_filter）を engine 外へ移設

**Files:**
- Create: `src/hachimoku/review/__init__.py`, `tests/unit/review/__init__.py`
- Move: `engine/_target.py` → `review/target.py`、`engine/_diff_filter.py` → `review/diff_filter.py`
- Move: 対応テスト3本を `tests/unit/review/` へ
- Modify: 上記2モジュールを import している全ファイル

- [ ] **Step 1: review サブパッケージを作る**

`src/hachimoku/review/__init__.py` と `tests/unit/review/__init__.py` を空ファイルで作成。

- [ ] **Step 2: モジュールを git mv で移動する**

```bash
git mv src/hachimoku/engine/_target.py src/hachimoku/review/target.py
git mv src/hachimoku/engine/_diff_filter.py src/hachimoku/review/diff_filter.py
git mv tests/unit/engine/test_target.py tests/unit/review/test_target.py
git mv tests/unit/engine/test_diff_filter.py tests/unit/review/test_diff_filter.py
git mv tests/unit/engine/test_diff_filter_integration.py tests/unit/review/test_diff_filter_integration.py
```

- [ ] **Step 3: 移動した2モジュール内の相対 import を確認・修正する**

`review/target.py` と `review/diff_filter.py` を開き、`from hachimoku.engine._target import ...` / `from hachimoku.engine._diff_filter import ...` という相互参照があれば `from hachimoku.review.target import ...` / `from hachimoku.review.diff_filter import ...` に書き換える。他の engine モジュールへの import が残っていれば、その時点で参照先が削除予定であることを意味するため停止し、依存内容を精査する（`target.py` / `diff_filter.py` は設計上 engine 非依存のはず）。

- [ ] **Step 4: 参照元を一括更新する**

Run（参照箇所の洗い出し）:
```bash
grep -rln 'hachimoku.engine._target\|hachimoku.engine._diff_filter' src/ tests/
```
ヒットした各ファイルで以下を置換する:
- `hachimoku.engine._target` → `hachimoku.review.target`
- `hachimoku.engine._diff_filter` → `hachimoku.review.diff_filter`

少なくとも `src/hachimoku/cli/_app.py`（46 行目 `from hachimoku.engine._target import ...`）と `src/hachimoku/cli/_history_writer.py`（`from hachimoku.engine._target import ...`）が該当する。移動したテスト3本の import も同様に更新する。

- [ ] **Step 5: ビルドとテストを確認する**

Run: `uv --directory $PWD run mypy . && uv --directory $PWD run pytest tests/unit/review -v`
Expected: mypy エラーなし。`tests/unit/review` の全テスト PASS。

- [ ] **Step 6: コミット**

```bash
git add -A
git commit -m "refactor: relocate target/diff_filter out of engine package"
```

---

## Task 4: 旧エンジンの削除

**Files:** `src/hachimoku/engine/` 配下（`review/` へ移設済みの2モジュールを除く全ファイル）と対応テストを削除。

> このタスク完了時点ではリポジトリはビルド不可。Task 5 と連続で実施すること。

- [ ] **Step 1: エンジンの実装ファイルを削除する**

```bash
git rm src/hachimoku/engine/_aggregator.py src/hachimoku/engine/_cancel_scope_guard.py \
  src/hachimoku/engine/_catalog.py src/hachimoku/engine/_context.py \
  src/hachimoku/engine/_engine.py src/hachimoku/engine/_executor.py \
  src/hachimoku/engine/_instruction.py src/hachimoku/engine/_live_progress.py \
  src/hachimoku/engine/_model_resolver.py src/hachimoku/engine/_prefetch.py \
  src/hachimoku/engine/_progress.py src/hachimoku/engine/_resolver.py \
  src/hachimoku/engine/_runner.py src/hachimoku/engine/_selector.py \
  src/hachimoku/engine/_signal.py src/hachimoku/engine/__init__.py
git rm -r src/hachimoku/engine/_tools
```

- [ ] **Step 2: エンジンのテストを削除する**

```bash
git rm tests/unit/engine/test_aggregator.py tests/unit/engine/test_cancel_scope_guard.py \
  tests/unit/engine/test_catalog.py tests/unit/engine/test_context.py \
  tests/unit/engine/test_engine.py tests/unit/engine/test_executor.py \
  tests/unit/engine/test_instruction.py tests/unit/engine/test_live_progress.py \
  tests/unit/engine/test_model_resolver.py tests/unit/engine/test_prefetch.py \
  tests/unit/engine/test_progress.py tests/unit/engine/test_resolver.py \
  tests/unit/engine/test_runner.py tests/unit/engine/test_selector.py \
  tests/unit/engine/test_signal.py tests/unit/engine/test_tools.py
```

- [ ] **Step 3: 空になった engine テストディレクトリを確認する**

Run: `ls tests/unit/engine/`
`__init__.py` のみが残るはず。残れば `git rm tests/unit/engine/__init__.py && rmdir tests/unit/engine` で削除。`src/hachimoku/engine/` ディレクトリも空になっていれば削除する。

- [ ] **Step 4: 残存参照を洗い出す（このタスクではコミットしない）**

Run: `grep -rln 'hachimoku.engine\|from hachimoku.engine' src/`
Expected: `src/hachimoku/cli/_app.py` のみがヒットする（Task 5 で解消）。他がヒットした場合は停止して精査する。

---

## Task 5: CLI 再形成（review コマンド撤去）

**Files:**
- Modify: `src/hachimoku/cli/_app.py`（全面縮小）
- Test: `tests/unit/cli/test_app.py`（既存。review 依存テストを削除し、縮小後の挙動テストへ）

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/cli/test_app.py` に以下のテストを追加（既存ファイルが review 実行を前提にしたテストを含む場合、それらは Step 5 で削除する）:

```python
from typer.testing import CliRunner

from hachimoku.cli._app import app


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
        # 旧 review モード（位置引数でのレビュー）は撤去済み
        result = CliRunner().invoke(app, ["123"])
        assert result.exit_code != 0
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv --directory $PWD run pytest tests/unit/cli/test_app.py::TestAppReducedSurface -v`
Expected: FAIL（現行 `_app.py` は engine を import しており収集時に ImportError、または挙動不一致）

- [ ] **Step 3: `cli/_app.py` を縮小後の内容で全面置換する**

`src/hachimoku/cli/_app.py` を以下の内容で置き換える:

```python
"""CliApp — Typer アプリケーション定義（薄い CLI）。

レビュー実行は Claude Code プラグイン（オーケストレーター skill + サブエージェント）
へ移行した。本 CLI は非課金のローカル操作（init / agents 等）のみを担う。
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path
from typing import Annotated

import typer

from hachimoku.agents import LoadResult, load_agents, load_builtin_agents
from hachimoku.cli._init_handler import InitError, run_init
from hachimoku.config import find_project_root
from hachimoku.models.exit_code import ExitCode

app = typer.Typer(
    name="8moku",
    help="Multi-agent code review — thin CLI (review runs in the Claude Code plugin).",
    add_completion=False,
    invoke_without_command=True,
)


def _version_callback(value: bool) -> None:
    """--version 指定時にバージョン番号を出力して終了する。"""
    if value:
        print(importlib.metadata.version("hachimoku"))
        raise typer.Exit()


def main() -> None:
    """CLI エントリポイント。8moku / hachimoku 両方から呼ばれる。"""
    app()


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """hachimoku — multi-agent code review for Claude Code."""
    if ctx.invoked_subcommand is not None:
        return
    print(
        "hachimoku review is migrating to the Claude Code plugin model.\n"
        "  Design: docs/superpowers/specs/2026-05-18-skill-migration-design.md\n"
        "  Available subcommands: init, agents\n"
        "  Run '8moku --help' for details.",
        file=sys.stderr,
    )
    raise typer.Exit(code=ExitCode.SUCCESS)


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files with defaults.")
    ] = False,
    upgrade: Annotated[
        bool,
        typer.Option(
            "--upgrade",
            help="Update built-in agent definitions using hash comparison.",
        ),
    ] = False,
) -> None:
    """Initialize .hachimoku/ directory with default configuration and agent definitions."""
    try:
        result = run_init(Path.cwd(), force=force, upgrade=upgrade)
    except InitError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    if upgrade:
        for path in result.created:
            print(f"  Added: {path}", file=sys.stderr)
        for path in result.updated:
            print(f"  Updated: {path}", file=sys.stderr)
        for path in result.skipped_customized:
            print(f"  Skipped (customized): {path}", file=sys.stderr)
        for path in result.skipped_up_to_date:
            print(f"  Skipped (up to date): {path}", file=sys.stderr)
        total_changed = len(result.created) + len(result.updated)
        total_skipped = len(result.skipped_customized) + len(result.skipped_up_to_date)
        if total_changed:
            print(
                f"\nUpgraded: {len(result.created)} added, "
                f"{len(result.updated)} updated, {total_skipped} skipped.",
                file=sys.stderr,
            )
        else:
            print(
                "\nAll built-in agents are up to date. Nothing to upgrade.",
                file=sys.stderr,
            )
    else:
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
                "\nAll files already exist."
                " Use --force to overwrite, or --upgrade to add new agents only.",
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
        print(
            f"{agent.name:<{_LIST_NAME_WIDTH}}"
            f"{agent.model:<{_LIST_MODEL_WIDTH}}"
            f"{agent.phase.value:<{_LIST_PHASE_WIDTH}}"
            f"{agent.output_schema}{custom_marker}"
        )


def _print_agent_detail(
    name: str, result: LoadResult, builtin_names: set[str]
) -> None:
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
```

> `config` サブコマンド（未実装スタブ）は撤去する。`_history_writer.py` は `aggregate`（後続計画）で再利用するため**残す**が、本タスクでは `_app.py` から参照しない。`_input_resolver.py` / `_file_resolver.py` / `_markdown_formatter.py` / `review/target.py` / `review/diff_filter.py` も後続計画で再利用するため削除しない（一時的に未使用となる）。

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv --directory $PWD run pytest tests/unit/cli/test_app.py::TestAppReducedSurface -v`
Expected: PASS（4 件）

- [ ] **Step 5: review 依存の旧テストを整理する**

Run: `uv --directory $PWD run pytest tests/unit/cli/ -v`
旧 review モード（位置引数レビュー実行、`--commit`、`run_review` 呼び出し等）を前提にした既存テストは収集エラーまたは失敗する。それらのテスト関数／ファイルを削除する。`init` / `agents` の挙動を検証する既存テストは残す。判断に迷うテストは「`run_review` / `engine` / レビュー実行を参照するか」で切り分ける。

- [ ] **Step 6: 全体の静的検査を確認する**

Run: `uv --directory $PWD run ruff check --fix . && uv --directory $PWD run ruff format . && uv --directory $PWD run mypy .`
Expected: 全てエラーなし。未使用 import が `_app.py` に残っていれば削除する。

- [ ] **Step 7: コミット**

```bash
git add -A
git commit -m "refactor: remove review engine and reduce CLI to init/agents"
```

---

## Task 6: pydantic-ai / claudecode-model 依存の削除

**Files:** Modify `pyproject.toml`

- [ ] **Step 1: 依存が残っていないことを確認する**

Run: `grep -rln 'pydantic_ai\|claudecode_model\|claudecode-model\|pydantic-ai' src/ tests/`
Expected: ヒットなし。ヒットした場合は停止し、該当箇所を解消してから続行する。

- [ ] **Step 2: `pyproject.toml` の dependencies を編集する**

`[project]` の `dependencies` から `"claudecode-model"` と `"pydantic-ai>=1.97.0"` の2行を削除する。`"pydantic>=2.12.5"` と `"typer>=0.21.1"` は残す。

- [ ] **Step 3: ロックファイルを更新する**

Run: `uv --directory $PWD sync`
Expected: pydantic-ai / claudecode-model とその推移的依存が環境から除去される。

- [ ] **Step 4: 全テストと静的検査を確認する**

Run:
```bash
uv --directory $PWD run ruff check . && uv --directory $PWD run mypy . && uv --directory $PWD run pytest
```
Expected: 全テスト PASS、ruff / mypy エラーなし。

- [ ] **Step 5: コミット**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: drop pydantic-ai and claudecode-model dependencies"
```

---

## 完了状態と後続計画

本計画の完了時点:
- `claude -p` を起動するコードは存在しない。pydantic-ai / claudecode-model 依存なし。
- CLI は `8moku init` / `8moku agents` のみ。レビュー実行コマンドは撤去済み。
- 再利用資産（`review/target.py`、`review/diff_filter.py`、`security/readonly_allowlist.py`）は中立モジュールに退避済み。
- モデル（`AgentResult` / `CostInfo` / `ReviewSummary` 等）は旧形状のまま（撤去済みエンジン専用の型は未使用のデッドコードとして残存）。

**後続計画:**
- SP1-2: モデル再形成（`CostInfo` 削除、`AgentResult` を `AgentSuccess | AgentError` に縮小、`elapsed_time` optional 化）＋ `Manifest` 契約定義 ＋ `select` 実装。
- SP1-3: `aggregate` 実装 ＋ JSONL 履歴連携。
- SP2 / SP3: 設計書 §12 のとおり。

`_selector.py`（applicability 評価）・`_aggregator.py`（非 LLM 集約）のロジックは、後続計画でタグ `v0.0.41` の内容を参照して再構成する。
