# Implementation Plan: エージェント定義・ローダー

**Branch**: `003-agent-definition` | **Date**: 2026-02-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-agent-definition/spec.md`

## Summary

TOML 形式のエージェント定義ファイルを読み込み、AgentDefinition モデルとして構築するローダーを実装する。6つのビルトインエージェント定義を Python パッケージ内にバンドルし、カスタムエージェント定義との統合読み込みをサポートする。ApplicabilityRule は 005-review-engine の SelectorAgent が参照する判断ガイダンスとして機能する。

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: pydantic ≥2.12.5（バリデーション）, tomllib（Python 標準ライブラリ、TOML パース）, importlib.resources（ビルトイン定義のパッケージ内配置）, re（正規表現バリデーション）
**Storage**: ファイルシステム（TOML 定義ファイル）
**Testing**: pytest
**Target Platform**: Python CLI（Linux/macOS/Windows）
**Project Type**: single（既存の `src/hachimoku/` パッケージに追加）
**Performance Goals**: N/A（定義読み込み・選択は軽量な処理）
**Constraints**: 既存の 002-domain-models（HachimokuBaseModel, SCHEMA_REGISTRY, BaseAgentOutput）との整合性を保つ
**Scale/Scope**: ビルトイン6エージェント + カスタムエージェント（数十程度を想定）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Gate | Status | Notes |
|---------|------|--------|-------|
| Art.1 TDD | テストファースト | PASS | 各モジュール（モデル・ローダー）に対し Red→Green→Refactor を実施 |
| Art.2 Documentation | 仕様整合 | PASS | spec.md の全 FR/SC を plan.md で対応付け済み |
| Art.3 CLI Design | データ駆動型 | PASS | エージェント定義は TOML で外部化、コード変更なしで拡張可能 |
| Art.4 Simplicity | 最大3プロジェクト構造 | PASS | 既存の `src/hachimoku/` に追加、新規プロジェクト不要 |
| Art.5 Code Quality | ruff + mypy | PASS | コミット前に `ruff check --fix . && ruff format . && mypy .` 実行 |
| Art.6 Data Accuracy | ハードコード禁止 | PASS | 定数は名前付き定数として定義、エージェント設定は TOML ファイルから取得 |
| Art.7 DRY | 重複防止 | PASS | 既存の HachimokuBaseModel, SCHEMA_REGISTRY を再利用 |
| Art.8 Refactoring | 既存コード直接修正 | PASS | V2 クラス作成なし。既存パッケージにモジュール追加 |
| Art.9 Type Safety | 全関数型注釈 | PASS | pydantic モデル + 全関数に型注釈必須 |
| Art.10 Docstring | Google-style | SHOULD | public モジュール・クラス・関数に記述 |
| Art.11 Naming | 命名規則準拠 | PASS | ブランチ名 `003-agent-definition`、モジュール名は snake_case |

**Violations**: なし

## Project Structure

### Documentation (this feature)

```text
specs/003-agent-definition/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── agent.py         # AgentDefinition, AgentLoader 契約
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/hachimoku/
├── models/              # 既存: 002-domain-models
│   ├── _base.py         # HachimokuBaseModel（再利用）
│   ├── schemas/         # SCHEMA_REGISTRY, 6種スキーマ（再利用）
│   └── ...
├── agents/              # 新規: 003-agent-definition
│   ├── __init__.py      # 公開 API エクスポート
│   ├── models.py        # AgentDefinition, ApplicabilityRule, Phase モデル
│   ├── loader.py        # AgentLoader（TOML 読み込み・バリデーション）
│   └── _builtin/        # ビルトイン定義ファイル（パッケージリソース）
│       ├── __init__.py   # パッケージマーカー（importlib.resources 用）
│       ├── code-reviewer.toml
│       ├── silent-failure-hunter.toml
│       ├── pr-test-analyzer.toml
│       ├── type-design-analyzer.toml
│       ├── comment-analyzer.toml
│       └── code-simplifier.toml
└── __init__.py

tests/
├── unit/
│   ├── models/          # 既存: 002-domain-models テスト
│   └── agents/          # 新規: 003-agent-definition テスト
│       ├── __init__.py
│       ├── test_models.py      # AgentDefinition, ApplicabilityRule, Phase テスト
│       └── test_loader.py      # AgentLoader テスト
```

**Structure Decision**: 既存の `src/hachimoku/` パッケージ内に `agents/` サブパッケージを新設。002-domain-models の `models/` パッケージと並列配置し、モジュール間の依存方向は `agents → models` の一方向とする。ビルトイン TOML 定義ファイルは `agents/_builtin/` に配置し `importlib.resources` でアクセスする。

## Constitution Check (Post-Design Re-evaluation)

*Phase 1 設計完了後の再評価。*

| Article | Gate | Status | Notes |
|---------|------|--------|-------|
| Art.1 TDD | テストファースト | PASS | quickstart.md にテスト構成を明記（test_models/test_loader） |
| Art.2 Documentation | 仕様整合 | PASS | data-model.md が spec.md の全エンティティ・バリデーション規則を網羅 |
| Art.3 CLI Design | データ駆動型 | PASS | 6ビルトイン TOML + カスタム TOML による拡張。contracts/agent.py で API 定義済み |
| Art.4 Simplicity | 最大3プロジェクト構造 | PASS | `agents/` は既存 `src/hachimoku/` 内のサブパッケージ。ローダーはクラスではなく関数 |
| Art.5 Code Quality | ruff + mypy | PASS | 全関数に型注釈、pydantic モデルで宣言的バリデーション |
| Art.6 Data Accuracy | ハードコード禁止 | PASS | AGENT_NAME_PATTERN, PHASE_ORDER は名前付き定数。ビルトイン定義は TOML ファイル |
| Art.7 DRY | 重複防止 | PASS | HachimokuBaseModel 再利用、SCHEMA_REGISTRY の get_schema() を model_validator で呼び出し |
| Art.8 Refactoring | 既存コード直接修正 | PASS | 既存コードへの変更なし。新規モジュール追加のみ |
| Art.9 Type Safety | 全関数型注釈 | PASS | contracts/agent.py で全シグネチャを型付きで定義済み |
| Art.10 Docstring | Google-style | SHOULD | contracts/agent.py に docstring テンプレート記述済み |
| Art.11 Naming | 命名規則準拠 | PASS | モジュール名 snake_case、エージェント名 kebab-case |

**Violations**: なし。設計は全 Article に準拠。

## Complexity Tracking

> 違反なし。追記不要。
