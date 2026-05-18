# SP1-2a: モデル再形成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 撤去済みエンジン固有の結果モデル（`CostInfo` / `AgentTruncated` / `AgentTimeout`）を削除し、`AgentResult` を `AgentSuccess | AgentError` の2肢へ縮小、`elapsed_time` を optional 化する。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §10「スキーマ変更まとめ」の実装。型削除が `agent_result.py` → `report.py` / `models/__init__.py` / `_markdown_formatter.py` に連鎖するため、4ファイル + 関連テストを **1タスク・単一コミット**の atomic な変更として行う（途中状態はビルド不可になるため分割不可）。`Manifest` 契約定義と `select` 実装は後続計画 SP1-2b。

**Tech Stack:** Python 3.13+ / pydantic v2 / pytest / ruff / mypy / uv

**前提:** 本計画は SP1-1（ブランチ `worktree-sp1-engine-removal`、旧エンジン撤去済み）の上で実行する。

---

## 背景: なぜ単一コミットか

`AgentResult` 判別共用体は `AgentSuccess | AgentTruncated | AgentError | AgentTimeout` の4肢。`CostInfo` は `AgentSuccess.cost` と `ReviewSummary.total_cost` が参照。これらの型を `agent_result.py` から削除すると、同時に `report.py`・`models/__init__.py`・`cli/_markdown_formatter.py` の import が壊れる。型削除の連鎖を途中でコミットするとビルド不可状態が履歴に残るため、4ファイルの変更を1コミットにまとめる。

## §10 スキーマ変更（本計画が実装する内容）

| 変更 | 内容 |
|------|------|
| `CostInfo` クラス削除 | `agent_result.py` から全廃。金額/トークンは記録しない（設計 §2 非ゴール） |
| `AgentSuccess.cost` 削除 | フィールド削除 |
| `AgentResult` 判別共用体の縮小 | `AgentTruncated` / `AgentTimeout` を削除し `AgentSuccess \| AgentError` の2肢に |
| `elapsed_time` を optional 化 | `AgentSuccess.elapsed_time` を `float \| None`（既定 `None`）へ |
| `ReviewSummary` 調整 | `total_cost` フィールド削除、`total_elapsed_time` を `float \| None` 化 |

> `report.py` の `AggregatedReport` / `ReviewReport.aggregated` / `aggregation_error` は旧 LLM アグリゲーター由来だが、本計画の対象外（SP1-3 で扱う）。本計画では変更しない。

## File Structure

**変更（src）:**
- `src/hachimoku/models/agent_result.py` — `CostInfo`/`AgentTimeout`/`AgentTruncated` 削除、`AgentSuccess` 再形成、`AgentResult` 2肢化
- `src/hachimoku/models/report.py` — `ReviewSummary` から `total_cost` 削除、`total_elapsed_time` optional 化、`CostInfo` import 削除
- `src/hachimoku/models/__init__.py` — `CostInfo`/`AgentTimeout`/`AgentTruncated` の import・`__all__` エントリ削除
- `src/hachimoku/cli/_markdown_formatter.py` — 削除型の import 撤去、`_format_cost_row` 削除、optional 対応

**変更（tests）:**
- `tests/unit/models/test_agent_result.py`、`tests/unit/models/test_report.py`、`tests/unit/cli/test_markdown_formatter.py`、その他削除型を参照する全テスト

---

## Task 1: モデル再形成（4ファイル + テスト、単一コミット）

**Files:**
- Modify: `src/hachimoku/models/agent_result.py`
- Modify: `src/hachimoku/models/report.py`
- Modify: `src/hachimoku/models/__init__.py`
- Modify: `src/hachimoku/cli/_markdown_formatter.py`
- Test: `tests/unit/models/test_agent_result.py`、`tests/unit/models/test_report.py`、`tests/unit/cli/test_markdown_formatter.py` ほか

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で `uv run` を用いて実行する。

- [ ] **Step 1: 新しい `agent_result.py` 形状の失敗するテストを書く**

`tests/unit/models/test_agent_result.py` に以下のテストクラスを追加する（既存の `CostInfo`/`AgentTimeout`/`AgentTruncated` を扱うテストは Step 7 で整理する）:

```python
import pytest
from pydantic import ValidationError

from hachimoku.models.agent_result import AgentError, AgentResult, AgentSuccess


class TestReshapedAgentResult:
    def test_agent_success_without_cost_field(self) -> None:
        success = AgentSuccess(agent_name="code-reviewer", issues=[])
        assert success.status == "success"
        assert success.elapsed_time is None
        assert not hasattr(success, "cost")

    def test_agent_success_elapsed_time_optional(self) -> None:
        success = AgentSuccess(
            agent_name="code-reviewer", issues=[], elapsed_time=12.5
        )
        assert success.elapsed_time == 12.5

    def test_agent_success_elapsed_time_rejects_non_positive(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(agent_name="a", issues=[], elapsed_time=0.0)

    def test_cost_info_is_removed(self) -> None:
        import hachimoku.models.agent_result as mod

        assert not hasattr(mod, "CostInfo")
        assert not hasattr(mod, "AgentTruncated")
        assert not hasattr(mod, "AgentTimeout")

    def test_agent_result_union_has_two_variants(self) -> None:
        # status による判別: success → AgentSuccess, error → AgentError
        from pydantic import TypeAdapter

        adapter = TypeAdapter(AgentResult)
        ok = adapter.validate_python(
            {"status": "success", "agent_name": "a", "issues": []}
        )
        assert isinstance(ok, AgentSuccess)
        err = adapter.validate_python(
            {"status": "error", "agent_name": "a", "error_message": "boom"}
        )
        assert isinstance(err, AgentError)

    def test_agent_result_rejects_removed_status(self) -> None:
        from pydantic import TypeAdapter

        adapter = TypeAdapter(AgentResult)
        with pytest.raises(ValidationError):
            adapter.validate_python(
                {"status": "timeout", "agent_name": "a", "timeout_seconds": 1.0}
            )
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/models/test_agent_result.py::TestReshapedAgentResult -v`
Expected: FAIL（現行 `AgentSuccess` は `cost` を持ち `elapsed_time` 必須、`CostInfo` 等が存在する）。

- [ ] **Step 3: `agent_result.py` を再形成する**

`src/hachimoku/models/agent_result.py` を以下の内容で全面置換する:

```python
"""エージェント実行結果の定義。

FR-DM-003: AgentResult 判別共用体。
status フィールドの固定値で型を一意に特定する。
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import ReviewIssue


class AgentSuccess(HachimokuBaseModel):
    """エージェント実行の成功結果。判別キー: status="success"。

    Attributes:
        status: 判別キー。固定値 "success"。
        agent_name: エージェント名。
        issues: 検出されたレビュー問題のリスト。
        overall_score: 品質スコア（0.0-10.0、オプション）。
        elapsed_time: 実行所要時間（秒、正の値）。観測できない場合は None。
    """

    status: Literal["success"] = "success"
    agent_name: str = Field(min_length=1)
    issues: list[ReviewIssue]
    overall_score: float | None = Field(default=None, ge=0.0, le=10.0)
    elapsed_time: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class AgentError(HachimokuBaseModel):
    """エージェント実行のエラー結果。判別キー: status="error"。

    Attributes:
        status: 判別キー。固定値 "error"。
        agent_name: エージェント名。
        error_message: エラーメッセージ。
        exit_code: CLI プロセス終了コード（オプション）。
        error_type: 構造化エラー種別（オプション）。
        stderr: 標準エラー出力（オプション）。
    """

    status: Literal["error"] = "error"
    agent_name: str = Field(min_length=1)
    error_message: str = Field(min_length=1)
    exit_code: int | None = None
    error_type: str | None = Field(default=None, min_length=1)
    stderr: str | None = None


AgentResult = Annotated[
    Union[AgentSuccess, AgentError],
    Field(discriminator="status"),
]
"""エージェント結果の判別共用体。status フィールドの値で型を自動選択する。"""
```

- [ ] **Step 4: `report.py` の `ReviewSummary` を再形成する**

`src/hachimoku/models/report.py` を次のとおり変更する。

(a) import 行（16行目付近）— `CostInfo` を除去:
```python
from hachimoku.models.agent_result import AgentResult
```

(b) `ReviewSummary` クラス — `total_cost` フィールドを削除し、`total_elapsed_time` を optional 化する。docstring も合わせて更新。クラス本体を以下に置換:
```python
class ReviewSummary(HachimokuBaseModel):
    """レビュー結果の全体サマリー。

    ReviewReport で使用される。

    Attributes:
        total_issues: 検出された問題の総数（非負）。
        max_severity: 検出された問題の最大重大度。問題なしの場合は None。
        total_elapsed_time: 全エージェントの合計実行時間（秒）。観測できない場合は None。
        overall_score: 総合品質スコア（0.0-10.0、オプション）。
    """

    total_issues: int = Field(ge=0)
    max_severity: Severity | None
    total_elapsed_time: float | None = Field(
        default=None, ge=0.0, allow_inf_nan=False
    )
    overall_score: float | None = Field(default=None, ge=0.0, le=10.0)

    @model_validator(mode="after")
    def check_severity_consistency(self) -> ReviewSummary:
        """total_issues と max_severity の整合性を検証する。

        - total_issues=0 なら max_severity は None でなければならない。
        - total_issues>0 なら max_severity は None であってはならない。
        """
        if self.total_issues == 0 and self.max_severity is not None:
            raise ValueError("max_severity must be None when total_issues is 0")
        if self.total_issues > 0 and self.max_severity is None:
            raise ValueError("max_severity must not be None when total_issues > 0")
        return self
```
`report.py` のそれ以外（`Priority`/`RecommendedAction`/`Contradiction`/`QualityFilteredIssue`/`AggregatedReport`/`ReviewReport`）は変更しない。

- [ ] **Step 5: `models/__init__.py` のエクスポートを整理する**

`src/hachimoku/models/__init__.py` から、`hachimoku.models.agent_result` の import 文中の `AgentTimeout` / `AgentTruncated` / `CostInfo` を削除し、`__all__` からも同3エントリを削除する。`AgentError` / `AgentResult` / `AgentSuccess` は残す。

- [ ] **Step 6: `_markdown_formatter.py` を再形成する**

`src/hachimoku/cli/_markdown_formatter.py` を次のとおり変更する。

(a) import（13-19行目）— 削除型を除去:
```python
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
)
```

(b) `_format_summary`（68行目〜）— `elapsed_display` を optional 対応にし、`total_cost` 行を削除:
```python
def _format_summary(summary: ReviewSummary) -> str:
    severity_display = summary.max_severity.value if summary.max_severity else "-"
    elapsed_display = (
        f"{summary.total_elapsed_time:.1f}s"
        if summary.total_elapsed_time is not None
        else "-"
    )

    rows = [
        f"| Total Issues | {summary.total_issues} |",
        f"| Max Severity | {severity_display} |",
        f"| Elapsed Time | {elapsed_display} |",
    ]

    if summary.overall_score is not None:
        rows.append(f"| Overall Score | {summary.overall_score} / 10.0 |")

    table = "\n".join(rows)
    return f"## Summary\n\n| Metric | Value |\n|--------|-------|\n{table}"
```

(c) `_format_cost_row` 関数（88-93行目）を**丸ごと削除**する。

(d) `_collect_issues`（99行目〜）— `AgentTruncated` を除去:
```python
def _collect_issues(report: ReviewReport) -> list[ReviewIssue]:
    """AgentSuccess から issues を収集する。"""
    issues: list[ReviewIssue] = []
    for agent_result in report.results:
        if isinstance(agent_result, AgentSuccess):
            issues.extend(agent_result.issues)
    return issues
```

(e) `_format_agent_result_row`（167行目〜）— シグネチャを2肢に、`match` から `AgentTruncated`/`AgentTimeout` を除去し、`elapsed_time` の optional 対応:
```python
def _format_agent_result_row(
    agent_result: AgentSuccess | AgentError,
) -> str:
    match agent_result:
        case AgentSuccess():
            issue_count = str(len(agent_result.issues))
            score_display = (
                str(agent_result.overall_score)
                if agent_result.overall_score is not None
                else "-"
            )
            time_display = (
                f"{agent_result.elapsed_time:.1f}s"
                if agent_result.elapsed_time is not None
                else "-"
            )
            return (
                f"| {agent_result.agent_name} | {agent_result.status} "
                f"| {issue_count} | {score_display} | {time_display} |"
            )
        case AgentError():
            return f"| {agent_result.agent_name} | error | - | - | - |"
        case _ as unreachable:
            assert_never(unreachable)
```
`_format_aggregated` 以降（`AggregatedReport` 関連）は変更しない。

- [ ] **Step 7: 削除型を参照する既存テストを整理する**

Run: `uv run pytest 2>&1` を実行する。`CostInfo` / `AgentTruncated` / `AgentTimeout` / `AgentSuccess(cost=...)` / `ReviewSummary(total_cost=...)` を参照する既存テストは収集エラーまたは失敗する。各該当テストについて:
- 削除された型・フィールドそのものを検証するテスト（例: `CostInfo` のバリデーションテスト、`AgentTruncated` の判別テスト、`total_cost` の集計テスト）→ **テスト関数／クラスを削除**する。
- 削除型を「テストデータの構築に使っているだけ」のテスト（例: `AgentSuccess(..., cost=CostInfo(...))` で結果を組み立てて別の振る舞いを検証）→ 構築部分を新形状（`cost` を渡さない、`AgentTruncated`→`AgentSuccess`、`AgentTimeout`→`AgentError` 等）に**書き換えて存続**させる。
判断基準: そのテストの assert 対象が「削除された型/フィールド自体」なら削除、「それ以外の振る舞い」なら新形状へ書き換え。対象は `tests/unit/models/test_agent_result.py`・`test_report.py`・`tests/unit/cli/test_markdown_formatter.py`・`tests/unit/cli/test_history_writer.py` を中心に、`grep -rln 'CostInfo\|AgentTruncated\|AgentTimeout' tests/` でヒットする全ファイル。

- [ ] **Step 8: 静的検査と全テストを確認する**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: ruff / mypy エラーなし、全テスト PASS・収集エラー0。`grep -rn 'CostInfo\|AgentTruncated\|AgentTimeout' src/ tests/` がヒット0であることも確認する。

- [ ] **Step 9: コミット**

```bash
git add -A
git commit -m "refactor: reshape AgentResult — drop CostInfo and truncated/timeout variants"
```

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 のドキュメント整備項目（SP1-1 計画と同方針） |
| `docs/ja`・`docs/en` | 否 | `models.md` は利用者向け CLI の最終形確定後（SP1 完了時）に一括改訂。本計画単独では更新しない |
| `README.md` | 否 | 影響なし |
| `CLAUDE.md` | 否 | 影響なし（pydantic-ai 記述は SP1-1 で除去済み） |

## 仕様トレーサビリティ

本計画は設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §10 を上位仕様とする。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する（SP1-1 計画と同方針）。

## 完了状態と後続計画

本計画の完了時点:
- `AgentResult` は `AgentSuccess | AgentError` の2肢。`CostInfo` / `AgentTruncated` / `AgentTimeout` は存在しない。
- `AgentSuccess.elapsed_time` は `float | None`、`cost` フィールドなし。
- `ReviewSummary` は `total_cost` を持たず、`total_elapsed_time` は `float | None`。
- `ReviewHistoryRecord`（`history.py`）の discriminator は不変。`results` 配下の `AgentResult` のみ上記のとおり変化。

**後続計画:**
- SP1-2b: `Manifest` 契約定義 ＋ `select` 実装。
- SP1-3: `aggregate` 実装 ＋ JSONL 履歴連携（`AggregatedReport` の扱いもここで確定）。
