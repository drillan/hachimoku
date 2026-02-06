# Tasks: ドメインモデル・出力スキーマ定義

**Input**: Design documents from `/specs/002-domain-models/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/models.py, research.md, quickstart.md

**Tests**: TDD 必須（Constitution Art.1 + quickstart.md に明記）

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: プロジェクト構造とパッケージの初期化

- [ ] T001 Create `src/hachimoku/models/` package directory with `__init__.py` (empty, placeholder for re-exports)
- [ ] T002 [P] Create `src/hachimoku/models/schemas/` sub-package directory with `__init__.py` (empty, placeholder for SCHEMA_REGISTRY)
- [ ] T003 [P] Create `tests/unit/models/` test package directory with `__init__.py`
- [ ] T004 [P] Verify dev dependencies (pytest) are installed: `uv --directory $PROJECT_ROOT add --dev pytest` (if not already)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存する基盤モデルの実装

**⚠️ CRITICAL**: US1/US2/US3 は本フェーズ完了まで開始不可

### Tests for Foundational

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T005 [P] Write tests for `HachimokuBaseModel` in `tests/unit/models/test_base.py`: extra="forbid" により未定義フィールドが拒否されること
- [ ] T006 [P] Write tests for `Severity` in `tests/unit/models/test_severity.py`: 列挙値の定義（Critical/Important/Suggestion/Nitpick）、大文字小文字非依存の入力正規化、順序比較（`SEVERITY_ORDER` 基準で Critical > Important > Suggestion > Nitpick）、不正な値でのエラー

### Implementation for Foundational

- [ ] T007 [P] Implement `HachimokuBaseModel` in `src/hachimoku/models/_base.py`: `ConfigDict(extra="forbid")` を設定した共通基底クラス
- [ ] T008 Implement `Severity` enum and `SEVERITY_ORDER` in `src/hachimoku/models/severity.py`: `StrEnum` による4段階重大度、比較演算子（`__lt__`, `__le__`, `__gt__`, `__ge__`）の実装。大文字小文字非依存は Pydantic フィールドバリデータで実現（モデル側で定義）
- [ ] T009 Run Red→Green cycle: confirm T005/T006 tests pass after T007/T008 implementation

**Checkpoint**: `HachimokuBaseModel` と `Severity` が利用可能。全後続タスクの基盤

---

## Phase 3: User Story 1 - 共通ドメインモデルによるエージェント結果の型安全な表現 (Priority: P1) 🎯 MVP

**Goal**: Severity, FileLocation, ReviewIssue, CostInfo, AgentResult（判別共用体）、ReviewSummary, ReviewReport を実装し、エージェント結果を型安全に表現可能にする

**Independent Test**: モデルクラスをインポートし、各フィールドの型検証・制約検証・判別共用体のデシリアライズが正しく動作する

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T010 [P] [US1] Write tests for `FileLocation` and `ReviewIssue` in `tests/unit/models/test_review.py`: FileLocation の制約（file_path 空文字不可、line_number >= 1）、ReviewIssue の必須フィールド検証（agent_name/severity/description）、オプションフィールド（location/suggestion/category）のデフォルト None、Severity の大文字小文字非依存入力（`field_validator` 経由）、extra="forbid" による追加フィールド拒否
- [ ] T011 [P] [US1] Write tests for `CostInfo`, `AgentSuccess`, `AgentError`, `AgentTimeout`, `AgentResult` in `tests/unit/models/test_agent_result.py`: CostInfo の制約（非負値）、AgentSuccess の制約（elapsed_time > 0, cost オプション）、AgentError の制約（error_message 空文字不可）、AgentTimeout の制約（timeout_seconds > 0）、AgentResult の判別共用体デシリアライズ（status フィールドによる型自動選択）、extra="forbid" 検証
- [ ] T012 [P] [US1] Write tests for `ReviewSummary` and `ReviewReport` in `tests/unit/models/test_report.py`: ReviewSummary の制約（total_issues >= 0, total_elapsed_time >= 0.0, max_severity None 許容）、ReviewReport の results 空リスト許容（SC-006）、extra="forbid" 検証

### Implementation for User Story 1

- [ ] T013 [P] [US1] Implement `FileLocation` and `ReviewIssue` in `src/hachimoku/models/review.py`: contracts/models.py の定義に準拠。ReviewIssue の severity フィールドに `@field_validator(mode="before")` で大文字小文字非依存の正規化を実装
- [ ] T014 [P] [US1] Implement `CostInfo`, `AgentSuccess`, `AgentError`, `AgentTimeout`, `AgentResult` in `src/hachimoku/models/agent_result.py`: contracts/models.py の定義に準拠。`AgentResult = Annotated[Union[...], Field(discriminator="status")]`
- [ ] T015 [US1] Implement `ReviewSummary` and `ReviewReport` in `src/hachimoku/models/report.py`: contracts/models.py の定義に準拠。ReviewReport.results は `list[AgentResult]` で空リスト許容
- [ ] T016 [US1] Run Red→Green cycle: confirm T010/T011/T012 tests pass after T013/T014/T015 implementation

**Checkpoint**: 共通ドメインモデルが完成。AgentResult の判別共用体による型安全なエージェント結果表現が利用可能

---

## Phase 4: User Story 2 - 出力スキーマによるエージェント出力の型検証 (Priority: P1)

**Goal**: BaseAgentOutput と6種の出力スキーマ、SCHEMA_REGISTRY を実装し、エージェント出力の型検証を可能にする

**Independent Test**: 各スキーマに有効/無効データを入力し、バリデーション成功/失敗を検証。SCHEMA_REGISTRY で名前からスキーマを取得

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T017 [P] [US2] Write tests for all output schemas and SCHEMA_REGISTRY in `tests/unit/models/test_schemas.py`: BaseAgentOutput の issues フィールド検証、ScoredIssues の overall_score 制約（0.0-10.0）、SeverityClassified の computed_field issues 導出、TestGapAssessment の coverage_gaps/risk_level 検証、MultiDimensionalAnalysis の dimensions 検証（DimensionScore の score 0.0-10.0）、CategoryClassification の categories 検証、ImprovementSuggestions の suggestions 検証（ImprovementItem のフィールド制約）、SCHEMA_REGISTRY の6種全登録確認・名前取得・未登録名での SchemaNotFoundError・重複登録での DuplicateSchemaError、extra="forbid" 検証

### Implementation for User Story 2

- [ ] T018 [P] [US2] Implement `BaseAgentOutput` in `src/hachimoku/models/schemas/_base.py`: contracts/models.py の定義に準拠
- [ ] T019 [P] [US2] Implement `ScoredIssues` in `src/hachimoku/models/schemas/scored_issues.py`: BaseAgentOutput 継承、overall_score (0.0-10.0)
- [ ] T020 [P] [US2] Implement `SeverityClassified` in `src/hachimoku/models/schemas/severity_classified.py`: BaseAgentOutput 継承、4段階分類リスト + computed_field で issues 導出
- [ ] T021 [P] [US2] Implement `TestGapAssessment` and `CoverageGap` in `src/hachimoku/models/schemas/test_gap.py`: BaseAgentOutput 継承
- [ ] T022 [P] [US2] Implement `MultiDimensionalAnalysis` and `DimensionScore` in `src/hachimoku/models/schemas/multi_dimensional.py`: BaseAgentOutput 継承
- [ ] T023 [P] [US2] Implement `CategoryClassification` in `src/hachimoku/models/schemas/category_classification.py`: BaseAgentOutput 継承
- [ ] T024 [P] [US2] Implement `ImprovementSuggestions` and `ImprovementItem` in `src/hachimoku/models/schemas/improvement_suggestions.py`: BaseAgentOutput 継承
- [ ] T025 [US2] Implement `SCHEMA_REGISTRY`, `get_schema()`, `register_schema()`, `SchemaNotFoundError`, `DuplicateSchemaError` in `src/hachimoku/models/schemas/__init__.py`: 6種のスキーマを初期登録
- [ ] T026 [US2] Run Red→Green cycle: confirm T017 tests pass after T018-T025 implementation

**Checkpoint**: 6種の出力スキーマと SCHEMA_REGISTRY が利用可能。エージェント出力の型検証が可能

---

## Phase 5: User Story 3 - Severity マッピングによる終了コード決定 (Priority: P2)

**Goal**: Severity から終了コードへのマッピングを実装し、レビュー結果から終了コードを一意に決定可能にする

**Independent Test**: 各 Severity 値と None に対して `determine_exit_code()` を呼び出し、期待する終了コード（0/1/2）が返されることを検証

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T027 [US3] Write tests for `determine_exit_code()` and exit code constants in `tests/unit/models/test_severity.py` (既存テストファイルに追加): Critical→1、Important→2、Suggestion→0、Nitpick→0、None→0 の各パターン、EXIT_CODE_SUCCESS/EXIT_CODE_CRITICAL/EXIT_CODE_IMPORTANT の定数値検証

### Implementation for User Story 3

- [ ] T028 [US3] Implement `determine_exit_code()` in `src/hachimoku/models/severity.py` (既存ファイルに追加): contracts/models.py の定義に準拠。EXIT_CODE_SUCCESS/EXIT_CODE_CRITICAL/EXIT_CODE_IMPORTANT 定数を使用
- [ ] T029 [US3] Run Red→Green cycle: confirm T027 tests pass after T028 implementation

**Checkpoint**: Severity → 終了コードのマッピングが利用可能。CLI やレビューエンジンが終了コードを決定可能

---

## Phase 6: User Story 1 (続) - ReviewHistoryRecord 判別共用体 (Priority: P1)

**Goal**: DiffReviewRecord, PRReviewRecord, FileReviewRecord, ReviewHistoryRecord 判別共用体を実装し、JSONL 蓄積用レコードの型安全な表現を可能にする

**Independent Test**: 各レコードモデルに有効/無効データを入力し、review_mode による判別共用体のデシリアライズを検証

### Tests for User Story 1 (History)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T030 [US1] Write tests for `DiffReviewRecord`, `PRReviewRecord`, `FileReviewRecord`, `ReviewHistoryRecord` in `tests/unit/models/test_history.py`: CommitHash の制約（40文字16進数、大文字不可）、DiffReviewRecord の必須フィールド（commit_hash/branch_name/reviewed_at/results/summary）、PRReviewRecord の pr_number >= 1 制約、FileReviewRecord の file_paths 最低1要素・重複排除バリデータ・working_directory 絶対パス検証、ReviewHistoryRecord の review_mode 判別共用体デシリアライズ、extra="forbid" 検証

### Implementation for User Story 1 (History)

- [ ] T031 [US1] Implement `CommitHash` type alias, `DiffReviewRecord`, `PRReviewRecord`, `FileReviewRecord`, `ReviewHistoryRecord` in `src/hachimoku/models/history.py`: contracts/models.py の定義に準拠。FileReviewRecord の `file_paths` 重複排除バリデータと `working_directory` 絶対パスバリデータを実装
- [ ] T032 [US1] Run Red→Green cycle: confirm T030 tests pass after T031 implementation

**Checkpoint**: ReviewHistoryRecord 判別共用体が利用可能。JSONL 蓄積の基盤が整備

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 公開 API の整備と品質チェック

- [ ] T033 Update `src/hachimoku/models/__init__.py` with all public model re-exports: Severity, FileLocation, ReviewIssue, CostInfo, AgentSuccess, AgentError, AgentTimeout, AgentResult, ReviewSummary, ReviewReport, BaseAgentOutput, 6種スキーマ, SCHEMA_REGISTRY, get_schema, register_schema, SchemaNotFoundError, DuplicateSchemaError, CommitHash, DiffReviewRecord, PRReviewRecord, FileReviewRecord, ReviewHistoryRecord, determine_exit_code, EXIT_CODE_SUCCESS, EXIT_CODE_CRITICAL, EXIT_CODE_IMPORTANT, SEVERITY_ORDER
- [ ] T034 Update `src/hachimoku/models/schemas/__init__.py` with schema sub-package public exports (BaseAgentOutput, ScoredIssues, SeverityClassified, TestGapAssessment, MultiDimensionalAnalysis, CategoryClassification, ImprovementSuggestions, CoverageGap, DimensionScore, ImprovementItem, SCHEMA_REGISTRY, get_schema, register_schema, SchemaNotFoundError, DuplicateSchemaError)
- [ ] T035 Run full test suite: `uv --directory $PROJECT_ROOT run pytest tests/unit/models/ -v`
- [ ] T036 Run quality checks: `uv --directory $PROJECT_ROOT run ruff check --fix src/hachimoku/models/ tests/unit/models/ && uv --directory $PROJECT_ROOT run ruff format src/hachimoku/models/ tests/unit/models/ && uv --directory $PROJECT_ROOT run mypy src/hachimoku/models/`
- [ ] T037 Run quickstart.md validation: quickstart.md の使用例コードが実際に動作することを確認

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion + Phase 3 の ReviewIssue（BaseAgentOutput が ReviewIssue を使用）
- **User Story 3 (Phase 5)**: Depends on Phase 2 completion（Severity のみ依存）
- **User Story 1 History (Phase 6)**: Depends on Phase 3 completion（AgentResult, ReviewSummary を使用）
- **Polish (Phase 7)**: Depends on Phase 3, 4, 5, 6 all complete

### User Story Dependencies

- **User Story 1 (P1) - Phase 3**: Phase 2 完了後に開始可能。他ストーリーに依存なし
- **User Story 2 (P1) - Phase 4**: Phase 3 の ReviewIssue に依存（BaseAgentOutput.issues で使用）
- **User Story 3 (P2) - Phase 5**: Phase 2 の Severity のみに依存。Phase 3/4 と並行実行可能
- **User Story 1 History - Phase 6**: Phase 3 の AgentResult/ReviewSummary に依存

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Red)
- Implementation must make tests pass (Green)
- Red→Green cycle confirmed before moving to next phase

### Parallel Opportunities

**Phase 1 (Setup)**:
- T002, T003, T004 は全て並行実行可能

**Phase 2 (Foundational)**:
- T005, T006 テスト作成は並行可能
- T007 は独立実装可能（T008 は T007 に依存しない）

**Phase 3 (US1)**:
- T010, T011, T012 テスト作成は全て並行可能
- T013, T014 実装は並行可能（T015 は T014 の AgentResult に依存）

**Phase 4 (US2)**:
- T017 は単一テストファイルのため直列
- T018-T024 は全て並行可能（異なるファイル、依存なし）
- T025 は T018-T024 に依存

**Phase 5 (US3)**:
- Phase 2 完了後、Phase 3/4 と並行開始可能

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Write tests for FileLocation/ReviewIssue in tests/unit/models/test_review.py"
Task: "Write tests for AgentResult in tests/unit/models/test_agent_result.py"
Task: "Write tests for ReviewReport in tests/unit/models/test_report.py"

# After tests written, launch parallel model implementations:
Task: "Implement FileLocation/ReviewIssue in src/hachimoku/models/review.py"
Task: "Implement AgentResult in src/hachimoku/models/agent_result.py"
# Then sequentially: ReviewReport (depends on AgentResult)
```

## Parallel Example: User Story 2

```bash
# After BaseAgentOutput implemented, launch all 6 schemas in parallel:
Task: "Implement ScoredIssues in src/hachimoku/models/schemas/scored_issues.py"
Task: "Implement SeverityClassified in src/hachimoku/models/schemas/severity_classified.py"
Task: "Implement TestGapAssessment in src/hachimoku/models/schemas/test_gap.py"
Task: "Implement MultiDimensionalAnalysis in src/hachimoku/models/schemas/multi_dimensional.py"
Task: "Implement CategoryClassification in src/hachimoku/models/schemas/category_classification.py"
Task: "Implement ImprovementSuggestions in src/hachimoku/models/schemas/improvement_suggestions.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (`HachimokuBaseModel`, `Severity`)
3. Complete Phase 3: User Story 1 (共通ドメインモデル)
4. **STOP and VALIDATE**: テスト全 Green + 品質チェック通過
5. MVP として利用可能: エージェント結果の型安全な表現

### Incremental Delivery

1. Setup + Foundational → 基盤完成
2. User Story 1 → テスト独立検証 → MVP (共通モデル)
3. User Story 2 → テスト独立検証 → 出力スキーマ利用可能
4. User Story 3 → テスト独立検証 → 終了コード決定利用可能
5. User Story 1 History → テスト独立検証 → JSONL 蓄積基盤
6. Polish → 公開 API 整備 + 全体品質確認

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Phase 3) → User Story 1 History (Phase 6)
   - Developer B: User Story 3 (Phase 5、Severity のみ依存) → User Story 2 (Phase 4、Phase 3 完了待ち)
3. Polish は全ストーリー完了後に実施

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD: tests MUST fail before implementing (Red→Green cycle)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
