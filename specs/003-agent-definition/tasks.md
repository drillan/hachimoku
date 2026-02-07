# Tasks: エージェント定義・ローダー

**Input**: Design documents from `/specs/003-agent-definition/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/agent.py, research.md, quickstart.md

**Tests**: TDD 必須（CLAUDE.md Art.1）。テストタスクは各フェーズに含まれる。

**Organization**: ユーザーストーリー優先度順に構成。US1/US4 は密結合のため同一フェーズで扱う。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: パッケージ構造の初期化とテストディレクトリの準備

- [ ] T001 Create `src/hachimoku/agents/` package with `__init__.py` (empty, public API export は最終フェーズで追加)
- [ ] T002 [P] Create `src/hachimoku/agents/_builtin/` package with `__init__.py` (importlib.resources 用マーカー)
- [ ] T003 [P] Create `tests/unit/agents/` package with `__init__.py`

**Checkpoint**: パッケージ構造が完成し、import が可能な状態

---

## Phase 2: Foundational — モデル定義 (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存する `Phase`, `ApplicabilityRule`, `AgentDefinition`, `LoadError`, `LoadResult` モデルの実装

**⚠️ CRITICAL**: US1/US2/US3/US4 のすべてがこのフェーズのモデルに依存する

### Tests for Phase 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T004 Write `Phase` StrEnum tests in `tests/unit/agents/test_models.py` — Phase 列挙値（early/main/final）、PHASE_ORDER 定数のソート順序検証
- [ ] T005 Write `ApplicabilityRule` tests in `tests/unit/agents/test_models.py` — デフォルト値、正規表現バリデーション（有効/無効パターン）、frozen 検証、extra=forbid 検証
- [ ] T006 Write `AgentDefinition` tests in `tests/unit/agents/test_models.py` — 全必須フィールド、name パターンバリデーション（`^[a-z0-9-]+$`）、output_schema の SCHEMA_REGISTRY 解決（model_validator）、存在しないスキーマ名でのエラー、デフォルト値（allowed_tools=[], applicability.always=True, phase=main）、frozen 検証、extra=forbid 検証
- [ ] T007 Write `LoadError` and `LoadResult` tests in `tests/unit/agents/test_models.py` — フィールドバリデーション、frozen 検証、errors のデフォルト空リスト

### Implementation for Phase 2

- [ ] T008 Implement `Phase` StrEnum and `PHASE_ORDER` constant in `src/hachimoku/agents/models.py` per contracts/agent.py
- [ ] T009 Implement `ApplicabilityRule` model in `src/hachimoku/agents/models.py` — `content_patterns` の `field_validator` で `re.compile()` 検証を含む
- [ ] T010 Implement `AgentDefinition` model in `src/hachimoku/agents/models.py` — `model_validator(mode="before")` で `output_schema` → `resolved_schema` を SCHEMA_REGISTRY から解決
- [ ] T011 Implement `LoadError` and `LoadResult` models in `src/hachimoku/agents/models.py`
- [ ] T012 Run all Phase 2 tests green: `uv --directory $PROJECT_ROOT run pytest tests/unit/agents/test_models.py -v`

**Checkpoint**: 全モデルが定義され、テストが green。ユーザーストーリーの実装に進める状態

---

## Phase 3: User Story 1 + User Story 4 — TOML 読み込み & ビルトイン6エージェント (Priority: P1) 🎯 MVP

**Goal**: TOML 形式のエージェント定義ファイルを読み込み AgentDefinition として構築する。6つのビルトインエージェント TOML 定義を標準提供する。

**Independent Test**: `load_builtin_agents()` を呼び出し、6つの AgentDefinition が正しく構築されることで検証。各エージェントの output_schema が SCHEMA_REGISTRY の対応スキーマと一致することを確認。

**US1 と US4 を統合する理由**: US1（ローダー）は US4（ビルトイン定義ファイル）がないとエンドツーエンドで検証不可。US4 は US1 のローダーで読み込んではじめて検証可能。両者は一体として実装・テストする。

### Tests for US1 + US4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T013 Write `_load_single_agent` tests in `tests/unit/agents/test_loader.py` — 正常な TOML dict からの AgentDefinition 構築、不正 TOML（構文エラー）での例外、必須フィールド欠損での ValidationError
- [ ] T014 [P] Write `load_builtin_agents` tests in `tests/unit/agents/test_loader.py` — 6エージェント全件読み込み、各エージェント名の存在確認（code-reviewer, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer, code-simplifier）、errors が空であること
- [ ] T015 [P] Write builtin agent validation tests in `tests/unit/agents/test_loader.py` — 各ビルトインエージェントの output_schema が正しいスキーマ名であること（code-reviewer→scored_issues, silent-failure-hunter→severity_classified, pr-test-analyzer→test_gap_assessment, type-design-analyzer→multi_dimensional_analysis, comment-analyzer→category_classification, code-simplifier→improvement_suggestions）、各エージェントの phase が適切であること、各エージェントの applicability ルールが設定されていること

### Implementation for US1 + US4

- [ ] T016 Implement `_load_single_agent(path: Path) -> AgentDefinition` in `src/hachimoku/agents/loader.py` — `tomllib.load()` で TOML パース → `AgentDefinition.model_validate(data)` でモデル構築
- [ ] T017 Implement `load_builtin_agents() -> LoadResult` in `src/hachimoku/agents/loader.py` — `importlib.resources.files("hachimoku.agents._builtin")` でリソース取得、`.toml` ファイル列挙、各ファイルを `_load_single_agent()` で読み込み、成功/失敗を LoadResult に分離
- [ ] T018 [P] Create builtin TOML: `src/hachimoku/agents/_builtin/code-reviewer.toml` — always=true, phase=main, output_schema=scored_issues
- [ ] T019 [P] Create builtin TOML: `src/hachimoku/agents/_builtin/silent-failure-hunter.toml` — content_patterns でエラーハンドリングパターン検出, phase=main, output_schema=severity_classified
- [ ] T020 [P] Create builtin TOML: `src/hachimoku/agents/_builtin/pr-test-analyzer.toml` — file_patterns でテストファイル検出, phase=main, output_schema=test_gap_assessment
- [ ] T021 [P] Create builtin TOML: `src/hachimoku/agents/_builtin/type-design-analyzer.toml` — file_patterns + content_patterns で型定義検出, phase=main, output_schema=multi_dimensional_analysis
- [ ] T022 [P] Create builtin TOML: `src/hachimoku/agents/_builtin/comment-analyzer.toml` — content_patterns でコメントパターン検出, phase=final, output_schema=category_classification
- [ ] T023 [P] Create builtin TOML: `src/hachimoku/agents/_builtin/code-simplifier.toml` — always=true, phase=final, output_schema=improvement_suggestions
- [ ] T024 Run all US1+US4 tests green: `uv --directory $PROJECT_ROOT run pytest tests/unit/agents/test_loader.py -v`

**Checkpoint**: ビルトイン6エージェントが TOML から正常に読み込まれ、全テスト green

---

## Phase 4: User Story 3 — カスタムエージェント定義によるレビュー拡張 (Priority: P2)

**Goal**: `.hachimoku/agents/` からカスタムエージェントを読み込み、ビルトインとの統合（同名上書き・部分失敗許容）を実現する。

**Independent Test**: tmp_path にカスタム TOML を配置し、`load_custom_agents()` と `load_agents()` で正しく読み込まれることを検証。

### Tests for US3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T030 Write `load_custom_agents` tests in `tests/unit/agents/test_loader.py` — 正常なカスタム定義の読み込み、ディレクトリ不在時の空 LoadResult、.toml 以外のファイル無視、不正な TOML ファイルの部分失敗（errors にエラー情報、他は正常読み込み）
- [ ] T031 [P] Write `load_agents` integration tests in `tests/unit/agents/test_loader.py` — ビルトインのみ（custom_dir=None）、ビルトイン+カスタム統合、同名カスタムによるビルトイン上書き、不正カスタムが同名ビルトインを上書きしない（ビルトイン維持）、全エラーの統合

### Implementation for US3

- [ ] T032 Implement `load_custom_agents(custom_dir: Path) -> LoadResult` in `src/hachimoku/agents/loader.py` — ディレクトリ存在チェック → .toml ファイル列挙 → _load_single_agent で読み込み → 成功/失敗を LoadResult に分離
- [ ] T033 Implement `load_agents(custom_dir: Path | None = None) -> LoadResult` in `src/hachimoku/agents/loader.py` — load_builtin_agents() + load_custom_agents() 統合、名前ベースの上書きロジック（カスタム成功時のみ上書き）、エラー統合
- [ ] T034 Run all US3 tests green: `uv --directory $PROJECT_ROOT run pytest tests/unit/agents/test_loader.py -v`

**Checkpoint**: カスタムエージェントの読み込み・統合・上書きが正常動作。全テスト green

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: 公開 API 整備、品質チェック、quickstart 検証

- [ ] T035 Update `src/hachimoku/agents/__init__.py` with public API exports — `Phase`, `PHASE_ORDER`, `ApplicabilityRule`, `AgentDefinition`, `LoadError`, `LoadResult`, `load_builtin_agents`, `load_custom_agents`, `load_agents`
- [ ] T036 Run full test suite: `uv --directory $PROJECT_ROOT run pytest -v`
- [ ] T037 Run quality checks: `uv --directory $PROJECT_ROOT run ruff check --fix . && uv --directory $PROJECT_ROOT run ruff format . && uv --directory $PROJECT_ROOT run mypy .`
- [ ] T038 Run quickstart.md validation — quickstart.md の使用例コードが実際の API と一致することを確認

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1+US4 (Phase 3)**: Depends on Phase 2 models
- **US3 (Phase 4)**: Depends on Phase 3 loader implementation
- **Polish (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **US1+US4 (P1)**: Phase 2 完了後に開始可能。他の US に依存しない
- **US3 (P2)**: Phase 3（US1+US4）完了後に開始。ローダーの `_load_single_agent` と `load_builtin_agents` を前提とする

### Within Each Phase

- テストを先に書き、FAIL を確認してから実装
- モデル → ローダーの順
- 各フェーズ完了時にチェックポイントで検証

### Parallel Opportunities

- **Phase 1**: T002, T003 は T001 と並列可能（[P]）
- **Phase 2**: T004〜T007 のテストは順次（同一ファイル）、T008〜T011 の実装は順次（同一ファイル `models.py`）
- **Phase 3**: T014, T015 のテストは並列可能。T018〜T023 の TOML ファイル作成は全て並列可能（[P]）

---

## Parallel Example: Phase 3 (US1+US4)

```text
# After T016, T017 implementation, launch all TOML file creation in parallel:
Task: T018 "Create code-reviewer.toml"
Task: T019 "Create silent-failure-hunter.toml"
Task: T020 "Create pr-test-analyzer.toml"
Task: T021 "Create type-design-analyzer.toml"
Task: T022 "Create comment-analyzer.toml"
Task: T023 "Create code-simplifier.toml"
```

## Implementation Strategy

### MVP First (US1+US4)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational models
3. Complete Phase 3: US1+US4 (Loader + Builtin TOMLs)
4. **STOP and VALIDATE**: 6ビルトインエージェントの読み込みが動作
5. MVP complete — 基本レビュー実行の前提が整う

### Incremental Delivery

1. Setup + Foundational → モデル定義完成
2. US1+US4 → ビルトインエージェント読み込み完成（MVP complete）
3. US3 → カスタムエージェント拡張追加（拡張性）
4. Polish → 公開 API 整備・品質確認

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD strict: テスト → Red 確認 → 実装 → Green → リファクタ
- 全モデルは `HachimokuBaseModel` 継承（`extra="forbid"`, `frozen=True`）
- 品質チェック: `ruff check --fix . && ruff format . && mypy .`
- ビルトインエージェントのシステムプロンプト内容は実装タスク（T018〜T023）で策定
