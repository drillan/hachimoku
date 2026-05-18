# SP2-pre: ビルトインプロンプトの Bash 化書き換え Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ビルトインレビューエージェント12本の `system_prompt` を、`run_git`/`run_gh`/`read_file`/`list_directory` という旧 hachimoku 固有ツール前提から、Claude Code ネイティブツール（`Bash`/`Read`/`Grep`/`Glob`）前提へ書き換える。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §6 の前提整備（direction A）。ビルトインプロンプトは旧ツール名を計120箇所以上参照し「## Tool Usage」節等に織り込まれているため、`build`（SP2-main）が純粋機械変換になるよう、プロンプトを事前に書き換える。本計画は TOML の `system_prompt` 文字列のみを変更し、構造（フィールド構成・`allowed_tools` 値・`applicability` 等）は一切変えない。

**Tech Stack:** TOML / Python 3.13+（pytest による構造検証）/ uv

**前提:** SP1 完了済みのブランチ `worktree-sp1-engine-removal` の上で実行する。CLAUDE.md「ビルトインエージェント TOML の保護」は「当該ファイル自体が変更対象である場合にのみ修正する」と定めており、本計画は12 TOML を変更対象として明示する（巻き込み修正ではない）。

---

## 対象ファイル

`src/hachimoku/agents/_builtin/` の**レビューエージェント12本**:
`architecture-reviewer.toml` `breaking-change-detector.toml` `code-reviewer.toml` `code-simplifier.toml` `comment-analyzer.toml` `dependency-auditor.toml` `performance-analyzer.toml` `plan-reviewer.toml` `pr-test-analyzer.toml` `security-analyzer.toml` `silent-failure-hunter.toml` `type-design-analyzer.toml`。

実行時に `ls src/hachimoku/agents/_builtin/*.toml` で全 `.toml` を確認すること（`selector.toml`・`aggregator.toml` を除いた全レビューエージェントが対象。上記12本と一致するはず）。

**対象外:** `selector.toml` / `aggregator.toml`。これらは旧 LLM セレクター／アグリゲーター定義であり、新アーキテクチャでは `select`/`aggregate` CLI に置換済み。本計画では触れない（`SelectorDefinition`/`AggregatorDefinition` クラスと併せた撤去は後続のクリーンアップ）。

## 変更しないもの

- TOML の構造（`name`/`description`/`model`/`output_schema`/`allowed_tools`/`applicability`/`phase` 等のフィールド）。`allowed_tools` のカテゴリ値（`git_read` 等）は維持する — カテゴリ → CC `tools` のマッピングは `build`（SP2-main）が行う。
- `system_prompt` のうちツール参照以外の全内容（レビュー方法論・重大度基準・信頼度フィルタ・出力形式・スコアリング等）。

## 書き換えルール

各 TOML の `system_prompt` 文字列に対し、以下の置換を行う。**ツール参照以外は一字一句保持する。**

### ルール1: 「## Tool Usage」節の刷新

`## Tool Usage` 節（`- run_git(args): ...` 等のリスト）を、その TOML が言及するツールに応じて以下のテンプレートで置換する（言及の無い行は省く）:

```text
## Tool Usage
- Use the `Bash` tool to run read-only git/gh commands. Allowed git: diff, log, show, status, merge-base, rev-parse, branch, ls-files. Allowed gh: pr view, pr diff, issue view, api (GET only). Never run commands that modify the repository (push, commit, reset, etc.).
- Use the `Read` tool to read file contents for full context.
- Use the `Glob` and `Grep` tools to discover project structure and related files.
```

git/gh を使わないエージェント（`Bash` 行不要）、ファイル読み取りをしないエージェント等は、不要な行を省く。Web 取得（旧 `web_fetch`）を使うエージェントには `- Use the `WebFetch` tool to fetch external web content.` を加える。

### ルール2: インラインのツール呼び出し記法

| 旧記法 | 新記法 |
|--------|--------|
| `run_git(["diff", "--name-only"])` | `` `git diff --name-only` `` |
| `run_git(["log", "-p", "-S", "name", "--", "path"])` | `` `git log -p -S name -- path` `` |
| `run_gh(["pr", "view"])` | `` `gh pr view` `` |
| `read_file(path)` | the `Read` tool（または「read the file with `Read`」） |
| `list_directory(path, pattern=None)` | the `Glob` / `Grep` tools |

リスト引数は要素を空白区切りで連結し、バッククォートで囲んだコマンド文字列にする。

### ルール3: 散文中のツール名

「Use run_git([...]) to list changed files.」のような散文は「Run `git diff --name-only` to list changed files.」のように、自然な英語として通る形に書き換える。Turn Budget 戦略等で `run_git`/`read_file` を参照する箇所も同様に `git ...` コマンドや `Read` ツールへの言及に直す。

### 書き換え例（`code-reviewer.toml` の Tool Usage 節）

**変更前:**
```text
## Tool Usage
- run_git(args): Read git history and diffs. Allowed: diff, log, show, status, merge-base, rev-parse, branch, ls-files.
- run_gh(args): Read PR metadata. Allowed: pr view, pr diff, issue view, api (GET only).
- read_file(path): Read file contents for full context.
- list_directory(path, pattern=None): Discover project structure and related files.
```

**変更後:**
```text
## Tool Usage
- Use the `Bash` tool to run read-only git/gh commands. Allowed git: diff, log, show, status, merge-base, rev-parse, branch, ls-files. Allowed gh: pr view, pr diff, issue view, api (GET only). Never run commands that modify the repository (push, commit, reset, etc.).
- Use the `Read` tool to read file contents for full context.
- Use the `Glob` and `Grep` tools to discover project structure and related files.
```

そのうえで本文中の `run_git(["diff", "--name-only"])` → `` `git diff --name-only` ``、`run_git(["diff"])` → `` `git diff` ``、`read_file(path)` → 「the `Read` tool」等をルール2・3 に従い全て置換する。

## File Structure

**変更:** `src/hachimoku/agents/_builtin/<reviewer>.toml` ×12（`system_prompt` のみ）

**新規:** `tests/unit/agents/test_builtin_prompts_bash.py` — 12本のプロンプトに旧ツール名が残っていないことを検証する構造テスト

---

## Task 1: 旧ツール名残存を検出する構造テスト

**Files:**
- Create: `tests/unit/agents/test_builtin_prompts_bash.py`

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で `uv run` を用いて実行する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/agents/test_builtin_prompts_bash.py` を作成:

```python
"""ビルトインレビューエージェントのプロンプトが Bash 化済みであることの検証。"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_BUILTIN_DIR = Path(__file__).parents[3] / "src" / "hachimoku" / "agents" / "_builtin"
_RETIRED = {"selector.toml", "aggregator.toml"}
# 旧 hachimoku 固有ツール名（呼び出し記法）
_LEGACY_TOOL_RE = re.compile(r"\b(run_git|run_gh|read_file|list_directory)\s*\(")

_REVIEWER_TOMLS = sorted(
    p for p in _BUILTIN_DIR.glob("*.toml") if p.name not in _RETIRED
)


@pytest.mark.parametrize("toml_path", _REVIEWER_TOMLS, ids=lambda p: p.name)
def test_system_prompt_has_no_legacy_tool_calls(toml_path: Path) -> None:
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    prompt = data["system_prompt"]
    matches = _LEGACY_TOOL_RE.findall(prompt)
    assert not matches, (
        f"{toml_path.name} still references legacy tool calls: {matches}"
    )


def test_reviewer_toml_count() -> None:
    # 退役2本（selector/aggregator）を除く全レビューエージェントが対象
    assert len(_REVIEWER_TOMLS) == 12
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/agents/test_builtin_prompts_bash.py -v`
Expected: `test_system_prompt_has_no_legacy_tool_calls` の大半が FAIL（現状プロンプトは旧ツール名を含む）。`test_reviewer_toml_count` は対象数の確認用（12でなければ対象集合・退役判定を見直す）。

- [ ] **Step 3: コミット（テストのみ先行）**

```bash
git add tests/unit/agents/test_builtin_prompts_bash.py
git commit -m "test: assert builtin prompts are free of legacy tool calls"
```

---

## Task 2: 12本のプロンプトを Bash 化する

**Files:**
- Modify: `src/hachimoku/agents/_builtin/<reviewer>.toml` ×12（`system_prompt` のみ）

- [ ] **Step 1: 対象ファイルを確定する**

Run: `ls src/hachimoku/agents/_builtin/*.toml`
`selector.toml` と `aggregator.toml` を除いた全 `.toml` が対象（12本想定）。

- [ ] **Step 2: 各 TOML の `system_prompt` を書き換える**

12本それぞれについて、上記「書き換えルール」1〜3 を適用する:
- 「## Tool Usage」節をルール1 のテンプレート（当該エージェントが使うツールに応じた行のみ）で置換。
- 本文中の `run_git(...)` / `run_gh(...)` / `read_file(...)` / `list_directory(...)` をルール2 の対応表で置換。
- 散文中のツール名参照をルール3 で自然な英語に整える。
- **ツール参照以外（レビュー方法論・Investigation Protocol・Turn Budget Strategy・Severity Criteria・Scoring・Confidence Filtering・Self-Filtering・Output Format・Quality Principles 等）は一字一句保持する。**

各ファイルの書き換え後、`run_git`/`run_gh`/`read_file`/`list_directory` の呼び出し記法が残っていないことを目視確認する。

- [ ] **Step 3: TOML が壊れていないことを確認する**

Run: `uv run pytest tests/unit/agents/test_builtin_prompts_bash.py -v`
Expected: 全 PASS（旧ツール名なし、12本）。

Run: `uv run python -c "from hachimoku.agents import load_builtin_agents; r = load_builtin_agents(); assert not r.errors, r.errors; print(len(r.agents), 'agents loaded')"`
Expected: ロードエラーなし、全ビルトインエージェントが読み込める（`system_prompt` の `min_length` 等のバリデーションを通る）。

- [ ] **Step 4: 全テストと静的検査を確認する**

Run: `uv run ruff check . && uv run pytest`
Expected: 全テスト PASS・収集エラー0。`system_prompt` の具体的文言に依存する既存テストが失敗した場合、その期待値が「ツール参照」に関するものなら新文言へ更新し、無関係な内容なら書き換えが過剰でないか見直す。

- [ ] **Step 5: `8moku agents` で目視確認する**

Run: `uv run 8moku agents`
Expected: 12本のレビューエージェントが一覧表示され、エラーなし。任意で `uv run 8moku agents code-reviewer` 等で詳細（System Prompt 冒頭）を確認する。

- [ ] **Step 6: コミット**

```bash
git add src/hachimoku/agents/_builtin/
git commit -m "refactor: rewrite builtin prompts for native Bash/Read tools"
```

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 の整備項目（既存計画と同方針） |
| `docs/ja`・`docs/en` | 否 | `agents.md` 等の利用者向け改訂は SP 完了時に一括 |
| `README.md` | 否 | 影響なし |
| `CLAUDE.md` | 否 | 影響なし（`_builtin/*.toml` の `model` プレフィックス規約 `claudecode:` は本計画で変更しない） |

## 仕様トレーサビリティ

本計画は設計書 §6 を上位仕様とする（direction A の前提整備）。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する（既存計画と同方針）。

## 完了状態と後続計画

本計画の完了時点:
- ビルトインレビューエージェント12本の `system_prompt` が `Bash`/`Read`/`Grep`/`Glob` 前提に書き換わる。
- `run_git`/`run_gh`/`read_file`/`list_directory` の呼び出し記法はプロンプトから消える。
- TOML 構造・`allowed_tools` 値・`applicability` 等は不変。

**後続計画:**
- SP2-main: `hachimoku build` — TOML → サブエージェント `.md`（frontmatter は `name`/`description`/`model`/`tools`/`hooks`、本文は書き換え済み `system_prompt` ＋ Output Contract）＋ `manifest.json` を**純粋機械変換**で生成。本計画でプロンプトが Bash 化済みのため、`build` は `system_prompt` を**そのまま本文にコピー**できる。
- 後続クリーンアップ: `selector.toml`/`aggregator.toml` と `SelectorDefinition`/`AggregatorDefinition` の撤去。
- SP3: Claude Code プラグイン。
