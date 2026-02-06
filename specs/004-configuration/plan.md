# Implementation Plan: 設定管理

**Branch**: `004-configuration` | **Date**: 2026-02-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-configuration/spec.md`

## Summary

設定管理機能は、5層の設定ソース（CLI > `.hachimoku/config.toml` > `pyproject.toml [tool.hachimoku]` > `~/.config/hachimoku/config.toml` > デフォルト値）を階層的に解決し、不変の `HachimokuConfig` モデルを構築する。既存の `HachimokuBaseModel`（`extra="forbid"`, `frozen=True`）を継承し、`tomllib`（標準ライブラリ）で TOML パースを行う。ディレクトリ探索は `pathlib.Path` で実装し、設定の項目単位マージは辞書操作で実現する。

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: pydantic ≥2.12.5（バリデーション）, tomllib（Python 標準ライブラリ、TOML パース）, pathlib（ファイルシステム操作）
**Storage**: ファイルシステム（TOML 設定ファイル）
**Testing**: pytest（`uv --directory $PROJECT_ROOT run pytest`）
**Target Platform**: Linux / macOS（CLI ツール）
**Project Type**: single
**Performance Goals**: 設定解決は100ms以内（ファイルI/O含む）
**Constraints**: 外部ライブラリ追加なし（tomllib は標準ライブラリ）。HachimokuBaseModel 継承必須
**Scale/Scope**: 設定項目10個 + エージェント個別設定（動的）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Article | Requirement | Status | Notes |
|---------|------------|--------|-------|
| Art.1 Test-First | TDD 厳守 | ✅ PASS | テスト → Red → 実装（Green）→ リファクタリング |
| Art.2 Doc Integrity | 仕様確認必須 | ✅ PASS | spec.md の全 FR/SC を確認済み |
| Art.3 CLI Design | データ駆動型 | ✅ PASS | 設定は `.hachimoku/config.toml` で一元管理 |
| Art.4 Simplicity | 最大3プロジェクト | ✅ PASS | 既存構造（src/, tests/, specs/）のみ使用 |
| Art.5 Code Quality | ruff + mypy | ✅ PASS | コミット前に品質チェック実行 |
| Art.6 Data Accuracy | ハードコード禁止 | ✅ PASS | デフォルト値は名前付き定数で定義 |
| Art.7 DRY | 重複禁止 | ✅ PASS | 既存の TOML ロードパターン（agents/loader.py）を参考に統一的な設計 |
| Art.8 Refactoring | 既存修正優先 | ✅ PASS | 新規モジュール追加（設定は新機能のため） |
| Art.9 Type Safety | 全関数型注釈 | ✅ PASS | mypy strict 準拠 |
| Art.10 Docstring | Google-style | ✅ PASS (SHOULD) | public API に docstring 付与 |
| Art.11 Naming | 命名規則準拠 | ✅ PASS | git-conventions.md 準拠 |

### Post-Design Check

| Article | Requirement | Status | Notes |
|---------|------------|--------|-------|
| Art.3 CLI Design | 設定一元管理 | ✅ PASS | ConfigResolver が全ソースを統合 |
| Art.4 Simplicity | 不要ラッパー禁止 | ✅ PASS | Pydantic バリデーション直接使用。不要な抽象化なし |
| Art.6 Data Accuracy | 名前付き定数 | ✅ PASS | デフォルト値はモデルフィールドのデフォルト引数として定義 |
| Art.7 DRY | TOML ロードパターン | ✅ PASS | agents/loader.py と同じ `tomllib.load` パターンを使用 |

## Project Structure

### Documentation (this feature)

```text
specs/004-configuration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    ├── config_models.py     # HachimokuConfig, AgentConfig, OutputFormat
    ├── project_locator.py   # find_project_root()
    └── config_resolver.py   # resolve_config()
```

### Source Code (repository root)

```text
src/hachimoku/
├── models/
│   ├── _base.py                # 既存: HachimokuBaseModel
│   └── config.py               # NEW: HachimokuConfig, AgentConfig, OutputFormat
├── config/
│   ├── __init__.py             # Public API: resolve_config, find_project_root
│   ├── _locator.py             # ProjectLocator: .hachimoku/ ディレクトリ探索
│   ├── _loader.py              # TOML ファイル読み込み（config.toml, pyproject.toml）
│   └── _resolver.py            # ConfigResolver: 5層マージロジック
└── ...

tests/unit/
├── models/
│   └── test_config.py          # NEW: HachimokuConfig, AgentConfig, OutputFormat のテスト
└── config/
    ├── test_locator.py         # NEW: .hachimoku/ 探索テスト
    ├── test_loader.py          # NEW: TOML 読み込みテスト
    └── test_resolver.py        # NEW: 5層マージテスト
```

**Structure Decision**: 既存の `src/hachimoku/` 構造を維持。設定モデルは `models/config.py` に配置（他のモデルと同じパターン）。設定解決ロジックは `config/` パッケージとして新設（agents/ と同レベル）。

## Complexity Tracking

> 該当なし。全 Constitution Article に準拠しており、違反の正当化は不要。
