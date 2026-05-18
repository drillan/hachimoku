# SP1-3: aggregate コマンド Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `8moku aggregate` コマンドを実装する。サブエージェントの findings JSON を run_dir から読み・検証・集約し、`ReviewReport` を構築して Markdown レポート出力・JSONL 履歴追記・重要度に応じた終了コードを行う。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §7・§9・§10。`aggregate` は LLM 不要の決定的コマンド。`select` が run_dir に書き出す `dispatch-plan.json`（期待エージェント一覧）と manifest（スキーマ名）を読み、各 findings JSON を該当スキーマで検証する。旧 LLM アグリゲーター由来の `AggregatedReport` 系は生成元が無いため削除する。

**Tech Stack:** Python 3.13+ / pydantic v2 / Typer / pytest / ruff / mypy / uv

**前提:** SP1-1・SP1-2a・SP1-2b-1・SP1-2b-2 完了済みのブランチ `worktree-sp1-engine-removal` の上で実行する。`agents/manifest.py`・`agents/applicability.py`・`cli/_select.py`・`review/changeset.py`・`models/schemas/*`・`cli/_history_writer.py`・`cli/_markdown_formatter.py` は実装済み。

---

## 設計決定

### `aggregate` の入力と CLI サーフェス

`8moku aggregate` サブコマンド。引数:
- `--run-dir PATH` — `select` が作成した run_dir（**必須**）。`<run_dir>/dispatch-plan.json` と `<run_dir>/<agent>.json` 群を含む。
- `--manifest PATH` — `Manifest` JSON（**必須**）。各エージェントの `output_schema` 名解決に使う。
- 位置引数 / `--commit` / `--base-branch` — JSONL 履歴レコードの review_mode を決めるレビュー対象。`select` と同じ判定（`_resolve_select_target` を再利用）。

### dispatch-plan の run_dir 永続化

設計書 §9「サブエージェントが JSON を書かなかった → `AgentError`」を満たすため、`aggregate` は「どのエージェントが起動されたか（期待集合）」を知る必要がある。そこで **`select` が `DispatchPlan` を `<run_dir>/dispatch-plan.json` にも書き出す**（Task 1）。`aggregate` はこれを読み、期待エージェントごとに findings ファイルの有無を検証する。

### findings の検証

各期待エージェント `<name>` について `<run_dir>/<name>.json` を読む:
- ファイルなし → `AgentError(name, "no output")`
- JSON 不正・スキーマ不適合 → `AgentError(name, 詳細)`
- 正常 → manifest の `output_schema` 名から `get_schema()` で型解決し検証 → `AgentSuccess(name, issues, overall_score)`（`elapsed_time=None`）

破損入力はフォールバックせず明示的に `AgentError` として可視化する（憲法・設計書 §9）。

### `ReviewSummary` の計算

- `total_issues` = 全 `AgentSuccess` の issues 件数合計
- `max_severity` = 全 issues の最大重大度（`SEVERITY_ORDER` で比較）。issues が0件なら `None`
- `total_elapsed_time` = `None`（薄い CLI から per-agent 実行時間を観測できない、SP1-2a）
- `overall_score` = `AgentSuccess` の `overall_score` の平均（成功エージェントが0なら `None`）

### 終了コード

`max_severity` に基づく: `Critical` → 1、`Important` → 2、`Suggestion`/`Nitpick`/`None` → 0。`aggregate` 自体の実行エラー（run_dir 不存在等）→ 3。

### `AggregatedReport` 系の削除（§10「SP1-3 で確定」）

旧 LLM アグリゲーターの構造化出力 `AggregatedReport` と、それ専用の `RecommendedAction` / `Priority` / `Contradiction` / `QualityFilteredIssue`、`ReviewReport.aggregated` / `ReviewReport.aggregation_error`、`_markdown_formatter.py` の `_format_aggregated` 系関数は、エンジン撤去後に生成元が存在しない。決定的 `aggregate` はこれらを生成しないため、デッドコードとして削除する（Task 3）。

### 重複排除（design §7 からの意図的な範囲外）

設計書 §7 は「重複排除」に言及するが、これは LLM アグリゲーターによる意味的重複排除を想定したもの。決定的 `aggregate` の v1 では cross-agent の重複排除は**行わない**（exact-dedup は価値が低く、エージェント別の問題帰属を保つ方が有用）。issues はエージェント別にそのまま集計する。将来の改善余地として記録する。

## File Structure

**新規作成:**
- `src/hachimoku/cli/_aggregate.py` — `aggregate` の中核（findings 読込・検証・`ReviewReport` 構築・終了コード）
- `tests/unit/cli/test_aggregate.py`

**変更:**
- `src/hachimoku/cli/_select.py` — `run_select` が `dispatch-plan.json` を run_dir に書き出す
- `src/hachimoku/cli/_app.py` — `aggregate` サブコマンドを登録
- `src/hachimoku/models/report.py` — `AggregatedReport`/`RecommendedAction`/`Priority`/`Contradiction`/`QualityFilteredIssue` と `ReviewReport.aggregated`/`aggregation_error` を削除
- `src/hachimoku/cli/_markdown_formatter.py` — `_format_aggregated` 系を削除
- `tests/unit/cli/test_select.py` — `dispatch-plan.json` 書き出しのテスト追加
- 上記モデル削除に伴い影響するテスト

---

## Task 1: select が dispatch-plan.json を run_dir に書き出す

**Files:**
- Modify: `src/hachimoku/cli/_select.py`
- Test: `tests/unit/cli/test_select.py`

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で `uv run` を用いて実行する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/cli/test_select.py` の `TestSelectCommand` クラスに以下を追加:

```python
    def test_writes_dispatch_plan_json_into_run_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "base.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "feature.py").write_text("y = 2\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], cwd=tmp_path, check=True, capture_output=True)
        manifest_path = _write_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(app, ["select", "--manifest", str(manifest_path)])

        assert result.exit_code == 0
        plan = json.loads(result.stdout)
        plan_file = Path(plan["run_dir"]) / "dispatch-plan.json"
        assert plan_file.is_file()
        assert json.loads(plan_file.read_text()) == plan
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/cli/test_select.py::TestSelectCommand::test_writes_dispatch_plan_json_into_run_dir -v`
Expected: FAIL（`dispatch-plan.json` が作成されない）

- [ ] **Step 3: `run_select` を変更する**

`src/hachimoku/cli/_select.py` の `run_select` を以下に変更する（run_dir 作成後に `dispatch-plan.json` を書き出す）:

```python
def run_select(target: ReviewTarget, manifest_path: Path) -> DispatchPlan:
    """select の中核処理。ChangeSet 計算 → applicability 評価 → run_dir 作成。

    DispatchPlan は戻り値であると同時に <run_dir>/dispatch-plan.json にも
    書き出す（aggregate が期待エージェント集合を知るために参照する）。

    Raises:
        SelectError: manifest 読み込み失敗時。
        ChangeSetError: 変更内容計算失敗時。
    """
    manifest = load_manifest(manifest_path)
    changeset = compute_changeset(target)
    phases = select_agent_names(
        manifest, changeset.changed_basenames, changeset.content
    )
    run_dir = tempfile.mkdtemp(prefix="hachimoku-run-")
    plan = DispatchPlan(run_dir=run_dir, phases=phases)
    (Path(run_dir) / "dispatch-plan.json").write_text(
        plan.model_dump_json(indent=2), encoding="utf-8"
    )
    return plan
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/cli/test_select.py -v`
Expected: PASS（既存4件 + 新規1件 = 5件）

- [ ] **Step 5: 静的検査とコミット**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy .`
Expected: エラーなし。その後:

```bash
git add src/hachimoku/cli/_select.py tests/unit/cli/test_select.py
git commit -m "feat: persist dispatch plan to run_dir"
```

---

## Task 2: aggregate コマンド

**Files:**
- Create: `src/hachimoku/cli/_aggregate.py`
- Modify: `src/hachimoku/cli/_app.py`
- Test: `tests/unit/cli/test_aggregate.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/cli/test_aggregate.py` を作成:

```python
"""aggregate コマンドのテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest, ManifestEntry
from hachimoku.agents.models import ApplicabilityRule, Phase
from hachimoku.cli._app import app


def _write_manifest(path: Path) -> Path:
    manifest = Manifest(
        version=MANIFEST_VERSION,
        entries=(
            ManifestEntry(
                name="code-reviewer",
                applicability=ApplicabilityRule(always=True),
                phase=Phase.MAIN,
                output_schema="scored_issues",
            ),
        ),
    )
    manifest_path = path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json())
    return manifest_path


def _write_dispatch_plan(run_dir: Path, agent_names: list[str]) -> None:
    plan = {
        "run_dir": str(run_dir),
        "phases": {"early": [], "main": agent_names, "final": []},
    }
    (run_dir / "dispatch-plan.json").write_text(json.dumps(plan))


def _findings(issues: list[dict[str, object]], score: float) -> str:
    return json.dumps({"issues": issues, "overall_score": score})


def _issue(severity: str) -> dict[str, object]:
    return {
        "agent_name": "code-reviewer",
        "severity": severity,
        "description": f"a {severity} issue",
        "location": None,
        "suggestion": None,
        "category": None,
    }


class TestAggregateCommand:
    def test_aggregates_findings_and_outputs_report(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        (run_dir / "code-reviewer.json").write_text(
            _findings([_issue("Important")], 7.0)
        )
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        # Important が最大重大度 → 終了コード 2
        assert result.exit_code == 2
        assert "Review Report" in result.stdout
        assert "code-reviewer" in result.stdout

    def test_missing_findings_file_becomes_agent_error(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        # dispatch-plan は code-reviewer を期待するが findings ファイルなし
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        # findings なし → AgentError、issue 0件 → 終了コード 0
        assert result.exit_code == 0
        assert "code-reviewer" in result.stdout

    def test_malformed_findings_becomes_agent_error(
        self, tmp_path: Path
    ) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        (run_dir / "code-reviewer.json").write_text("{not valid json")
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        assert result.exit_code == 0  # issue 0件
        assert "code-reviewer" in result.stdout

    def test_critical_issue_exits_1(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        (run_dir / "code-reviewer.json").write_text(
            _findings([_issue("Critical")], 2.0)
        )
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        assert result.exit_code == 1

    def test_missing_run_dir_exits_3(self, tmp_path: Path) -> None:
        manifest_path = _write_manifest(tmp_path)
        result = CliRunner().invoke(
            app,
            [
                "aggregate",
                "--run-dir",
                str(tmp_path / "nonexistent"),
                "--manifest",
                str(manifest_path),
            ],
        )
        assert result.exit_code == 3
```

> `_issue` の severity 文字列・`ReviewIssue` のフィールド構成（`agent_name`/`severity`/`description`/`location`/`suggestion`/`category`）は `src/hachimoku/models/review.py` の実定義に必ず合わせること。実装着手時に `review.py` を開き、フィールド名・必須/オプション・`severity` の許容値（"Critical"/"Important"/"Suggestion"/"Nitpick"）を確認し、テストデータをそれに整合させる。

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/cli/test_aggregate.py -v`
Expected: FAIL（`aggregate` サブコマンド未登録）

- [ ] **Step 3: `cli/_aggregate.py` を実装する**

`src/hachimoku/cli/_aggregate.py` を作成する。要件:

- `class AggregateError(Exception)` — run_dir / dispatch-plan 不在等。
- `load_dispatch_plan(run_dir: Path) -> DispatchPlan` — `<run_dir>/dispatch-plan.json` を読み `DispatchPlan`（`cli/_select.py`）に検証。ファイル不在・JSON 不正・スキーマ不適合は `AggregateError`。
- `_expected_agents(plan: DispatchPlan) -> list[str]` — `plan.phases` 全フェーズのエージェント名を集約。
- `_load_one(run_dir: Path, name: str, schema_name: str) -> AgentResult` — `<run_dir>/<name>.json` を読む。ファイル不在 → `AgentError(agent_name=name, error_message="no output")`。`json.JSONDecodeError` → `AgentError(... , error_message=...)`。`get_schema(schema_name)`（`hachimoku.models.schemas` の `get_schema`）で型解決し `model_validate` で検証、`ValidationError` → `AgentError`。成功 → `AgentSuccess(agent_name=name, issues=parsed.issues, overall_score=parsed.overall_score)`（`elapsed_time` は渡さない＝None）。
- `build_report(results: list[AgentResult]) -> ReviewReport`:
  - `total_issues` = 全 `AgentSuccess` の `len(issues)` 合計。
  - 全 `AgentSuccess` の全 issues から最大重大度を求める（`hachimoku.models.severity` の `Severity` と `SEVERITY_ORDER` を使用。`SEVERITY_ORDER` の値が大きいほど重大）。issues 0件なら `max_severity=None`。
  - `overall_score` = `AgentSuccess` の `overall_score` の平均（成功0件なら None）。
  - `total_elapsed_time=None`。
  - `ReviewReport(results=results, summary=ReviewSummary(...), load_errors=())` を返す。
- `exit_code_for(summary: ReviewSummary) -> ExitCode` — `max_severity` が `Severity.CRITICAL` → `ExitCode.CRITICAL`、`Severity.IMPORTANT` → `ExitCode.IMPORTANT`、それ以外（Suggestion/Nitpick/None）→ `ExitCode.SUCCESS`。
- `run_aggregate(run_dir: Path, manifest_path: Path) -> tuple[ReviewReport, list[str]]` — dispatch-plan 読込、manifest 読込（`load_manifest`、`cli/_select.py` から import）、manifest から `name -> output_schema` の対応を作り、期待エージェントごとに `_load_one`、`build_report`。manifest に無いエージェント名が dispatch-plan にあった場合は `AgentError(name, "agent not in manifest")`。戻り値はレポートと「期待エージェント名一覧」（呼び出し側の参考用、未使用なら戻り値から外してよい）。
- `aggregate_command(run_dir: Path, manifest_path: Path, target: ReviewTarget) -> None`:
  - `try: report = run_aggregate(...)` — `AggregateError` → `print(..., file=sys.stderr)` ＋ `raise typer.Exit(code=ExitCode.EXECUTION_ERROR)`。
  - JSONL 履歴追記: `find_project_root(Path.cwd())` で project root を求め、`<root>/.hachimoku/reviews/` に `save_review_history(reviews_dir, target, report)`（`cli/_history_writer.py`）。`HistoryWriteError`/`GitInfoError` は警告を stderr に出し継続（終了コードに影響させない。既存 `_history_writer` の例外型に従う）。project root が None の場合は履歴をスキップし stderr に警告。
  - `print(format_markdown(report))`（`cli/_markdown_formatter.py`、stdout）。
  - `raise typer.Exit(code=exit_code_for(report.summary))`。

import の方針: `DispatchPlan` / `SelectError` / `load_manifest` は `hachimoku.cli._select` から、`get_schema` は `hachimoku.models.schemas` から、`AgentError`/`AgentResult`/`AgentSuccess` は `hachimoku.models.agent_result` から、`ReviewReport`/`ReviewSummary` は `hachimoku.models.report` から、`Severity`/`SEVERITY_ORDER` は `hachimoku.models.severity` から、`format_markdown` は `hachimoku.cli._markdown_formatter` から、`save_review_history` 等は `hachimoku.cli._history_writer` から、`ExitCode` は `hachimoku.models.exit_code` から import する。各シンボルの正確な名前・シグネチャは実装着手時に該当ファイルを開いて確認すること（特に `get_schema` の戻り値、`save_review_history` の引数、`SEVERITY_ORDER` の構造）。

全関数に型注釈と Google-style docstring を付ける。`AgentError` 等への破損入力は握り潰さず `AgentError` として可視化する（フォールバック禁止）。

- [ ] **Step 4: `cli/_app.py` に `aggregate` サブコマンドを登録する**

`src/hachimoku/cli/_app.py` に以下を追加する（import は既存と重複しないこと）:

```python
from hachimoku.cli._aggregate import aggregate_command
```

`aggregate` コマンド関数を `select` の後に追加:

```python
@app.command()
def aggregate(
    run_dir: Annotated[
        Path, typer.Option("--run-dir", help="Run directory created by 'select'.")
    ],
    manifest: Annotated[
        Path, typer.Option("--manifest", help="Path to the manifest JSON file.")
    ],
    args: Annotated[
        list[str] | None,
        typer.Argument(help="PR number or file paths (omit for diff mode)."),
    ] = None,
    commit: Annotated[
        str | None,
        typer.Option("--commit", help="Commit ref or range (SHA or SHA1..SHA2)."),
    ] = None,
    base_branch: Annotated[
        str, typer.Option("--base-branch", help="Base branch for diff mode.")
    ] = "main",
) -> None:
    """Aggregate subagent findings into a review report."""
    target = _resolve_select_target(args, commit, base_branch)
    aggregate_command(run_dir, manifest, target)
```

> `run_dir` と `manifest` はデフォルト値なしの必須引数として先頭に置く（SP1-2b-2 の `select` で `= ...` が mypy 非互換だった教訓に従う）。`typer.Option` 注釈付きのためオプション扱いになる。`_resolve_select_target` は `_app.py` 内の既存ヘルパー。

- [ ] **Step 5: テストが通ることを確認する**

Run: `uv run pytest tests/unit/cli/test_aggregate.py -v`
Expected: PASS（5 件）。失敗する場合、`review.py` の `ReviewIssue` フィールド整合（Step 1 の注記）と各 import シンボル名を確認する。

- [ ] **Step 6: 静的検査と全テストを確認する**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全てエラーなし、全テスト PASS・収集エラー0。

- [ ] **Step 7: コミット**

```bash
git add src/hachimoku/cli/_aggregate.py src/hachimoku/cli/_app.py tests/unit/cli/test_aggregate.py
git commit -m "feat: add aggregate command for subagent findings"
```

---

## Task 3: AggregatedReport 系の削除

**Files:**
- Modify: `src/hachimoku/models/report.py`
- Modify: `src/hachimoku/cli/_markdown_formatter.py`
- Modify: 影響テスト

> 型削除が `report.py` → `_markdown_formatter.py` → テストに連鎖するため、変更を一括し単一コミットにする（SP1-2a と同じ理由）。

- [ ] **Step 1: 削除対象を確認する**

`report.py` から削除する: `Priority`、`RecommendedAction`、`Contradiction`、`QualityFilteredIssue`、`AggregatedReport` の各クラスと、`ReviewReport` の `aggregated` / `aggregation_error` フィールド。`report.py` の `ReviewSummary` / `ReviewReport`（`aggregated`/`aggregation_error` 以外）は維持する。

`_markdown_formatter.py` から削除する: `_format_aggregated`、`_format_contradictions`、`_format_quality_filtered`、`_format_aggregation_error` の各関数と、`format_markdown` 内の `report.aggregated` / `report.aggregation_error` を参照する分岐、関連 import（`AggregatedReport`/`Contradiction`/`QualityFilteredIssue`）。

事前確認: `grep -rn 'AggregatedReport\|RecommendedAction\|Priority\|Contradiction\|QualityFilteredIssue\|aggregation_error\|\.aggregated' src/ tests/` で全参照箇所を洗い出す。

- [ ] **Step 2: `report.py` を変更する**

`Priority`/`RecommendedAction`/`Contradiction`/`QualityFilteredIssue`/`AggregatedReport` クラス定義を削除する。`ReviewReport` を以下に変更（`aggregated`/`aggregation_error` 削除）:

```python
class ReviewReport(HachimokuBaseModel):
    """全エージェントの結果を集約したレビューレポート。

    results は空リストを許容する（全エージェント失敗時の部分レポート対応）。

    Attributes:
        results: エージェント結果のリスト。
        summary: レビュー結果の全体サマリー。
        load_errors: エージェント読み込みエラーのタプル。
    """

    results: list[AgentResult]
    summary: ReviewSummary
    load_errors: tuple[LoadError, ...] = ()
```

未使用になる import（`StrEnum`、`field_validator`、`normalize_enum_value` 等）があれば削除する。`ruff check` で検出される。

- [ ] **Step 3: `_markdown_formatter.py` を変更する**

`_format_aggregated`/`_format_contradictions`/`_format_quality_filtered`/`_format_aggregation_error` を削除。`format_markdown` から `if report.aggregated is not None:` ブロックと `if report.aggregation_error is not None:` ブロックを削除。`AggregatedReport`/`Contradiction`/`QualityFilteredIssue` の import を削除。

- [ ] **Step 4: 影響テストを整理する**

`uv run pytest 2>&1` を実行。削除した型・フィールドを参照するテストは収集エラー・失敗する。assert 対象が削除型・削除フィールド自体のテストは削除、それ以外でデータ構築に使っているだけのテストは新形状に書き換える（SP1-2a と同じ基準）。`grep` でヒットした全テストファイルが対象。

- [ ] **Step 5: 静的検査と全テストを確認する**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全てエラーなし、全テスト PASS。`grep -rn 'AggregatedReport\|RecommendedAction\|Contradiction\|QualityFilteredIssue\|aggregation_error' src/ tests/` がヒット0であることも確認。

- [ ] **Step 6: コミット**

```bash
git add -A
git commit -m "refactor: remove LLM-aggregator legacy (AggregatedReport et al.)"
```

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 の整備項目（既存計画と同方針） |
| `docs/ja`・`docs/en` | 否 | 利用者向けドキュメントは SP1 完了時に一括改訂 |
| `README.md` | 否 | 同上 |
| `CLAUDE.md` | 否 | 影響なし |

## 仕様トレーサビリティ

本計画は設計書 §7・§9・§10 を上位仕様とする。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する（既存計画と同方針）。

## 完了状態と後続計画

本計画の完了時点:
- `8moku select` が `dispatch-plan.json` を run_dir に書き出す。
- `8moku aggregate` が findings JSON を集約し、`ReviewReport` を Markdown 出力・JSONL 履歴追記・重要度に応じた終了コードを返す。
- `AggregatedReport` 系のデッドコードが削除される。
- これで SP1（薄い CLI 化）の決定的処理 — `select` / `aggregate` / `init` / モデル — が完成。

**後続計画:**
- SP2: `build`（TOML → サブエージェント `.md` + `manifest.json`）。`select`/`aggregate` が消費する manifest の生成側。
- SP3: Claude Code プラグイン（オーケストレーター skill が `select` → サブエージェント → `aggregate` を駆動）。
