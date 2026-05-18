# SP3: Claude Code プラグイン Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** hachimoku を Claude Code プラグインとして提供する。オーケストレーター skill が `select` → サブエージェント並列ディスパッチ → `aggregate` を駆動し、`/hachimoku:review` でレビューを実行する。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §3-§9。**案A**（SP3 計画時の設計判断）: プラグイン同梱エージェントは frontmatter `hooks` を無視するため、サブエージェント `.md` はプラグインに同梱せず、`8moku build` で `.claude/agents/` へ生成する（そこでは hook が有効）。プラグインはオーケストレーター skill・setup skill・`block-git-mutations.sh` を同梱する。

**Tech Stack:** Claude Code プラグイン（`plugin.json` / skill / hook）/ bash ＋ jq / Python 3.13+（`build` の小修正と bash スクリプトのテスト）/ pytest / uv

**前提:** SP1 ＋ SP2 完了済みのブランチ `worktree-sp1-engine-removal` の上で実行する。`8moku init`/`agents`/`select`/`aggregate`/`build`、`security/readonly_allowlist.py` は実装済み。

---

## 設計決定

### プラグイン配置と配布

- プラグインは hachimoku リポジトリ内の `plugin/` ディレクトリに置く（リポジトリ内サブディレクトリのプラグインは Claude Code が許容）。
- 配布: `claude --plugin-dir ./plugin`（開発）、または `drillan/hachimoku#plugin` 形式のインストール。マーケットプレイス登録は将来検討。
- プラグイン名 `hachimoku`。コマンドは `/hachimoku:review` と `/hachimoku:setup`。

### 案A の構成（サブエージェントは `.claude/agents/` へ）

- プラグイン同梱物: `plugin.json`、`skills/review/`（オーケストレーター）、`skills/setup/`、`scripts/block-git-mutations.sh`。**`agents/` ディレクトリは持たない**（同梱すると hook 無視のため）。
- サブエージェント `.md` 12本 ＋ `manifest.json` は `8moku build --output .claude` で `.claude/agents/*.md` ＋ `.claude/manifest.json` として生成する。`.claude/agents/` のサブエージェントは frontmatter `hooks` が有効。
- 生成された各サブエージェント `.md` の hook は `block-git-mutations.sh` を**絶対パス**で参照する必要がある（`.claude/agents/` のファイルでは `${CLAUDE_PLUGIN_ROOT}` が解決されないため）。よって `build` に `--hook-script PATH` を追加し（Task 2）、`setup` skill が `${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh` の絶対パスを渡す。

### `uvx` による薄い CLI 呼び出し

オーケストレーター／setup skill は薄い CLI を `uvx` でエフェメラル実行する:
```
uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku <subcommand> ...
```
`<ref>` はプラグイン版に対応するタグ（リリース時 `v0.1.0`）。本計画では `<ref>` をプレースホルダとし、SKILL.md には固定文字列として記述、リリース時に確定する旨を明記する。`uv`/`uvx` 不在時は skill が明示エラーを出し導入を案内する。

### `block-git-mutations.sh` の脅威モデル

best-effort の多層防御。PreToolUse hook として Bash コマンドを検査し、git/gh の書き込み系を deny する。完全なサンドボックスではない（パイプ・サブシェル等は deny 側に倒す）。許可リストは `security/readonly_allowlist.py` と一致させ、テストで drift を検出する。

## File Structure

**新規作成:**
- `plugin/.claude-plugin/plugin.json` — プラグインマニフェスト
- `plugin/scripts/block-git-mutations.sh` — git/gh 書き込み禁止 hook
- `plugin/skills/setup/SKILL.md` — `/hachimoku:setup`（サブエージェント生成）
- `plugin/skills/review/SKILL.md` — `/hachimoku:review`（オーケストレーター）
- `plugin/README.md` — プラグイン説明・前提（`uv`/`jq`）
- `tests/unit/plugin/test_block_git_mutations.py` — hook スクリプトの allow/deny テスト
- `tests/unit/plugin/__init__.py`

**変更:**
- `src/hachimoku/agents/subagent.py` — `render_subagent_md` に hook スクリプトパス引数を追加
- `src/hachimoku/cli/_build.py` ＋ `src/hachimoku/cli/_app.py` — `build` に `--hook-script` オプション追加
- 対応テスト

---

## Task 1: block-git-mutations.sh（読み取り専用 hook）

**Files:**
- Create: `plugin/scripts/block-git-mutations.sh`
- Create: `tests/unit/plugin/__init__.py`、`tests/unit/plugin/test_block_git_mutations.py`

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で実行する。Python は `uv run`。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/plugin/__init__.py` を空ファイルで作成。`tests/unit/plugin/test_block_git_mutations.py` を作成:

```python
"""block-git-mutations.sh の allow/deny テスト。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hachimoku.security.readonly_allowlist import ALLOWED_GIT_SUBCOMMANDS

_SCRIPT = (
    Path(__file__).parents[3] / "plugin" / "scripts" / "block-git-mutations.sh"
)


def _run_hook(command: str) -> int:
    """hook スクリプトに PreToolUse 入力を渡し、終了コードを返す。"""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
    )
    return result.returncode


class TestBlockGitMutations:
    @pytest.mark.parametrize(
        "command",
        [
            "git diff",
            "git log --oneline",
            "git show HEAD",
            "git status",
            "gh pr view 123",
            "gh pr diff 123",
            "ls -la",  # git/gh 以外はすべて許可
            "cat file.py",
        ],
    )
    def test_allows_read_only_and_non_git(self, command: str) -> None:
        assert _run_hook(command) == 0

    @pytest.mark.parametrize(
        "command",
        [
            "git push",
            "git commit -m x",
            "git reset --hard",
            "git checkout .",
            "git restore .",
            "git clean -fd",
            "git branch -D feature",
            "gh pr close 1",
            "gh pr merge 1",
        ],
    )
    def test_denies_git_gh_mutations(self, command: str) -> None:
        assert _run_hook(command) == 2

    @pytest.mark.parametrize(
        "command",
        [
            "git diff && git push",   # パイプ/連結は deny 側に倒す
            "git diff; git commit",
            "bash -c 'git push'",
        ],
    )
    def test_denies_compound_commands(self, command: str) -> None:
        assert _run_hook(command) == 2

    def test_allowlist_matches_python_definition(self) -> None:
        # スクリプト内 git 許可リストが readonly_allowlist.py と一致すること（drift 検出）
        text = _SCRIPT.read_text()
        for sub in ALLOWED_GIT_SUBCOMMANDS:
            assert sub in text, f"script missing allowed subcommand: {sub}"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/plugin/test_block_git_mutations.py -v`
Expected: FAIL（スクリプト未作成）

- [ ] **Step 3: `plugin/scripts/block-git-mutations.sh` を実装する**

`plugin/scripts/block-git-mutations.sh` を作成する。仕様:

- shebang `#!/usr/bin/env bash`、`set -euo pipefail`。
- stdin から PreToolUse 入力 JSON を読み、`jq -r '.tool_input.command // empty'` で Bash コマンド文字列を取り出す（`jq` 前提。`jq` 不在時はエラーで deny=exit 2 に倒す）。
- コマンドが `git` または `gh` で始まらなければ **exit 0（許可）** — hachimoku の関心は git/gh のみ。
- コマンドにシェル制御文字（`;` `&&` `||` `|` `` ` `` `$(` `bash -c` 等）が含まれる場合は **exit 2（拒否）** — 複合コマンドは安全側に倒す。
- `git` の場合: 第1サブコマンド（最初の非オプショントークン）が許可リスト `{diff, grep, log, show, status, merge-base, rev-parse, branch, ls-files}` に**含まれれば exit 0、含まれなければ exit 2**。`git -c x=y <sub>` のように `-c` 等が先行する場合も第1サブコマンドを正しく取り出す。判定不能なら exit 2。
- `gh` の場合: 先頭2トークンが `{pr view, pr diff, issue view}` または先頭1トークンが `api` なら exit 0、それ以外は exit 2。
- exit 2 の際は stderr に理由（例: `block-git-mutations: denied mutating command: git push`）を出力する。

許可リストの git サブコマンドは `security/readonly_allowlist.py` の `ALLOWED_GIT_SUBCOMMANDS` と同一集合をスクリプト内に記述する（bash 配列）。`gh` パターンも同様。冒頭コメントに「`security/readonly_allowlist.py` と一致させること。drift は `test_block_git_mutations.py::test_allowlist_matches_python_definition` が検出する」と明記する。

`chmod +x plugin/scripts/block-git-mutations.sh` で実行権限を付与する。

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/plugin/test_block_git_mutations.py -v`
Expected: PASS（全パラメータ）

- [ ] **Step 5: コミット**

```bash
git add plugin/scripts/block-git-mutations.sh tests/unit/plugin/
git commit -m "feat: add read-only git/gh guard hook script"
```

---

## Task 2: build に --hook-script オプションを追加

**Files:**
- Modify: `src/hachimoku/agents/subagent.py`
- Modify: `src/hachimoku/cli/_build.py`、`src/hachimoku/cli/_app.py`
- Test: `tests/unit/agents/test_subagent.py`、`tests/unit/cli/test_build.py`

- [ ] **Step 1: 事前調査**

`src/hachimoku/agents/subagent.py` の `render_subagent_md` 現状を読む。現在 hook の `command` は `${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh` をハードコードしている。案A では生成先が `.claude/agents/` のため `${CLAUDE_PLUGIN_ROOT}` が解決されない。hook スクリプトの絶対パスを呼び出し側から渡せるようにする。

- [ ] **Step 2: 失敗するテストを書く**

`tests/unit/agents/test_subagent.py` の `TestRenderSubagentMd` に追加:

```python
    def test_hook_script_path_is_parameterized(self) -> None:
        agent = _agent("code-reviewer")
        md = render_subagent_md(agent, hook_script="/abs/path/to/guard.sh")
        assert "command: /abs/path/to/guard.sh" in md
```

既存の `test_bash_agent_has_hook_block` は `hook_script` 引数なし呼び出しのままなら、`render_subagent_md` の `hook_script` をデフォルト値ありにするか、既存テストも引数付きに更新する（下記 Step 3 の方針に合わせて調整）。

`tests/unit/cli/test_build.py` の `test_code_reviewer_md_has_expected_frontmatter` 系に、`--hook-script` を渡したとき生成 `.md` にそのパスが入る旨のアサーションを追加する。

- [ ] **Step 3: `render_subagent_md` を変更する**

`render_subagent_md(agent: AgentDefinition, *, hook_script: str) -> str` のように **キーワード必須引数 `hook_script`** を追加し、hook ブロックの `command` をハードコードからこの値に置き換える。`to_manifest_entry` 等他関数は変更しない。docstring を更新する。

- [ ] **Step 4: `build` に `--hook-script` を追加する**

`src/hachimoku/cli/_build.py` の `run_build` に `hook_script: str` 引数を追加し、`render_subagent_md(agent, hook_script=hook_script)` の形で渡す。`build_command` にも `hook_script` を通す。`src/hachimoku/cli/_app.py` の `build` サブコマンドに以下を追加:

```python
    hook_script: Annotated[
        str,
        typer.Option(
            "--hook-script",
            help="Absolute path to the read-only git guard hook script.",
        ),
    ] = "${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh",
```

既定値はプラグイン文脈の参照（`setup` skill が絶対パスで上書きする）。`build_command(output, hook_script)` の形で渡す。

- [ ] **Step 5: テストと静的検査**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全エラーなし・全 PASS。`render_subagent_md` のシグネチャ変更に伴い既存呼び出し箇所（`_build.py` 等）が全て更新されていること。

- [ ] **Step 6: コミット**

```bash
git add -A
git commit -m "feat: parameterize subagent hook script path in build"
```

---

## Task 3: プラグイン雛形と setup skill

**Files:**
- Create: `plugin/.claude-plugin/plugin.json`、`plugin/skills/setup/SKILL.md`、`plugin/README.md`

- [ ] **Step 1: `plugin/.claude-plugin/plugin.json` を作成する**

```json
{
  "name": "hachimoku",
  "version": "0.1.0",
  "description": "Multi-agent code review orchestrator for Claude Code.",
  "author": { "name": "driller" },
  "repository": "https://github.com/drillan/hachimoku",
  "license": "MIT"
}
```

- [ ] **Step 2: `plugin/skills/setup/SKILL.md` を作成する**

`/hachimoku:setup` — サブエージェントと manifest を `.claude/` へ生成する skill。内容:

````markdown
---
description: Set up hachimoku review subagents for this project. Run once before the first review, or after upgrading hachimoku.
disable-model-invocation: true
allowed-tools: Bash
---

# hachimoku setup

Generate hachimoku's review subagents and manifest into `.claude/` so that
`/hachimoku:review` can dispatch them.

## Steps

1. Verify `uv` is available by running `uv --version`. If it is not installed,
   stop and tell the user to install `uv` (https://docs.astral.sh/uv/).

2. Run the build command, passing the absolute path of the bundled guard script:

   ```
   uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku build \
     --output .claude \
     --hook-script "${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh"
   ```

   Replace `<ref>` with the pinned hachimoku release matching this plugin
   version (see the plugin README).

3. Confirm that `.claude/agents/` now contains the review subagent `.md`
   files and `.claude/manifest.json` exists. Report the count to the user.
````

> `<ref>` の確定はリリース時。本計画では文字列 `<ref>` のままとし、Task 5 完了後のリリース準備で実タグへ置換する旨を Documentation Impact に記す。

- [ ] **Step 3: `plugin/README.md` を作成する**

プラグインの説明、前提（`uv`／`jq` が必要）、導入手順（`/hachimoku:setup` を最初に1回 → `/hachimoku:review`）、`<ref>` 固定の注意を記述する。

- [ ] **Step 4: 構造を確認する**

Run: `ls -R plugin/`
Expected: `.claude-plugin/plugin.json`、`scripts/block-git-mutations.sh`（Task 1）、`skills/setup/SKILL.md`、`README.md` が揃っている。`plugin.json` が JSON として妥当か `uv run python -c "import json; json.load(open('plugin/.claude-plugin/plugin.json'))"` で確認。

- [ ] **Step 5: コミット**

```bash
git add plugin/.claude-plugin/ plugin/skills/setup/ plugin/README.md
git commit -m "feat: add plugin manifest and setup skill"
```

---

## Task 4: オーケストレーター skill（/hachimoku:review）

**Files:**
- Create: `plugin/skills/review/SKILL.md`

- [ ] **Step 1: `plugin/skills/review/SKILL.md` を作成する**

`/hachimoku:review` — レビュー実行のオーケストレーター。内容:

````markdown
---
description: Run a multi-agent code review. Use when the user asks for a code review of changes, a PR, or files.
argument-hint: [PR number | file paths | empty for diff]
allowed-tools: Bash, Agent, Read
---

# hachimoku review

Orchestrate a multi-agent code review. You are the orchestrator: dispatch
review subagents, but do NOT read diffs or findings into your own context —
keep your context light. Subagents work in isolated context windows.

## Preconditions

- `.claude/manifest.json` and `.claude/agents/` must exist. If not, tell the
  user to run `/hachimoku:setup` first, then stop.
- `uv` must be available (`uv --version`).

## Steps

1. **Determine the target** from `$ARGUMENTS`:
   - empty → diff mode
   - a single integer → PR mode (`--commit` not used)
   - file paths → file mode

2. **Select** — run `select` to compute the dispatch plan. Replace `<ref>`
   with the pinned hachimoku release:

   ```
   uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku select \
     <target args> --manifest .claude/manifest.json
   ```

   Parse the JSON output: it contains `run_dir` and `phases`
   (`early` / `main` / `final`, each a list of agent names).

3. **Dispatch subagents** — for each phase in order (early → main → final),
   dispatch every listed agent **in parallel** using the Agent tool. Give
   each subagent this instruction (substitute the run_dir and agent name):

   > Review the changes for <target>. The run directory is `<run_dir>`.
   > Write your findings JSON to `<run_dir>/<agent-name>.json` per your
   > Output Contract.

   Wait for all agents in a phase before starting the next phase. Do not
   read the subagents' findings yourself.

4. **Aggregate** — after all phases complete:

   ```
   uvx --from git+https://github.com/drillan/hachimoku@<ref> hachimoku aggregate \
     --run-dir <run_dir> --manifest .claude/manifest.json <target args>
   ```

   This prints the Markdown report and exits with a severity-based code.

5. **Present** the Markdown report to the user.

## Notes

- If `uv`/`uvx` is missing, stop with a clear error (do not fall back).
- If `select` reports no applicable agents, tell the user there is nothing
  to review and stop.
````

> このタスクのテストは LLM 挙動を伴うため単体テスト化しない。Task 5（手動 E2E 検証）で確認する。

- [ ] **Step 2: skill ファイルの体裁を確認する**

Run: `head -8 plugin/skills/review/SKILL.md`
Expected: YAML frontmatter（`description`/`argument-hint`/`allowed-tools`）が正しく、本文が続く。

- [ ] **Step 3: コミット**

```bash
git add plugin/skills/review/
git commit -m "feat: add review orchestrator skill"
```

---

## Task 5: E2E 手動検証

**Files:** なし（検証のみ）

- [ ] **Step 1: プラグインをローカル導入して検証する**

`claude --plugin-dir ./plugin` でセッションを起動し、サンプルのレビュー対象がある git リポジトリで:
1. `/hachimoku:setup` を実行 → `.claude/agents/` に12本の `.md`、`.claude/manifest.json` が生成されることを確認。
2. 生成された `.md` の hook `command` が `block-git-mutations.sh` の絶対パスを指していることを確認。
3. `/hachimoku:review` を実行 → `select` → サブエージェント並列起動 → `aggregate` → Markdown レポート提示まで通ることを確認。
4. サブエージェント内で `git push` 等が hook により拒否されることを確認（可能なら）。

検証できない項目があればその旨を報告に記す。本タスクはコミットを伴わない。

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 の整備項目（既存計画と同方針） |
| `docs/ja`・`docs/en` | 要（後続） | SP1〜SP3 完了に伴う利用者向けドキュメント全面改訂（`installation.md`/`cli.md`/`agents.md` 等）。本計画スコープ外、リリース準備でまとめて実施 |
| `README.md` | 要（後続） | プラグイン導入手順への全面改訂。リリース準備でまとめて実施 |
| `plugin/README.md` | 要 | Task 3 で新規作成 |
| `<ref>` 確定 | 要（リリース時） | SKILL.md 内の `<ref>` を実リリースタグ `v0.1.0` へ置換 |

## 仕様トレーサビリティ

本計画は設計書 §3-§9 を上位仕様とする。案A（プラグイン同梱エージェントの `hooks` 無視への対応）は SP3 計画時の設計判断であり、設計書 §8 に追記すべき内容（後続のドキュメント整備で反映）。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する。

## 完了状態と後続計画

本計画の完了時点:
- hachimoku が Claude Code プラグインとして動作する。`/hachimoku:setup` ＋ `/hachimoku:review` でレビューが実行できる。
- 読み取り専用 git/gh 強制が `.claude/agents/` のサブエージェント frontmatter hook ＋ `block-git-mutations.sh` で機能する。
- これで移行（SP1〜SP3）の実装が完成。

**後続（リリース準備）:**
- `selector.toml`/`aggregator.toml` ＋ `SelectorDefinition`/`AggregatorDefinition` の撤去（クリーンアップ）。
- 設計書 §8 への案A 反映、`docs/`・`README.md` の全面改訂。
- SKILL.md の `<ref>` を `v0.1.0` へ確定。
- 移行ブランチを `main` へマージし `v0.1.0` をタグ付け・リリース。
- v2: Codex / GitHub Copilot 対応、APM 配布（設計書 §2 非ゴール）。
