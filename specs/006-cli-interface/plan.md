# Implementation Plan: CLI インターフェース・初期化

**Branch**: `006-cli-interface` | **Date**: 2026-02-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-cli-interface/spec.md`

## Summary

Typer ベースの CLI エントリポイントを構築し、`8moku` / `hachimoku` のデュアルコマンド名でレビュー実行・init・agents サブコマンドを提供する。位置引数から diff/PR/file モードを自動判定し、005-review-engine の `run_review()` に委譲する。終了コード 0-4 によるプロセス制御、stdout/stderr のストリーム分離、file モードのファイル解決・確認プロンプトを実装する。

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Typer ≥0.21.1（CLI フレームワーク）, pydantic ≥2.12.5（バリデーション）, pydantic-ai ≥1.56.0（エンジン経由）
**Storage**: ファイルシステム（`.hachimoku/` ディレクトリ構造の初期化）
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux / macOS / Windows（CLI ツール）
**Project Type**: Single project
**Performance Goals**: CLI 起動 < 500ms（レビュー実行時間は 005-review-engine 依存）
**Constraints**: stdin/stdout/stderr の適切な分離（パイプ・リダイレクト対応）
**Scale/Scope**: 5 サブモジュール（app, input_resolver, file_resolver, init_handler, exit_code）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Gate | Status |
|---------|------|--------|
| Art.1 TDD | テスト先行で全機能を実装する | PASS |
| Art.2 Doc Integrity | 仕様書 006-cli-interface/spec.md を基に実装する | PASS |
| Art.3 CLI Design | --help 全対応、エラーメッセージに解決方法、stdout/stderr 分離、終了コード準拠 | PASS — 本機能の中核 |
| Art.4 Simplicity | 最大3プロジェクト構造。Typer を直接使用しラッパーを作らない | PASS |
| Art.5 Code Quality | ruff + mypy 全エラー解消 | PASS |
| Art.6 Data Accuracy | マジックナンバー禁止。終了コードは IntEnum で定数化 | PASS |
| Art.7 DRY | 既存の ConfigResolver / AgentLoader / ReviewEngine を再利用 | PASS |
| Art.8 Refactoring | 既存コードの直接修正優先 | PASS |
| Art.9 Type Safety | 全関数に型注釈。Any 禁止 | PASS |
| Art.10 Docstring | public モジュール・クラス・関数に Google-style docstring | PASS (SHOULD) |
| Art.11 Naming | git-conventions.md 準拠 | PASS |

**Pre-Phase 0 Gate**: PASS（違反なし）

## Project Structure

### Documentation (this feature)

```text
specs/006-cli-interface/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli_app.py
│   ├── input_resolver.py
│   ├── file_resolver.py
│   ├── init_handler.py
│   └── exit_code.py
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/hachimoku/
├── cli/                         # 新規: CLI パッケージ
│   ├── __init__.py              # 公開 API: app, main
│   ├── _app.py                  # Typer app 定義・コールバック・サブコマンド
│   ├── _input_resolver.py       # 位置引数 → ReviewTarget 判定
│   ├── _file_resolver.py        # file モード: glob/ディレクトリ展開・確認
│   ├── _init_handler.py         # init サブコマンド: .hachimoku/ 初期化
│   └── _exit_code.py            # ExitCode IntEnum
├── agents/                      # 既存: load_agents, load_builtin_agents
├── config/                      # 既存: resolve_config
├── engine/                      # 既存: run_review, EngineResult
├── models/                      # 既存: HachimokuConfig, ReviewReport 等
└── __init__.py                  # 変更: main() → cli.main() への委譲

tests/
└── unit/
    └── cli/                     # 新規: CLI テストパッケージ
        ├── test_app.py          # Typer app テスト（typer.testing.CliRunner）
        ├── test_input_resolver.py  # 入力モード判定テスト
        ├── test_file_resolver.py   # ファイル解決テスト
        ├── test_init_handler.py    # init ハンドラーテスト
        └── test_exit_code.py       # 終了コードテスト
```

**Structure Decision**: 既存の `src/hachimoku/` 内に `cli/` パッケージを追加する単一プロジェクト構造。既存の agents/config/engine/models パッケージはそのまま利用し、CLI 層は engine の `run_review()` を呼び出す薄いレイヤーとして機能する。

## Complexity Tracking

> 憲法違反なし。追加の正当化不要。
