# Tasks: 設定管理

**Input**: Design documents from `/specs/004-configuration/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: TDD 厳守（CLAUDE.md）。テスト作成 → Red 確認 → 実装（Green）→ 品質チェック。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 設定管理モジュールのディレクトリ構造とパッケージ初期化

- [ ] T001 Create `src/hachimoku/config/` package with `src/hachimoku/config/__init__.py`
- [ ] T002 [P] Create `tests/unit/config/` package with `tests/unit/config/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存する設定モデル（OutputFormat, AgentConfig, HachimokuConfig）を TDD で実装する

**⚠️ CRITICAL**: 設定モデルは全 US の基盤。このフェーズが完了するまで US のタスクに着手しない

### Tests

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T003 Write tests for `OutputFormat` enum (`"markdown"`, `"json"`, invalid values) in `tests/unit/models/test_config.py`
- [ ] T004 [P] Write tests for `AgentConfig` model in `tests/unit/models/test_config.py`:
  - デフォルト値: enabled=True, model=None, timeout=None, max_turns=None
  - validation: model が非 None 時 min_length=1（空文字列で ValidationError）, timeout/max_turns gt=0
  - extra="forbid" (未知キー拒否)
- [ ] T005 [P] Write tests for `HachimokuConfig` model in `tests/unit/models/test_config.py`:
  - デフォルト値のみでインスタンス構築可能
  - 各フィールドのデフォルト値（model="anthropic:claude-opus-4-6", timeout=300, max_turns=10, parallel=True, base_branch="main", output_format=MARKDOWN, save_reviews=True, show_cost=False, max_files_per_review=100, agents={})
  - バリデーション: timeout/max_turns/max_files_per_review > 0, model/base_branch min_length=1, output_format enum, parallel に非 boolean 値（例: 文字列 "abc"）で ValidationError
  - agents キーの名前パターン検証（`^[a-z0-9-]+$`、不正名でエラー）
  - extra="forbid": 未知キー拒否で `ValidationError`（`match=` で未知キー名を含むことを検証）
  - frozen=True (不変性)

### Implementation

- [ ] T006 Implement `OutputFormat` StrEnum in `src/hachimoku/models/config.py` — contract: `specs/004-configuration/contracts/config_models.py`
- [ ] T007 Implement `AgentConfig` model in `src/hachimoku/models/config.py` — contract: `specs/004-configuration/contracts/config_models.py`
- [ ] T008 Implement `HachimokuConfig` model with `field_validator("agents")` in `src/hachimoku/models/config.py` — contract: `specs/004-configuration/contracts/config_models.py`
- [ ] T009 Run quality checks: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: 設定モデル（OutputFormat, AgentConfig, HachimokuConfig）が全テストを通過し、品質チェック合格

---

## Phase 3: User Story 4 - プロジェクト設定ディレクトリの探索 (Priority: P1) 🎯 MVP

**Goal**: カレントディレクトリから親ディレクトリへ遡って `.hachimoku/` を探索し、プロジェクトルートを特定する。pyproject.toml およびユーザーグローバル設定パスも提供する。

**Independent Test**: `tmp_path` にディレクトリ構造を構築し、`find_project_root()`, `find_config_file()`, `find_pyproject_toml()`, `get_user_config_path()` の戻り値を検証する。

**Acceptance Scenarios**:
- カレントディレクトリに `.hachimoku/` が存在 → カレントディレクトリ返却
- 親ディレクトリに `.hachimoku/` が存在 → 親ディレクトリ返却
- ルートまで見つからない → None 返却
- pyproject.toml の探索（独立探索）
- ユーザーグローバル設定パス（`~/.config/hachimoku/config.toml`）

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T010 [P] [US4] Write tests for `find_project_root()` in `tests/unit/config/test_locator.py`:
  - カレントディレクトリに `.hachimoku/` あり → そのパスを返す
  - 親ディレクトリに `.hachimoku/` あり → 親パスを返す
  - ルートまで見つからない → None
- [ ] T011 [P] [US4] Write tests for `find_config_file()` in `tests/unit/config/test_locator.py`:
  - プロジェクトルートあり → `.hachimoku/config.toml` のパスを返す（config.toml が実際に存在しなくてもパスを構築する）
  - プロジェクトルートなし → None
- [ ] T012 [P] [US4] Write tests for `find_pyproject_toml()` in `tests/unit/config/test_locator.py`:
  - カレントに pyproject.toml あり → そのパスを返す
  - 親に pyproject.toml あり → そのパスを返す
  - 見つからない → None
  - `.hachimoku/` と `pyproject.toml` が異なるディレクトリにあるケース → それぞれ独立に検出（FR-CF-005 独立探索）
- [ ] T013 [P] [US4] Write test for `get_user_config_path()` in `tests/unit/config/test_locator.py`:
  - `~/.config/hachimoku/config.toml` のパスを返す

### Implementation for User Story 4

- [ ] T014 [US4] Implement `find_project_root()` in `src/hachimoku/config/_locator.py` — contract: `specs/004-configuration/contracts/project_locator.py`
- [ ] T015 [US4] Implement `find_config_file()` in `src/hachimoku/config/_locator.py` — contract: `specs/004-configuration/contracts/project_locator.py`
- [ ] T016 [P] [US4] Implement `find_pyproject_toml()` in `src/hachimoku/config/_locator.py` — contract: `specs/004-configuration/contracts/project_locator.py`
- [ ] T017 [P] [US4] Implement `get_user_config_path()` in `src/hachimoku/config/_locator.py` — contract: `specs/004-configuration/contracts/project_locator.py`
- [ ] T018 [US4] Export `find_project_root` from `src/hachimoku/config/__init__.py`
- [ ] T019 [US4] Run quality checks: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: プロジェクト探索機能が全テストを通過し、品質チェック合格。`find_project_root()` がサブディレクトリからプロジェクトルートを正しく特定。

---

## Phase 4: User Story 2 - プロジェクト設定ファイルの読み込みと検証 (Priority: P1)

**Goal**: `.hachimoku/config.toml` と `pyproject.toml [tool.hachimoku]` を TOML 形式で読み込み、辞書として返す。不正な TOML やアクセスエラーは例外として送出する。

**Independent Test**: `tmp_path` に各種 TOML ファイルを作成し、`load_toml_config()` と `load_pyproject_config()` の正常系・エラー系を検証する。

**Acceptance Scenarios**:
- 有効な config.toml → 正しくパースされた辞書
- TOML 構文エラー → `TOMLDecodeError` 送出
- ファイル不在 → `FileNotFoundError` 送出
- 読み取り権限なし → `PermissionError` 送出
- pyproject.toml に `[tool.hachimoku]` あり → そのセクションの辞書
- pyproject.toml に `[tool.hachimoku]` なし → None
- 空の config.toml → 空辞書

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US2] Write tests for `load_toml_config()` in `tests/unit/config/test_loader.py`:
  - 有効な TOML → 辞書返却
  - 空ファイル → 空辞書返却
  - TOML 構文エラー → `TOMLDecodeError`
  - ファイル不在 → `FileNotFoundError`
  - 読み取り権限なし → `PermissionError`
- [ ] T021 [P] [US2] Write tests for `load_pyproject_config()` in `tests/unit/config/test_loader.py`:
  - `[tool.hachimoku]` セクションあり → そのセクションの辞書
  - `[tool.hachimoku]` セクションあるが空 → 空辞書（Edge Case）
  - `[tool.hachimoku]` セクションなし → None
  - `[tool]` セクション自体なし → None
  - TOML 構文エラー → `TOMLDecodeError`

### Implementation for User Story 2

- [ ] T022 [US2] Implement `load_toml_config()` in `src/hachimoku/config/_loader.py` — contract: `specs/004-configuration/contracts/config_resolver.py`
- [ ] T023 [US2] Implement `load_pyproject_config()` in `src/hachimoku/config/_loader.py` — contract: `specs/004-configuration/contracts/config_resolver.py`
- [ ] T024 [US2] Run quality checks: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: TOML 読み込み機能が全テストを通過。有効/無効/不在の設定ファイルが正しく処理される。

---

## Phase 5: User Story 1 - 設定ファイル階層による設定解決 (Priority: P1)

**Goal**: 5層の設定ソース（CLI > .hachimoku/config.toml > pyproject.toml > ~/.config/hachimoku/config.toml > デフォルト値）を階層的にマージし、`HachimokuConfig` を構築する。

**Independent Test**: 複数レイヤーの辞書を用意し、`merge_config_layers()` と `resolve_config()` が正しい優先順位で値を解決することを検証する。

**Acceptance Scenarios**:
- 設定ソースなし → デフォルト値の HachimokuConfig
- .hachimoku/config.toml に `base_branch = "develop"` → 反映、他はデフォルト
- .hachimoku/config.toml と pyproject.toml 両方に base_branch → .hachimoku 優先
- ユーザーグローバル設定のみ → 適用
- CLI `--model sonnet` と .hachimoku `model = "opus"` → CLI 優先
- pyproject.toml に `[tool.hachimoku]` なし → スキップ

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T025 [P] [US1] Write tests for `merge_config_layers()` in `tests/unit/config/test_resolver.py`:
  - 空レイヤーのみ → 空辞書
  - 単一レイヤー → そのまま返却
  - 2レイヤーで上位が上書き
  - None レイヤーはスキップ
  - agents セクションのフィールド単位マージ（R-006）
- [ ] T026 [P] [US1] Write tests for `filter_cli_overrides()` in `tests/unit/config/test_resolver.py`:
  - None 値のキーが除外される
  - 非 None 値は保持される
  - 空辞書 → 空辞書
- [ ] T027 [P] [US1] Write tests for `resolve_config()` in `tests/unit/config/test_resolver.py`:
  - 設定ファイルなし → デフォルト値の HachimokuConfig
  - .hachimoku/config.toml のみ → 反映
  - 5層の優先順位テスト（cli_overrides > config.toml > pyproject.toml > user global > default）
  - cli_overrides の None 値は無視される
  - 不正な設定値 → `ValidationError`（`match=` でフィールド名を含むことを検証: US2 AS2/AS3）
  - start_dir=None → カレントディレクトリ（Path.cwd()）から探索
  - config.toml の TOML 構文エラー → `TOMLDecodeError` が伝播
  - config.toml の読み取り権限なし → `PermissionError` が伝播

### Implementation for User Story 1

- [ ] T028 [US1] Implement `merge_config_layers()` in `src/hachimoku/config/_resolver.py` — contract: `specs/004-configuration/contracts/config_resolver.py`
- [ ] T029 [US1] Implement `filter_cli_overrides()` in `src/hachimoku/config/_resolver.py` — contract: `specs/004-configuration/contracts/config_resolver.py`
- [ ] T030 [US1] Implement `resolve_config()` in `src/hachimoku/config/_resolver.py` — contract: `specs/004-configuration/contracts/config_resolver.py`. Uses `find_config_file()`, `find_pyproject_toml()`, `get_user_config_path()` from `_locator.py` and `load_toml_config()`, `load_pyproject_config()` from `_loader.py`
- [ ] T031 [US1] Export `resolve_config` from `src/hachimoku/config/__init__.py`
- [ ] T032 [US1] Run quality checks: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: 設定解決が全テストを通過。5層の設定ソースが正しい優先順位で解決され、HachimokuConfig が構築される。

---

## Phase 6: User Story 3 - エージェント個別設定によるレビュー動作制御 (Priority: P2)

**Goal**: 設定ファイルの `[agents.<name>]` セクションでエージェントの無効化やモデル/タイムアウト/max_turns の上書きが設定モデルに正しく反映される。

**Independent Test**: エージェント個別設定を含む設定ファイルを読み込み、`HachimokuConfig.agents` に正しく反映されることを検証する。

**Acceptance Scenarios**:
- `[agents.code-reviewer]` で `enabled = false` → agents["code-reviewer"].enabled is False
- `[agents.code-reviewer]` で `model = "haiku"` → agents["code-reviewer"].model == "haiku"
- 存在しないエージェント名 → 設定モデルに保持（エラーとしない）
- 複数ソースのエージェント個別設定がフィールド単位でマージされる

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T033 [P] [US3] Write integration tests for agent config through `resolve_config()` in `tests/unit/config/test_resolver.py`:
  - config.toml に `[agents.code-reviewer]` enabled=false → 反映
  - config.toml に `[agents.code-reviewer]` model="haiku" → 反映
  - 存在しないエージェント名のセクション → 保持
  - 複数ソース（config.toml + user global）のエージェント設定がフィールド単位マージ

### Implementation for User Story 3

- [ ] T034 [US3] Verify agent config integration — merge_config_layers() の agents マージが US3 シナリオを正しく処理することを確認。必要に応じて `src/hachimoku/config/_resolver.py` を修正
- [ ] T035 [US3] Run quality checks: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: エージェント個別設定の全シナリオが通過。複数ソースからのフィールド単位マージが正しく動作。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 品質向上、ドキュメント整合性、quickstart 検証

- [x] T036 Run full test suite: `uv --directory $PROJECT_ROOT run pytest`
- [x] T037 [P] Run final quality checks: `ruff check --fix . && ruff format . && mypy .`
- [x] T038 Validate quickstart.md scenarios work end-to-end (manual verification against `specs/004-configuration/quickstart.md`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US4 (Phase 3)**: Depends on Foundational — No dependencies on other stories
- **US2 (Phase 4)**: Depends on Foundational — No dependencies on other stories (parallel with US4 possible)
- **US1 (Phase 5)**: Depends on US4 + US2 (uses locator and loader functions)
- **US3 (Phase 6)**: Depends on US1 (uses resolve_config, verifies agent merge behavior)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

```text
Phase 1 (Setup)
    ↓
Phase 2 (Foundational: Models)
    ↓
    ├── Phase 3 (US4: Locator) ──┐
    │                            ├── Phase 5 (US1: Resolver)
    └── Phase 4 (US2: Loader) ──┘          ↓
                                    Phase 6 (US3: Agent Config)
                                           ↓
                                    Phase 7 (Polish)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation follows contract definitions
- Quality checks after each story

### Parallel Opportunities

- **Phase 1**: T001 and T002 can run in parallel
- **Phase 2**: T003, T004, T005 (tests) can run in parallel → T006, T007, T008 (implementation) are sequential (same file)
- **Phase 3 + Phase 4**: US4 and US2 can run in parallel (different files)
  - Within US4: T010, T011, T012, T013 (tests) in parallel
  - Within US2: T020, T021 (tests) in parallel
- **Phase 5**: T025, T026, T027 (tests) in parallel
- **Phase 6**: T033 (single test task)

---

## Parallel Example: Phase 3 + Phase 4

```bash
# US4 tests (all in test_locator.py, but separate test functions):
Task: T010 "Write tests for find_project_root()"
Task: T011 "Write tests for find_config_file()"
Task: T012 "Write tests for find_pyproject_toml()"
Task: T013 "Write test for get_user_config_path()"

# US2 tests (all in test_loader.py, but separate test functions):
Task: T020 "Write tests for load_toml_config()"
Task: T021 "Write tests for load_pyproject_config()"
```

---

## Implementation Strategy

### MVP First (US4 + US2 + US1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational — 設定モデル実装
3. Complete Phase 3: US4 — プロジェクト探索
4. Complete Phase 4: US2 — TOML 読み込み
5. Complete Phase 5: US1 — 5層マージ → **STOP and VALIDATE**: `resolve_config()` がデフォルト値と設定ファイルから正しく HachimokuConfig を構築することを検証
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → モデル基盤
2. US4 (Locator) → テスト独立検証
3. US2 (Loader) → テスト独立検証
4. US1 (Resolver) → 統合検証（MVP!）
5. US3 (Agent Config) → カスタマイズ機能追加
6. Polish → 最終品質チェック

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD strict: テスト → Red 確認 → 実装（Green）→ 品質チェック
- `AGENT_NAME_PATTERN` は `hachimoku.agents.models` から import（DRY）
- 全モデルは `HachimokuBaseModel` 継承 (`extra="forbid"`, `frozen=True`)
- 設定マージは辞書操作で実現（R-001）、agents はフィールド単位マージ（R-006）
