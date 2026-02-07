# Quickstart: レビュー実行エンジン

**Feature**: 005-review-engine | **Date**: 2026-02-07

## 前提条件

- specs 002-domain-models, 003-agent-definition, 004-configuration が実装済み
- pydantic-ai がインストール済み（`uv add pydantic-ai`）
- pytest-asyncio がインストール済み（`uv add --dev pytest-asyncio`）

## 実装順序

### Step 1: ReviewTarget モデル（P1, US5）

**ファイル**: `src/hachimoku/engine/_target.py`, `tests/unit/engine/test_target.py`

最も依存が少なく、他の全コンポーネントの基盤となる。DiffTarget / PRTarget / FileTarget の判別共用体を実装する。

```python
# テストから始める（TDD）
def test_diff_target_creation() -> None:
    target = DiffTarget(base_branch="main")
    assert target.mode == "diff"
    assert target.base_branch == "main"
```

### Step 2: ReviewInstructionBuilder（P1, US5/US6）

**ファイル**: `src/hachimoku/engine/_instruction.py`, `tests/unit/engine/test_instruction.py`

ReviewTarget からエージェント向けのプロンプトコンテキスト（ユーザーメッセージ文字列）を構築する。純粋な文字列生成ロジックで、外部依存なし。

### Step 3: ToolCatalog（P1, FR-RE-016）

**ファイル**: `src/hachimoku/engine/_catalog.py`, `src/hachimoku/engine/_tools/`, `tests/unit/engine/test_catalog.py`

カテゴリ名（git_read, gh_read, file_read）から pydantic-ai ツールへのマッピング。ツール関数の実装（subprocess でコマンド実行）。バリデーション（不正カテゴリ検出）。

### Step 4: AgentExecutionContext 構築（P1, US6）

**ファイル**: `src/hachimoku/engine/_context.py`, `tests/unit/engine/test_context.py`

AgentDefinition + HachimokuConfig + ReviewTarget → AgentExecutionContext への変換ロジック。モデル名・タイムアウト・ターン数の優先順解決を含む。

### Step 5: ReviewReport.load_errors 追加（P1, FR-RE-014）

**ファイル**: `src/hachimoku/models/report.py`, `tests/unit/models/test_report.py`

既存の ReviewReport モデルに `load_errors: tuple[LoadError, ...] = ()` フィールドを追加。Step 11（統合）で ReviewReport を構築する際に必要となるため、統合より先に実施する。

### Step 6: AgentRunner（P1, US1/US2）

**ファイル**: `src/hachimoku/engine/_runner.py`, `tests/unit/engine/test_runner.py`

単一エージェントの実行。pydantic-ai Agent の構築と実行。タイムアウト（asyncio.timeout）とターン数制御（UsageLimits）。結果の AgentResult への変換。

**注意**: R-003（AgentTruncated の部分結果取得）は実装時に pydantic-ai の実際の動作を検証して確定する（research.md R-003 参照）。

### Step 7: SelectorAgent（P1, US5）

**ファイル**: `src/hachimoku/engine/_selector.py`, `tests/unit/engine/test_selector.py`

セレクターエージェントの構築と実行。SelectorOutput（selected_agents, reasoning）の取得。

### Step 8: Executors（P1/P2, US1/US3）

**ファイル**: `src/hachimoku/engine/_executor.py`, `tests/unit/engine/test_executor.py`

SequentialExecutor（P1）と ParallelExecutor（P2）。フェーズ順序制御。

### Step 9: Progress Reporter（P1, FR-RE-015）

**ファイル**: `src/hachimoku/engine/_progress.py`, `tests/unit/engine/test_progress.py`

stderr への進捗表示。エージェント開始/完了/サマリーのフォーマット。

### Step 10: Signal Handler（P2, US4）

**ファイル**: `src/hachimoku/engine/_signal.py`, `tests/unit/engine/test_signal.py`

SIGINT/SIGTERM のハンドリング。asyncio.Event ベースのシャットダウン制御。

### Step 11: ReviewEngine 統合（P1）

**ファイル**: `src/hachimoku/engine/_engine.py`, `tests/unit/engine/test_engine.py`

パイプライン全体の統合。EngineResult（ReviewReport + exit_code）の生成。

## テスト戦略

### モック戦略

pydantic-ai のエージェント実行はテスト時にモックする:

```python
# pydantic-ai 提供の TestModel を使用
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

agent = Agent(TestModel(), output_type=ScoredIssues)
```

### テストレベル

1. **ユニットテスト**: 各モジュールの純粋ロジック（ReviewTarget, InstructionBuilder, ToolCatalog, Context 構築等）
2. **統合テスト**: パイプライン全体（TestModel でのエンドツーエンド実行）

## 依存関係

```
pydantic-ai       ← 新規依存（エージェント実行基盤）
pytest-asyncio    ← 新規 dev 依存（非同期テスト）
```

## 品質チェック

各 Step 完了後に必ず実行:

```bash
uv --directory $PROJECT_ROOT run ruff check --fix .
uv --directory $PROJECT_ROOT run ruff format .
uv --directory $PROJECT_ROOT run mypy .
uv --directory $PROJECT_ROOT run pytest
```
