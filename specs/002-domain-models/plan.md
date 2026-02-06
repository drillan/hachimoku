# Implementation Plan: ドメインモデル・出力スキーマ定義

**Branch**: `002-domain-models` | **Date**: 2026-02-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-domain-models/spec.md`

## Summary

全レイヤーの基盤となる共通ドメインモデルと出力スキーマを Pydantic v2 モデルとして定義する。Severity 列挙型、ReviewIssue、AgentResult 判別共用体（AgentSuccess/AgentError/AgentTimeout）、ReviewReport、6種の出力スキーマ（BaseAgentOutput 継承）、SCHEMA_REGISTRY、ReviewHistoryRecord 判別共用体（DiffReviewRecord/PRReviewRecord/FileReviewRecord）を実装する。pydantic-ai の `result_type` 制約により全モデルは Pydantic モデルとして実装される。

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: pydantic v2（pydantic-ai 経由で導入済み）
**Storage**: N/A（モデル定義のみ。JSONL 蓄積は 007-output-format が担当）
**Testing**: pytest + uv run
**Target Platform**: Linux / macOS CLI ツール
**Project Type**: single（`src/hachimoku/` パッケージ）
**Performance Goals**: モデルのバリデーションはミリ秒以下（Pydantic v2 の Rust バックエンドに依存）
**Constraints**: pydantic-ai の `result_type` が Pydantic モデルを要求するアーキテクチャ制約
**Scale/Scope**: 約15モデルクラス + 1レジストリ

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution ファイルがテンプレート状態（プレースホルダーのみ）のため、具体的なゲート検証は該当なし。CLAUDE.md のルール（フォールバック禁止、TDD、型安全、DRY）を遵守する。

**適用ルール**:
- フォールバック禁止: エラー時にデフォルト値で続行しない → 全モデルで `extra="forbid"`、未登録スキーマは例外送出
- TDD: テスト先行で実装
- 型安全: 全関数に型注釈、`Any` 型禁止、`| None` 構文優先
- DRY: 共通ベースモデル（`HachimokuBaseModel`）で `ConfigDict` を一元管理

**結果**: ゲート通過（違反なし）

## Project Structure

### Documentation (this feature)

```text
specs/002-domain-models/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── models.py        # Python モデル定義のインターフェース契約
└── tasks.md             # Phase 2 output (/speckit.tasks で生成)
```

### Source Code (repository root)

```text
src/hachimoku/
├── __init__.py              # 既存エントリポイント
└── models/
    ├── __init__.py          # 公開 API（全モデル re-export）
    ├── _base.py             # HachimokuBaseModel（ConfigDict 共通設定）
    ├── severity.py          # Severity 列挙型、終了コードマッピング
    ├── review.py            # FileLocation, ReviewIssue
    ├── agent_result.py      # AgentSuccess, AgentError, AgentTimeout, AgentResult
    ├── report.py            # ReviewReport
    ├── schemas/
    │   ├── __init__.py      # SCHEMA_REGISTRY, スキーマ公開 API
    │   ├── _base.py         # BaseAgentOutput
    │   ├── scored_issues.py
    │   ├── severity_classified.py
    │   ├── test_gap.py
    │   ├── multi_dimensional.py
    │   ├── category_classification.py
    │   └── improvement_suggestions.py
    └── history.py           # DiffReviewRecord, PRReviewRecord, FileReviewRecord, ReviewHistoryRecord

tests/
└── unit/
    └── models/
        ├── __init__.py
        ├── test_severity.py
        ├── test_review.py
        ├── test_agent_result.py
        ├── test_report.py
        ├── test_schemas.py
        └── test_history.py
```

**Structure Decision**: `src/hachimoku/models/` パッケージとして既存の `src/hachimoku/` 配下に配置。モデルのドメイン領域ごとにモジュールを分離し、`__init__.py` で公開 API を一元管理する。出力スキーマは `schemas/` サブパッケージに分離し、SCHEMA_REGISTRY と共に管理する。

## Complexity Tracking

> Constitution Check に違反なし。追加の正当化は不要。
