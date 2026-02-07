# Tasks: CLI インターフェース・初期化

**Input**: Design documents from `/specs/006-cli-interface/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: TDD ワークフロー準拠。各ユーザーストーリーでテストを先行作成し、Red 確認後に実装する。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: CLI パッケージの基盤構造とプロジェクト設定

- [ ] T001 CLI パッケージディレクトリとテストディレクトリを作成する: `src/hachimoku/cli/__init__.py`, `tests/unit/cli/__init__.py`
- [ ] T002 `pyproject.toml` の `[project.scripts]` にデュアルコマンド名エントリを追加する: `8moku = "hachimoku.cli:main"`, `hachimoku = "hachimoku.cli:main"`
- [ ] T003 `pyproject.toml` の依存に `typer>=0.21.1` を追加し、`uv sync` で同期する

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存する ExitCode 定義と基本エントリポイント

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 [P] `tests/unit/cli/test_exit_code.py` に ExitCode の TDD テストを作成する（IntEnum 性質、値の検証、EngineResult.exit_code からの変換）。contracts/exit_code.py の仕様に準拠
- [ ] T005 [P] Red 確認: T004 のテストが失敗することを確認する
- [ ] T006 [P] `src/hachimoku/cli/_exit_code.py` に ExitCode IntEnum を実装する（contracts/exit_code.py 準拠）
- [ ] T006b `src/hachimoku/models/severity.py` の `EXIT_CODE_SUCCESS`, `EXIT_CODE_CRITICAL`, `EXIT_CODE_IMPORTANT` 定数と `determine_exit_code()` の戻り値型を `ExitCode` メンバーに置き換える。`src/hachimoku/engine/_engine.py` の `_determine_exit_code()` 内で直接返している `Literal` 値（`return 3` 等）を `ExitCode` メンバーに置き換え、`EngineResult.exit_code` の型を `Literal[0, 1, 2, 3]` から `ExitCode` に変更する。`models/__init__.py` の公開 API 更新と既存テストの更新を含む
- [ ] T007 `src/hachimoku/cli/__init__.py` に公開 API（`app`, `main`）を定義し、`src/hachimoku/__init__.py` から `cli.main()` への委譲を設定する
- [ ] T008 品質チェック: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: ExitCode と CLI エントリポイントが確立。ユーザーストーリーの実装を開始可能

---

## Phase 3: User Story 1 — デュアルコマンド名と入力モード判定 (Priority: P1) 🎯 MVP

**Goal**: `8moku` / `hachimoku` の両コマンドで位置引数から diff / PR / file モードを自動判定する

**Independent Test**: `8moku --help` と `hachimoku --help` で同一ヘルプが表示され、各引数パターン（なし→diff、整数→PR、パスライク→file、不明→エラー）で正しいモードが判定される

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T009 [P] [US1] `tests/unit/cli/test_input_resolver.py` に InputResolver の TDD テストを作成する。contracts/input_resolver.py の仕様に準拠。テストケース: 引数なし→DiffInput、整数→PRInput、パスライク→FileInput、複数ファイル→FileInput、整数混在→InputError、不明文字列→InputError、`_is_path_like()` と `_is_existing_path()` のヘルパーテスト
- [ ] T010 [P] [US1] `tests/unit/cli/test_app.py` に Typer app の TDD テストを作成する（CliRunner 使用）。テストケース: `--help` 表示、引数なしで diff モード判定（終了コード検証）、不明文字列で終了コード 4
- [ ] T011 [US1] Red 確認: T009, T010 のテストが失敗することを確認する

### Implementation for User Story 1

- [ ] T012 [US1] `src/hachimoku/cli/_input_resolver.py` に ResolvedInput 型（DiffInput, PRInput, FileInput）、InputError 例外、`resolve_input()` 関数を実装する。contracts/input_resolver.py 準拠
- [ ] T013 [US1] `src/hachimoku/cli/_app.py` に Typer app 定義、`main()` 関数、`review_callback()` を実装する。入力モード判定の呼び出しと InputError → 終了コード 4 のエラーハンドリングを含む。contracts/cli_app.py 準拠（レビュー実行はスタブ、US2 で完成）
- [ ] T014 [US1] `config` 予約サブコマンドを `_app.py` に実装する（未実装エラー、終了コード 4）。research.md R-009 準拠。※ `_app.py` 構築と同時に登録する方が効率的なため US1 に含める
- [ ] T015 [US1] 品質チェック: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: 入力モード判定が正しく動作し、`8moku --help` でヘルプが表示される。レビュー実行自体は US2 で接続する

---

## Phase 4: User Story 2 — レビュー実行とストリーム分離・終了コード (Priority: P1)

**Goal**: CLI がレビューを 005-review-engine に委譲し、stdout にレポート出力、stderr に進捗、重大度に応じた終了コードを返す

**Independent Test**: レビュー実行後、stdout にレポートのみ・stderr に進捗のみが出力され、重大度に応じた終了コード（0/1/2/3）が返される

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T016 [P] [US2] `tests/unit/cli/test_app.py` にレビュー実行テストを追加する（CliRunner 使用）。テストケース: diff モードでのレビュー実行（engine モック）、終了コード 0/1/2/3 の検証、stdout/stderr 分離の検証、CLI オプション（`--model`, `--timeout`, `--format`, `--issue` 等）の設定上書き辞書構築検証、boolean フラグペアの三値テスト（`--parallel` → `{"parallel": True}`, `--no-parallel` → `{"parallel": False}`, 未指定 → config_overrides に `parallel` キーなし）
- [ ] T017 [US2] Red 確認: T016 のテストが失敗することを確認する

### Implementation for User Story 2

- [ ] T018 [US2] `src/hachimoku/cli/_app.py` の `review_callback()` にレビュー実行フローを完成させる。ResolvedInput → ReviewTarget 変換、CLI オプション → config_overrides 辞書構築（None 除外、キー名変換: format→output_format, max_files→max_files_per_review）、`run_review()` 呼び出し、stdout レポート出力、ExitCode 変換
- [ ] T019 [US2] 品質チェック: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: diff モード・PR モードでレビューが実行され、正しい終了コードとストリーム分離が動作する

---

## Phase 5: User Story 3 — init サブコマンド (Priority: P2)

**Goal**: `8moku init` で `.hachimoku/` ディレクトリを初期化し、デフォルト設定・エージェント定義・reviews ディレクトリを生成する

**Independent Test**: `8moku init` 実行後、`.hachimoku/config.toml`（コメント付き）、`.hachimoku/agents/` に6エージェント定義、`.hachimoku/reviews/` が生成される

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US3] `tests/unit/cli/test_init_handler.py` に InitHandler の TDD テストを作成する（`tmp_path` 使用）。contracts/init_handler.py 準拠。テストケース: Git リポジトリ内での正常初期化、既存ファイルのスキップ、`--force` での上書き、Git リポジトリ外での InitError、config.toml テンプレートの内容検証、ビルトインエージェント6ファイルのコピー検証
- [ ] T021 [US3] Red 確認: T020 のテストが失敗することを確認する

### Implementation for User Story 3

- [ ] T022 [US3] `src/hachimoku/cli/_init_handler.py` に `run_init()`, `_ensure_git_repository()`, `_generate_config_template()`, `_copy_builtin_agents()` を実装する。contracts/init_handler.py 準拠。`importlib.resources` でビルトイン定義を取得
- [ ] T023 [US3] `src/hachimoku/cli/_app.py` の `init` サブコマンドに InitHandler の呼び出しを接続する。InitError → 終了コード 4 のエラーハンドリング、結果の stderr 表示を実装
- [ ] T024 [US3] 品質チェック: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: `8moku init` と `8moku init --force` が正しく動作する

---

## Phase 6: User Story 4 — file モードの入力解決と確認 (Priority: P2)

**Goal**: file モードの位置引数（ファイル・ディレクトリ・glob パターン）を解決し、`max_files_per_review` 超過時にユーザーに確認を求める

**Independent Test**: 各種入力形式でファイルパスが正しく展開され、超過時に確認プロンプトが表示される

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T025 [P] [US4] `tests/unit/cli/test_file_resolver.py` に FileResolver の TDD テストを作成する（`tmp_path` 使用）。contracts/file_resolver.py 準拠。テストケース: 単一ファイル、複数ファイル、ディレクトリ再帰探索、glob パターン展開、存在しないパスで FileResolutionError、シンボリックリンク循環参照の検出と警告、相対パスと絶対パスの解決、`_is_glob_pattern()` ヘルパーテスト
- [ ] T026 [US4] Red 確認: T025 のテストが失敗することを確認する

### Implementation for User Story 4

- [ ] T027 [US4] `src/hachimoku/cli/_file_resolver.py` に `resolve_files()`, `_expand_single_path()`, `_is_glob_pattern()` を実装する。contracts/file_resolver.py 準拠
- [ ] T028 [US4] `src/hachimoku/cli/_app.py` の `review_callback()` に file モード完全対応を追加する。FileInput → `resolve_files()` → ResolvedFiles、`max_files_per_review` 超過時の確認プロンプト（`typer.confirm()`）、`--no-confirm` オプション対応、FileResolutionError → 終了コード 4 のエラーハンドリング、空結果の正常終了（終了コード 0）
- [ ] T029 [US4] `tests/unit/cli/test_app.py` に file モード統合テストを追加する（CliRunner 使用）。テストケース: ファイルパス指定でのレビュー実行、`--no-confirm` の動作、存在しないファイルでの終了コード 4
- [ ] T030 [US4] 品質チェック: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: file モードの全機能（ファイル・ディレクトリ・glob・確認プロンプト）が動作する

---

## Phase 7: User Story 5 — agents サブコマンド (Priority: P3)

**Goal**: `8moku agents` でエージェント一覧を表示し、`8moku agents <name>` で詳細情報を確認する

**Independent Test**: `8moku agents` でビルトイン6エージェントが一覧表示され、`8moku agents code-reviewer` で詳細が表示される

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T031 [P] [US5] `tests/unit/cli/test_app.py` に agents サブコマンドの TDD テストを追加する（CliRunner 使用）。テストケース: 引数なしで一覧表示、カスタムエージェントの `[custom]` マーカー、エージェント名指定で詳細表示、存在しないエージェント名で終了コード 4
- [ ] T032 [US5] Red 確認: T031 のテストが失敗することを確認する

### Implementation for User Story 5

- [ ] T033 [US5] `src/hachimoku/cli/_app.py` の `agents` サブコマンドに一覧表示と詳細表示を実装する。`load_agents()` / `load_builtin_agents()` の呼び出し、テーブル形式出力、`[custom]` マーカー、エージェント名不一致時の終了コード 4
- [ ] T034 [US5] 品質チェック: `ruff check --fix . && ruff format . && mypy .`

**Checkpoint**: agents サブコマンドの全機能が動作する

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 全ストーリーにまたがる品質向上

- [ ] T035 [P] Edge Case テストを `tests/unit/cli/test_app.py` に追加する: PR 番号とファイルパスの同時指定エラー、`init`/`agents` と同名ファイルの扱い（`./init` でファイルモード判定）、`--format` 不正値、`--timeout` 不正値、`--issue` 不正値、Git リポジトリ外での diff モード実行→終了コード 4、Git リポジトリ外での PR モード実行→終了コード 4
- [ ] T036 [P] エラーメッセージの解決方法ヒントを全エラーパスで確認・改善する（FR-CLI-014 準拠）
- [ ] T037 最終品質チェック: `ruff check --fix . && ruff format . && mypy .` で全エラー解消を確認
- [ ] T038 quickstart.md の検証: quickstart.md の手順に従い一連の CLI 操作を実行して動作確認

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP の入口、入力モード判定
- **US2 (Phase 4)**: Depends on US1（`review_callback()` の骨格が必要）
- **US3 (Phase 5)**: Depends on Phase 2 only — US1/US2 とは独立して実装可能
- **US4 (Phase 6)**: Depends on US2（レビュー実行フローが必要）
- **US5 (Phase 7)**: Depends on Phase 2 only — US1-US4 とは独立して実装可能
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Phase 2 完了後に開始可能。他ストーリーへの依存なし
- **US2 (P1)**: US1 に依存（`_app.py` の `review_callback()` 骨格が必要）
- **US3 (P2)**: Phase 2 完了後に開始可能。**US1/US2 と並行実装可能**
- **US4 (P2)**: US2 に依存（レビュー実行フローへの file モード統合が必要）
- **US5 (P3)**: Phase 2 完了後に開始可能。**US1-US4 と並行実装可能**

### Within Each User Story

- テストを先に書き、失敗（Red）を確認する
- モデル/型定義 → ロジック実装 → アプリ統合 の順序
- 各ストーリー完了時に品質チェックを実施

### Parallel Opportunities

- **Phase 2**: T004 と T006 は異なるファイルへの並行作成は可能だが、TDD フロー（T004 → T005 → T006）を遵守する
- **Phase 3**: T009, T010 は並行可能（InputResolver テストと App テスト）
- **Phase 5 と Phase 3**: US3（init）は US1 完了を待たずに Phase 2 完了後から開始可能
- **Phase 7 と Phase 3-6**: US5（agents）は他ストーリーと独立して実装可能
- **Phase 8**: T035, T036 は並行可能

---

## Parallel Example: User Story 1

```bash
# テスト作成を並行実行:
Task: "T009 - InputResolver テスト in tests/unit/cli/test_input_resolver.py"
Task: "T010 - Typer app テスト in tests/unit/cli/test_app.py"

# Red 確認後、独立モジュールの実装:
Task: "T012 - InputResolver 実装 in src/hachimoku/cli/_input_resolver.py"
# T012 完了後:
Task: "T013 - Typer app 実装 in src/hachimoku/cli/_app.py"
```

## Parallel Example: US3 と US1 の並行実装

```bash
# Phase 2 完了後、US1 と US3 を並行開始:
Developer A: "T009-T015 (US1: 入力モード判定)"
Developer B: "T020-T024 (US3: init サブコマンド)"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Complete Phase 1: Setup（パッケージ構造 + pyproject.toml）
2. Complete Phase 2: Foundational（ExitCode + エントリポイント）
3. Complete Phase 3: User Story 1（入力モード判定）
4. Complete Phase 4: User Story 2（レビュー実行 + ストリーム分離）
5. **STOP and VALIDATE**: `8moku` / `hachimoku` で diff モード・PR モードのレビューが動作することを確認

### Incremental Delivery

1. Setup + Foundational → CLI エントリポイント確立
2. US1 → 入力モード判定が動作 → `8moku --help` が使える
3. US2 → レビュー実行が動作 → **MVP 完成**（diff + PR モード）
4. US3 → init サブコマンド追加 → カスタマイズの起点
5. US4 → file モード追加 → Git 管理外レビューが可能に
6. US5 → agents サブコマンド追加 → エージェント管理が可能に
7. Polish → Edge Case 対応・品質向上

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 1 + 2 together
2. Once Phase 2 is done:
   - Developer A: US1 → US2 → US4（メインフロー）
   - Developer B: US3（init、独立）→ US5（agents、独立）
3. Team together: Phase 8 Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD: テスト作成 → Red 確認 → 実装（Green）→ 品質チェック
- Typer の CliRunner でテスト、`typer.Exit(code=N)` で終了
- CLI パラメータ名 → config キー名の変換に注意（format→output_format, max_files→max_files_per_review）
- 品質チェック: `ruff check --fix . && ruff format . && mypy .`（各ストーリー完了時に必須）
