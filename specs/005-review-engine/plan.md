# Implementation Plan: レビュー実行エンジン

**Branch**: `005-review-engine` | **Date**: 2026-02-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-review-engine/spec.md`

## Summary

pydantic-ai ベースのマルチエージェントレビュー実行エンジンを実装する。エンジンは設定解決 → エージェント読み込み → セレクターエージェントによる選択 → 実行コンテキスト構築 → 逐次/並列実行 → 結果集約のパイプラインで動作する。エージェントは `allowed_tools`（git_read, gh_read, file_read）を通じてレビュー対象を自律的に調査し、`output_type` による構造化出力で型安全な結果を返す。SIGINT/SIGTERM によるグレースフルシャットダウンと、個別エージェントの失敗許容（部分レポート生成）を備える。

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: pydantic-ai（エージェント実行基盤）, pydantic ≥2.12.5（バリデーション）, asyncio（並列実行・タイムアウト制御）
**Storage**: N/A（ファイルシステムは設定・エージェント定義の読み込みのみ、004/003 が担当済み）
**Testing**: pytest + pytest-asyncio（非同期テスト）
**Target Platform**: Linux / macOS CLI
**Project Type**: single
**Performance Goals**: 並列実行時の全体所要時間が最も遅いエージェント＋オーバーヘッド10%以内（SC-RE-003）
**Constraints**: SIGINT 受信後3秒以内に全プロセス終了（SC-RE-005）、タイムアウト＋10秒以内にプロセス終了（SC-RE-001）
**Scale/Scope**: 最大6ビルトインエージェント＋カスタムエージェント、3フェーズ（early/main/final）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Status | Notes |
|---------|--------|-------|
| Art.1 Test-First | PASS | TDD で実装。テスト → Red → Green → Refactor |
| Art.2 Documentation Integrity | PASS | 仕様書（spec.md）を基に実装。曖昧点は Clarifications で解決済み |
| Art.3 CLI Design | PASS | stdout=レビューレポート、stderr=進捗/ログ。終了コード 0/1/2/3/4 準拠 |
| Art.4 Simplicity | PASS | 既存の src/hachimoku/ 内に engine/ パッケージを追加。3プロジェクト以内。pydantic-ai を直接使用、不要なラッパーなし |
| Art.5 Code Quality | PASS | ruff + mypy 完全準拠 |
| Art.6 Data Accuracy | PASS | 設定値は HachimokuConfig から取得。デフォルト値は 004-configuration で定義済み。マジックナンバーなし |
| Art.7 DRY | PASS | 既存の models/agents/config パッケージを再利用。新規作成は engine 固有ロジックのみ |
| Art.8 Refactoring | PASS | 既存モデルへの変更（ReviewReport.load_errors フィールド追加等）は直接修正 |
| Art.9 Type Safety | PASS | 全関数に型注釈。Any 禁止。mypy strict |
| Art.10 Docstring | SHOULD | public モジュール・クラス・関数に Google-style docstring |
| Art.11 Naming | PASS | git-conventions.md 準拠 |

**GATE RESULT**: PASS（違反なし）

## Project Structure

### Documentation (this feature)

```text
specs/005-review-engine/
├── plan.md              # This file
├── research.md          # Phase 0: pydantic-ai API 調査・設計判断
├── data-model.md        # Phase 1: エンジン固有のデータモデル
├── quickstart.md        # Phase 1: 実装開始ガイド
├── contracts/           # Phase 1: モジュール間契約
│   ├── review_engine.py     # ReviewEngine 公開 API, EngineResult
│   ├── review_target.py     # ReviewTarget 判別共用体
│   ├── instruction_builder.py # ReviewInstructionBuilder 入出力仕様
│   ├── selector_agent.py    # SelectorAgent, SelectorOutput
│   ├── execution_context.py # AgentExecutionContext 構築ロジック
│   ├── agent_runner.py      # AgentRunner インターフェース
│   ├── tool_catalog.py      # ToolCatalog インターフェース
│   ├── executors.py         # SequentialExecutor / ParallelExecutor
│   ├── progress_reporter.py # stderr 進捗表示フォーマット
│   └── signal_handler.py   # SIGINT/SIGTERM ハンドリング
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/hachimoku/
├── models/                    # 既存（002/004 で実装済み）
│   ├── agent_result.py        # AgentResult 判別共用体（変更なし、AgentTruncated 追加済み）
│   ├── report.py              # ReviewReport（load_errors フィールド追加）
│   ├── config.py              # HachimokuConfig, SelectorConfig（変更なし）
│   ├── tool_category.py       # ToolCategory（変更なし）
│   └── schemas/               # 出力スキーマ（変更なし）
├── agents/                    # 既存（003 で実装済み）
│   ├── models.py              # AgentDefinition, LoadResult（変更なし）
│   └── loader.py              # load_agents()（変更なし）
├── config/                    # 既存（004 で実装済み）
│   └── _resolver.py           # resolve_config()（変更なし）
└── engine/                    # 新規（005 で実装）
    ├── __init__.py             # 公開 API: ReviewEngine, ReviewTarget
    ├── _target.py              # ReviewTarget, ReviewMode（入力モード）
    ├── _instruction.py         # ReviewInstructionBuilder（プロンプト構築）
    ├── _context.py             # AgentExecutionContext（実行コンテキスト構築）
    ├── _runner.py              # AgentRunner（単一エージェント実行）
    ├── _selector.py            # SelectorAgent（エージェント選択）
    ├── _executor.py            # SequentialExecutor, ParallelExecutor
    ├── _catalog.py             # ToolCatalog（カテゴリ→pydantic-aiツール解決）
    ├── _tools/                 # pydantic-ai ツール実装
    │   ├── __init__.py
    │   ├── _git.py             # git_read カテゴリのツール群
    │   ├── _gh.py              # gh_read カテゴリのツール群
    │   └── _file.py            # file_read カテゴリのツール群
    ├── _progress.py            # stderr 進捗表示
    ├── _signal.py              # SIGINT/SIGTERM ハンドリング
    └── _engine.py              # ReviewEngine（パイプライン統括）

tests/unit/
└── engine/                    # 新規（005 のテスト）
    ├── test_target.py          # ReviewTarget テスト
    ├── test_instruction.py     # ReviewInstructionBuilder テスト
    ├── test_context.py         # AgentExecutionContext テスト
    ├── test_runner.py          # AgentRunner テスト
    ├── test_selector.py        # SelectorAgent テスト
    ├── test_executor.py        # SequentialExecutor / ParallelExecutor テスト
    ├── test_catalog.py         # ToolCatalog テスト
    ├── test_tools.py           # 個別ツール関数テスト
    ├── test_progress.py        # 進捗表示テスト
    ├── test_signal.py          # シグナルハンドリングテスト
    └── test_engine.py          # ReviewEngine 統合テスト
```

**Structure Decision**: 既存の `src/hachimoku/` パッケージ内に `engine/` サブパッケージを追加する。既存の models/agents/config パッケージには最小限の変更（ReviewReport への load_errors フィールド追加）のみ行う。engine 内部のモジュールは `_` プレフィックスでプライベートとし、`__init__.py` で公開 API のみエクスポートする。

## Complexity Tracking

> 憲法違反なし。追記不要。
