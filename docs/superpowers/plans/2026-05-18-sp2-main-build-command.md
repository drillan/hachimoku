# SP2-main: build コマンド Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `8moku build` コマンドを実装する。TOML エージェント定義を Claude Code サブエージェント `.md` ファイルと `manifest.json` へ**純粋機械変換**する。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §6。SP2-pre でビルトインプロンプトが Bash 化済みのため、`build` は `system_prompt` を本文へそのままコピーできる純粋な変換器。変換は I/O を持たない関数（`agents/subagent.py`）と、それを使ってファイルを書く CLI コマンド（`cli/_build.py`）に分離する。

**Tech Stack:** Python 3.13+ / pydantic v2 / Typer / pytest / ruff / mypy / uv

**前提:** SP1 ＋ SP2-pre 完了済みのブランチ `worktree-sp1-engine-removal` の上で実行する。`agents/manifest.py`（`Manifest`/`ManifestEntry`/`MANIFEST_VERSION`）、`agents/models.py`（`AgentDefinition`/`ToolCategory`/`Phase`）、`agents/loader.py`（`load_agents`/`load_builtin_agents`）は実装済み。

---

## 設計決定

### `build` の CLI サーフェス

`8moku build` サブコマンド。引数:
- `--output PATH` — 出力ルートディレクトリ（既定 `.hachimoku/build`）。

`build` は `load_agents(custom_dir=<project>/.hachimoku/agents)` で読み込んだ全エージェント（ビルトイン12 ＋ プロジェクト独自）を変換し、以下を書き出す:
- `<output>/agents/<name>.md` — エージェントごとのサブエージェント定義
- `<output>/manifest.json` — 全エージェントの `Manifest`

### TOML → サブエージェント `.md` の変換規則

各 `AgentDefinition` から以下の `.md` を生成する:

```text
---
name: <AgentDefinition.name>
description: <AgentDefinition.description>
model: <model から claudecode:/anthropic: プレフィックスを除去>
tools: <allowed_tools カテゴリを CC ツール名へマッピング（下表）、正規順で連結>
hooks:                                    # tools に Bash を含む場合のみ
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: ${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh
---
<AgentDefinition.system_prompt をそのまま（SP2-pre で Bash 化済み）>

## Output Contract

When you finish your review, write your findings as a single JSON object
conforming to the schema below to the path `<run_dir>/<name>.json`, where
`<run_dir>` is the run directory provided to you.

```json
<AgentDefinition.resolved_schema.model_json_schema() を 2-space indent で整形>
```
```

**ツールカテゴリ → CC ツールのマッピング:**

| `allowed_tools` カテゴリ | CC ツール |
|---|---|
| `git_read` | `Bash` |
| `gh_read` | `Bash` |
| `file_read` | `Read`, `Grep`, `Glob` |
| `web_fetch` | `WebFetch` |

複数カテゴリの結果は和集合・重複排除し、正規順 `["Bash", "Read", "Grep", "Glob", "WebFetch"]` で並べてカンマ＋空白区切りにする。`allowed_tools` が空ならフロントマターに `tools` 行を出さない。

**`hooks` ブロック**: `tools` に `Bash` を含む場合のみ出力する。`block-git-mutations.sh`（SP3 でプラグインに同梱）への参照。`Bash` を持たないエージェントは git/gh を実行しないため hook 不要。

### TOML → `ManifestEntry`

各 `AgentDefinition` から `ManifestEntry(name=..., applicability=..., phase=..., output_schema=...)` を構築する。全エントリを `Manifest(version=MANIFEST_VERSION, entries=...)` にまとめる。

### 退役エージェント

`selector` / `aggregator` は `load_agents` の対象に含まれない（`AgentDefinition` ではなく `SelectorDefinition`/`AggregatorDefinition`、別ローダー）。`build` は `load_agents` が返す**レビューエージェントのみ**を変換するため、退役分は自然に対象外。

## File Structure

**新規作成:**
- `src/hachimoku/agents/subagent.py` — 純粋変換関数（`render_subagent_md`・`to_manifest_entry`・補助関数）
- `src/hachimoku/cli/_build.py` — `build` コマンド（エージェント読込・変換・ファイル書き出し）
- `tests/unit/agents/test_subagent.py`
- `tests/unit/cli/test_build.py`

**変更:**
- `src/hachimoku/cli/_app.py` — `build` サブコマンドを登録

---

## Task 1: 純粋変換関数（`agents/subagent.py`）

**Files:**
- Create: `src/hachimoku/agents/subagent.py`
- Test: `tests/unit/agents/test_subagent.py`

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で `uv run` を用いて実行する。

- [ ] **Step 1: 事前調査**

`src/hachimoku/agents/models.py` で `AgentDefinition` のフィールド（`name`/`description`/`model`/`output_schema`/`resolved_schema`/`system_prompt`/`allowed_tools`/`applicability`/`phase`）と `ToolCategory` の値、`src/hachimoku/agents/manifest.py` の `ManifestEntry`/`Manifest`/`MANIFEST_VERSION` を確認する。`resolved_schema` は `type[BaseAgentOutput]` で `.model_json_schema()` が呼べる。

- [ ] **Step 2: 失敗するテストを書く**

`tests/unit/agents/test_subagent.py` を作成:

```python
"""TOML → サブエージェント変換の純粋関数テスト。"""

from __future__ import annotations

from hachimoku.agents import load_builtin_agents
from hachimoku.agents.manifest import ManifestEntry
from hachimoku.agents.subagent import (
    render_subagent_md,
    strip_model_prefix,
    to_manifest_entry,
    tools_frontmatter_value,
)


def _agent(name: str = "code-reviewer"):
    result = load_builtin_agents()
    agent = next(a for a in result.agents if a.name == name)
    return agent


class TestStripModelPrefix:
    def test_strips_claudecode_prefix(self) -> None:
        assert strip_model_prefix("claudecode:claude-opus-4-7") == "claude-opus-4-7"

    def test_strips_anthropic_prefix(self) -> None:
        assert strip_model_prefix("anthropic:claude-opus-4-7") == "claude-opus-4-7"

    def test_no_prefix_returned_as_is(self) -> None:
        assert strip_model_prefix("claude-opus-4-7") == "claude-opus-4-7"


class TestToolsFrontmatterValue:
    def test_git_and_file_categories(self) -> None:
        # git_read/gh_read → Bash, file_read → Read/Grep/Glob, 正規順
        assert tools_frontmatter_value(("git_read", "gh_read", "file_read")) == (
            "Bash, Read, Grep, Glob"
        )

    def test_web_fetch_category(self) -> None:
        assert tools_frontmatter_value(("file_read", "web_fetch")) == (
            "Read, Grep, Glob, WebFetch"
        )

    def test_empty_returns_empty_string(self) -> None:
        assert tools_frontmatter_value(()) == ""


class TestToManifestEntry:
    def test_builds_entry_from_agent(self) -> None:
        agent = _agent("code-reviewer")
        entry = to_manifest_entry(agent)
        assert isinstance(entry, ManifestEntry)
        assert entry.name == agent.name
        assert entry.phase == agent.phase
        assert entry.output_schema == agent.output_schema
        assert entry.applicability == agent.applicability


class TestRenderSubagentMd:
    def test_frontmatter_and_body(self) -> None:
        agent = _agent("code-reviewer")
        md = render_subagent_md(agent)
        # フロントマター
        assert md.startswith("---\n")
        assert f"name: {agent.name}\n" in md
        assert "model: claude-opus-4-7\n" in md  # claudecode: 除去済み
        # SP2-pre で Bash 化済みの system_prompt が本文に含まれる
        assert agent.system_prompt.strip() in md
        # Output Contract 節
        assert "## Output Contract" in md
        assert "```json" in md

    def test_bash_agent_has_hook_block(self) -> None:
        # code-reviewer は git_read を持つ → Bash → hook ブロックあり
        agent = _agent("code-reviewer")
        md = render_subagent_md(agent)
        assert "hooks:" in md
        assert "block-git-mutations.sh" in md
        assert "PreToolUse" in md
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/agents/test_subagent.py -v`
Expected: FAIL（`ModuleNotFoundError: hachimoku.agents.subagent`）

- [ ] **Step 4: `agents/subagent.py` を実装する**

`src/hachimoku/agents/subagent.py` を作成する。要件:

- `strip_model_prefix(model: str) -> str` — `claudecode:` または `anthropic:` プレフィックスがあれば除去して返す。なければそのまま返す。
- `tools_frontmatter_value(allowed_tools: tuple[str, ...]) -> str` — `allowed_tools` の各カテゴリを CC ツールへマッピングし、和集合・重複排除のうえ正規順 `("Bash", "Read", "Grep", "Glob", "WebFetch")` で並べ、`", "` 連結した文字列を返す。空なら空文字列。マッピングはモジュール内定数 `_CATEGORY_TO_CC_TOOLS: dict[str, tuple[str, ...]]`（`"git_read": ("Bash",)`, `"gh_read": ("Bash",)`, `"file_read": ("Read", "Grep", "Glob")`, `"web_fetch": ("WebFetch",)`）で定義する。未知カテゴリは `ValueError` を送出（フォールバックしない）。
- `to_manifest_entry(agent: AgentDefinition) -> ManifestEntry` — `ManifestEntry(name=agent.name, applicability=agent.applicability, phase=agent.phase, output_schema=agent.output_schema)`。
- `render_subagent_md(agent: AgentDefinition) -> str` — 上記「TOML → サブエージェント `.md`」の規則どおりの文字列を返す。フロントマターは YAML。`tools` 値が空文字列なら `tools` 行を省く。`tools` に `Bash` を含む場合のみ `hooks` ブロックを出す。本文は `agent.system_prompt`（前後の余分な空白は `.strip()` 程度に正規化）＋ 空行 ＋ `## Output Contract` 節。Output Contract 節には固定の説明文（設計の文面）＋ ```json フェンスで `agent.resolved_schema.model_json_schema()` を `json.dumps(..., indent=2, ensure_ascii=False)` で整形したものを埋め込む。

全関数に型注釈と Google-style docstring を付ける。`hooks` ブロックの `command` は `${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh` 固定。

- [ ] **Step 5: テストが通ることを確認する**

Run: `uv run pytest tests/unit/agents/test_subagent.py -v`
Expected: PASS（10 件）

- [ ] **Step 6: 静的検査とコミット**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy .`
Expected: エラーなし。その後:

```bash
git add src/hachimoku/agents/subagent.py tests/unit/agents/test_subagent.py
git commit -m "feat: add TOML-to-subagent conversion functions"
```

---

## Task 2: build コマンド（`cli/_build.py` + `_app.py` 登録）

**Files:**
- Create: `src/hachimoku/cli/_build.py`
- Modify: `src/hachimoku/cli/_app.py`
- Test: `tests/unit/cli/test_build.py`

- [ ] **Step 1: 事前調査**

`src/hachimoku/agents/loader.py` で `load_agents` のシグネチャ（`custom_dir` 引数、戻り値 `LoadResult` の `.agents`/`.errors`）を確認する。`src/hachimoku/config/__init__.py` の `find_project_root` を確認する。

- [ ] **Step 2: 失敗するテストを書く**

`tests/unit/cli/test_build.py` を作成:

```python
"""build コマンドのテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hachimoku.agents.manifest import Manifest
from hachimoku.cli._app import app


class TestBuildCommand:
    def test_builds_subagent_md_and_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        output = tmp_path / "build"

        result = CliRunner().invoke(app, ["build", "--output", str(output)])

        assert result.exit_code == 0
        # manifest.json が生成され、Manifest として検証できる
        manifest_path = output / "manifest.json"
        assert manifest_path.is_file()
        manifest = Manifest.model_validate_json(manifest_path.read_text())
        assert len(manifest.entries) == 12  # ビルトインレビュー12本
        # 各エントリに対応する .md が生成されている
        agents_dir = output / "agents"
        for entry in manifest.entries:
            md_path = agents_dir / f"{entry.name}.md"
            assert md_path.is_file()
            text = md_path.read_text()
            assert text.startswith("---\n")
            assert "## Output Contract" in text

    def test_code_reviewer_md_has_expected_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        output = tmp_path / "build"
        CliRunner().invoke(app, ["build", "--output", str(output)])

        md = (output / "agents" / "code-reviewer.md").read_text()
        assert "name: code-reviewer\n" in md
        assert "model: claude-opus-4-7\n" in md
        assert "block-git-mutations.sh" in md
```

> ビルトインエントリ件数 `12` は SP2-pre と同じ前提。`8moku init` 等でプロジェクト独自エージェントが無い `tmp_path` 環境ではビルトインのみが対象。

- [ ] **Step 3: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/cli/test_build.py -v`
Expected: FAIL（`build` サブコマンド未登録）

- [ ] **Step 4: `cli/_build.py` を実装する**

`src/hachimoku/cli/_build.py` を作成する。要件:

- `class BuildError(Exception)` — 出力ディレクトリ書き込み失敗、エージェント読み込みエラー等。
- `run_build(output_dir: Path, custom_agents_dir: Path | None) -> int` — 中核処理:
  - `load_agents(custom_dir=custom_agents_dir)` で全エージェントを読み込む。`LoadResult.errors` が非空なら、各エラーを stderr に警告出力する（読み込めたエージェントの変換は継続）。
  - `output_dir / "agents"` を作成（`mkdir(parents=True, exist_ok=True)`）。
  - 各 `AgentDefinition` について `render_subagent_md(agent)` を `output_dir/agents/<name>.md` に書き出す。
  - 全エージェントの `to_manifest_entry(agent)` から `Manifest(version=MANIFEST_VERSION, entries=tuple(...))` を構築し、`output_dir/manifest.json` に `manifest.model_dump_json(indent=2)` で書き出す。
  - 書き出した `.md` 件数を返す。
  - ディレクトリ作成・ファイル書き込みの `OSError` は `BuildError` に変換して送出（フォールバックしない）。
- `build_command(output_dir: Path) -> None` — `build` サブコマンドのエントリ:
  - `find_project_root(Path.cwd())` でプロジェクトルートを求め、あれば `custom_agents_dir = root / ".hachimoku" / "agents"`、なければ `None`。
  - `try: count = run_build(output_dir, custom_agents_dir)` / `except BuildError as exc:` → `print(f"Error: {exc}", file=sys.stderr)` ＋ `raise typer.Exit(code=ExitCode.EXECUTION_ERROR)`。
  - 成功時、`print(f"Built {count} subagents and manifest.json under {output_dir}", file=sys.stderr)`。

import 元: `load_agents` ← `hachimoku.agents`（パッケージから再エクスポート。`_app.py` と同じ）、`render_subagent_md`/`to_manifest_entry` ← `hachimoku.agents.subagent`、`Manifest`/`MANIFEST_VERSION` ← `hachimoku.agents.manifest`、`find_project_root` ← `hachimoku.config`、`ExitCode` ← `hachimoku.models.exit_code`。全関数に型注釈・docstring。

- [ ] **Step 5: `_app.py` に `build` サブコマンドを登録する**

`src/hachimoku/cli/_app.py` に import を追加（既存と重複しないこと）:
```python
from hachimoku.cli._build import build_command
```

`agents` コマンド定義の後に追加:
```python
@app.command()
def build(
    output: Annotated[
        Path,
        typer.Option("--output", help="Output directory for generated subagents."),
    ] = Path(".hachimoku/build"),
) -> None:
    """Build Claude Code subagents and manifest.json from TOML agent definitions."""
    build_command(output)
```

> `output` はデフォルト値 `Path(".hachimoku/build")` を持つため引数順は問題ない（SP1-2b-2 で問題になった `= ...` Ellipsis ではなく実値デフォルトなので mypy 非互換は起きない）。

- [ ] **Step 6: テストが通ることを確認する**

Run: `uv run pytest tests/unit/cli/test_build.py -v`
Expected: PASS（2 件）

- [ ] **Step 7: 静的検査と全テストを確認する**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全てエラーなし、全テスト PASS・収集エラー0。

- [ ] **Step 8: 生成物の目視確認**

Run: `uv run 8moku build --output /tmp/hachimoku-build-check && head -20 /tmp/hachimoku-build-check/agents/code-reviewer.md`
Expected: フロントマター（`name`/`description`/`model`/`tools`/`hooks`）が正しく出力され、`manifest.json` も生成されている。

- [ ] **Step 9: コミット**

```bash
git add src/hachimoku/cli/_build.py src/hachimoku/cli/_app.py tests/unit/cli/test_build.py
git commit -m "feat: add build command for subagent/manifest generation"
```

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 の整備項目（既存計画と同方針） |
| `docs/ja`・`docs/en` | 否 | 利用者向けドキュメントは SP 完了時に一括改訂 |
| `README.md` | 否 | 同上 |
| `CLAUDE.md` | 否 | 影響なし |

## 仕様トレーサビリティ

本計画は設計書 §6 を上位仕様とする。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する（既存計画と同方針）。

## 完了状態と後続計画

本計画の完了時点:
- `8moku build` が TOML エージェント定義をサブエージェント `.md` ＋ `manifest.json` へ機械変換する。
- `agents/subagent.py`（純粋変換）と `cli/_build.py`（CLI）が追加される。
- これで SP2（変換パイプライン）が完成。`select`/`aggregate` が消費する manifest の生成側が揃う。

**後続計画:**
- SP3: Claude Code プラグイン。`build` の出力（ビルトイン12本の `.md` ＋ `manifest.json`）をパッケージビルド時に生成してプラグインへ同梱し、オーケストレーター skill・`block-git-mutations.sh`・`uvx` 配線を実装。
- クリーンアップ: `selector.toml`/`aggregator.toml` ＋ `SelectorDefinition`/`AggregatorDefinition` の撤去。
