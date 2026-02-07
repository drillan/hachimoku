# Tasks: レビュー実行エンジン

**Input**: Design documents from `/specs/005-review-engine/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: TDD で実装する（CLAUDE.md Art.1 準拠）。テストを先に作成し、Red 確認後に実装する。

**Organization**: タスクはユーザーストーリー単位でグループ化し、独立した実装・テストを可能にする。ただし P1 ストーリー間には依存関係があるため、US5 → US6 → US1 → US2 の順で実装する。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 並列実行可能（異なるファイル、依存なし）
- **[Story]**: 対応するユーザーストーリー（US1, US2, US3 等）
- 各タスクに正確なファイルパスを記載

## Path Conventions

- **Source**: `src/hachimoku/engine/`
- **Tests**: `tests/unit/engine/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: engine パッケージの初期構造と依存関係の追加

- [ ] T001 pydantic-ai と pytest-asyncio の依存関係を追加する（`uv add pydantic-ai` / `uv add --dev pytest-asyncio`）
- [ ] T002 engine パッケージディレクトリ構造を作成する（`src/hachimoku/engine/__init__.py`, `src/hachimoku/engine/_tools/__init__.py`, `tests/unit/engine/__init__.py`）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全ユーザーストーリーが依存する基盤モデル・ユーティリティの実装

**WARNING**: このフェーズが完了するまでユーザーストーリーの実装に着手しないこと

- [ ] T003 [P] ReviewTarget 判別共用体のテストを作成する（`tests/unit/engine/test_target.py`）: DiffTarget / PRTarget / FileTarget の生成・バリデーション・issue_number オプション・discriminator による型判別を検証
- [ ] T004 [P] ToolCatalog のテストを作成する（`tests/unit/engine/test_catalog.py`）: resolve_tools() によるカテゴリ→ツール解決、validate_categories() による不正カテゴリ検出、空カテゴリ・重複カテゴリの処理を検証
- [ ] T005 [P] ReviewInstructionBuilder のテストを作成する（`tests/unit/engine/test_instruction.py`）: build_review_instruction() の diff/PR/file 各モード出力、issue_number 付加、build_selector_instruction() のエージェント定義一覧含有を検証
- [ ] T006 [P] ProgressReporter のテストを作成する（`tests/unit/engine/test_progress.py`）: report_agent_start/report_agent_complete/report_summary/report_load_warnings/report_selector_result の stderr 出力フォーマットを検証
- [ ] T007 [P] ReviewReport の load_errors フィールド追加テストを作成する（`tests/unit/models/test_report.py` に追加）: load_errors のデフォルト値（空タプル）、LoadError タプルの設定・取得を検証
- [ ] T008 ReviewTarget 判別共用体を実装する（`src/hachimoku/engine/_target.py`）: DiffTarget / PRTarget / FileTarget の Pydantic モデルと ReviewTarget Union 型を定義（contracts/review_target.py 準拠）
- [ ] T009 ToolCatalog を実装する（`src/hachimoku/engine/_catalog.py`）: resolve_tools() / validate_categories() 関数とカテゴリ→ツールマッピング辞書を定義（contracts/tool_catalog.py 準拠）
- [ ] T010 ツール関数を実装する（`src/hachimoku/engine/_tools/_git.py`, `src/hachimoku/engine/_tools/_gh.py`, `src/hachimoku/engine/_tools/_file.py`）: git_read（run_git）/ gh_read（run_gh）/ file_read（read_file, list_directory）のツール関数を定義。ホワイトリスト検証を含む（research.md R-005 準拠）
- [ ] T011 [P] ツール関数のテストを作成する（`tests/unit/engine/test_tools.py`）: run_git / run_gh / read_file / list_directory の正常系・ホワイトリスト違反・コマンドエラーを検証
- [ ] T012 ReviewInstructionBuilder を実装する（`src/hachimoku/engine/_instruction.py`）: build_review_instruction() / build_selector_instruction() を定義（contracts/instruction_builder.py 準拠）
- [ ] T013 ProgressReporter を実装する（`src/hachimoku/engine/_progress.py`）: 全 report_* 関数を定義し stderr に出力（contracts/progress_reporter.py 準拠）
- [ ] T014 ReviewReport に load_errors フィールドを追加する（`src/hachimoku/models/report.py`）: `load_errors: tuple[LoadError, ...] = ()` フィールドを追加（data-model.md / research.md R-009 準拠）

**Checkpoint**: 基盤モジュール（ReviewTarget, ToolCatalog, InstructionBuilder, ProgressReporter）が全て動作し、テストが Green であること

---

## Phase 3: User Story 5 - レビュー対象の取得と入力モード判別 (Priority: P1)

**Goal**: 入力モード（diff / PR / file）に応じてレビュー指示情報を構築し、エージェントのプロンプトコンテキストとして提供する

**Independent Test**: 各入力モード（diff / file / PR）でレビュー指示が正しく構築され、エージェントのプロンプトコンテキストに含まれることで検証可能

> Phase 2 で ReviewTarget / ReviewInstructionBuilder のテスト・実装が完了しているため、このフェーズでは **統合的な検証** と **エッジケース対応** を行う

### Implementation for User Story 5

- [ ] T015 [US5] ReviewTarget のエッジケーステストを追加する（`tests/unit/engine/test_target.py` に追加）: base_branch 空文字、pr_number が 0 以下、paths が空タプルのバリデーションエラーを検証
- [ ] T016 [US5] ReviewInstructionBuilder のエッジケーステストを追加する（`tests/unit/engine/test_instruction.py` に追加）: glob パターン指定の file モード、ディレクトリ指定の file モード、issue_number 有無の組み合わせを検証
- [ ] T017 [US5] エッジケースの実装を反映する（`src/hachimoku/engine/_target.py`, `src/hachimoku/engine/_instruction.py`）: テストを Green にする

**Checkpoint**: 全入力モード（diff / PR / file）でレビュー指示が正しく構築され、エッジケースも網羅されていること

---

## Phase 4: User Story 6 - エージェント実行コンテキストの構築 (Priority: P1)

**Goal**: エージェント定義・設定・レビュー対象・オプションの情報を統合し、各エージェントの実行コンテキスト（モデル・ツール・プロンプト・タイムアウト・最大ターン数）を構築する

**Independent Test**: エージェント定義と設定から実行コンテキストを構築し、各フィールドが正しく設定されることで検証可能

### Tests for User Story 6

- [ ] T018 [US6] AgentExecutionContext 構築のテストを作成する（`tests/unit/engine/test_context.py`）: build_execution_context() のモデル名解決（個別設定 > グローバル > デフォルト）、タイムアウト解決、最大ターン数解決、出力スキーマ解決、ツール設定、issue_number 付加を検証

### Implementation for User Story 6

- [ ] T019 [US6] AgentExecutionContext モデルと build_execution_context() を実装する（`src/hachimoku/engine/_context.py`）: 設定値の優先順解決ロジックを含む（contracts/execution_context.py 準拠）

**Checkpoint**: エージェント定義と設定から実行コンテキストが正しく構築され、全設定値の優先順解決が動作すること

---

## Phase 5: User Story 1 - 逐次実行によるマルチエージェントレビュー (Priority: P1) MVP

**Goal**: 設定とエージェント定義に基づいてレビュー対象を取得し、適用可能なエージェントを逐次実行して結果を ReviewReport に集約する

**Independent Test**: テスト用エージェント定義と差分データをエンジンに渡し、各エージェントがフェーズ順に逐次実行され、ReviewReport が生成されることで検証可能

### Tests for User Story 1

- [ ] T020 [P] [US1] AgentRunner のテストを作成する（`tests/unit/engine/test_runner.py`）: pydantic-ai TestModel を使用し、正常完了→AgentSuccess、出力スキーマ設定、ツール設定、モデル設定を検証
- [ ] T021 [P] [US1] SelectorAgent のテストを作成する（`tests/unit/engine/test_selector.py`）: pydantic-ai TestModel を使用し、SelectorOutput の構造化出力取得、空リスト返却、選択理由の記録を検証
- [ ] T022 [US1] SequentialExecutor のテストを作成する（`tests/unit/engine/test_executor.py`）: フェーズ順（early → main → final）・同フェーズ内名前辞書順の逐次実行、group_by_phase() のフェーズグルーピングを検証

### Implementation for User Story 1

- [ ] T023 [US1] AgentRunner を実装する（`src/hachimoku/engine/_runner.py`）: pydantic-ai Agent 構築、agent.run() 実行、結果の AgentResult 変換を実装（contracts/agent_runner.py 準拠）
- [ ] T024 [US1] SelectorAgent を実装する（`src/hachimoku/engine/_selector.py`）: SelectorOutput モデル定義、run_selector() 関数、pydantic-ai Agent(output_type=SelectorOutput) による構造化出力を実装（contracts/selector_agent.py 準拠）
- [ ] T025 [US1] SequentialExecutor を実装する（`src/hachimoku/engine/_executor.py`）: execute_sequential() / group_by_phase() を実装（contracts/executors.py 準拠）
- [ ] T026 [US1] ReviewEngine 統合テストを作成する（`tests/unit/engine/test_engine.py`）: パイプライン全体（設定解決→エージェント読み込み→選択→逐次実行→結果集約）を TestModel でエンドツーエンド検証。EngineResult の report / exit_code を検証
- [ ] T027 [US1] ReviewEngine を実装する（`src/hachimoku/engine/_engine.py`）: run_review() 関数でパイプライン全体を統合。EngineResult（ReviewReport + exit_code）を生成（contracts/review_engine.py 準拠）
- [ ] T028 [US1] engine パッケージの公開 API を定義する（`src/hachimoku/engine/__init__.py`）: ReviewEngine, ReviewTarget（DiffTarget, PRTarget, FileTarget）, EngineResult をエクスポート

**Checkpoint**: 逐次実行モードでマルチエージェントレビューが動作し、ReviewReport が正しく生成されること。これが **MVP** である

---

## Phase 6: User Story 2 - 個別エージェントの失敗許容と部分レポート生成 (Priority: P1)

**Goal**: 個別エージェントがタイムアウト・実行エラー・出力スキーマ違反で失敗しても、成功したエージェントの結果のみでレビューレポートを生成する

**Independent Test**: 意図的にタイムアウトやエラーを発生させるテスト用エージェントを含めてレビューを実行し、成功したエージェントのみの結果でレポートが生成されることで検証可能

### Tests for User Story 2

- [ ] T029 [P] [US2] AgentRunner のエラーハンドリングテストを追加する（`tests/unit/engine/test_runner.py` に追加）: asyncio.TimeoutError→AgentTimeout、UsageLimitExceeded→AgentTruncated、その他例外→AgentError、出力スキーマ違反→AgentError を検証
- [ ] T030 [P] [US2] SequentialExecutor の部分失敗テストを追加する（`tests/unit/engine/test_executor.py` に追加）: 3エージェント中1つがタイムアウト/エラーでも残り2つの結果が返ること、全エージェント失敗時の空成功リストを検証

### Implementation for User Story 2

- [ ] T031 [US2] AgentRunner にタイムアウト制御（asyncio.timeout）とターン数制御（UsageLimits）を実装する（`src/hachimoku/engine/_runner.py` に追加）: asyncio.TimeoutError / UsageLimitExceeded / その他例外のキャッチと AgentResult 変換（research.md R-001, R-002, R-003 準拠）
- [ ] T032 [US2] ReviewEngine に全エージェント失敗時の exit_code=3 判定を実装する（`src/hachimoku/engine/_engine.py` に追加）: AgentSuccess + AgentTruncated が 0 件の場合に exit_code=3 を返す（FR-RE-009）
- [ ] T033 [US2] ReviewEngine の全エージェント失敗テストを追加する（`tests/unit/engine/test_engine.py` に追加）: 全エージェント失敗→exit_code=3、1つ以上成功→Severity マッピングに基づく exit_code を検証

**Checkpoint**: エージェント個別の失敗が他のエージェントに影響せず、部分レポートが正しく生成されること

---

## Phase 7: User Story 3 - 並列実行によるレビュー高速化 (Priority: P2)

**Goal**: 同一フェーズ内のエージェントを並列実行し、フェーズ間は順序を保持する

**Independent Test**: 並列オプション付きでレビューを実行し、同一フェーズ内のエージェントが並行して実行され、全体の所要時間が逐次実行より短いことで検証可能

### Tests for User Story 3

- [ ] T034 [US3] ParallelExecutor のテストを作成する（`tests/unit/engine/test_executor.py` に追加）: 同一フェーズ内の並列実行、フェーズ間の順序保持（early → main → final）、並列実行中の個別エージェント失敗許容を検証

### Implementation for User Story 3

- [ ] T035 [US3] ParallelExecutor を実装する（`src/hachimoku/engine/_executor.py` に追加）: execute_parallel() を asyncio.TaskGroup で実装。フェーズ間は逐次、同一フェーズ内は並列実行（contracts/executors.py / research.md R-007 準拠）
- [ ] T036 [US3] ReviewEngine に parallel 設定の切り替えを実装する（`src/hachimoku/engine/_engine.py` に追加）: HachimokuConfig.parallel に基づき execute_sequential / execute_parallel を切り替え
- [ ] T037 [US3] ReviewEngine の並列実行テストを追加する（`tests/unit/engine/test_engine.py` に追加）: parallel=true / parallel=false の切り替え動作を検証

**Checkpoint**: 並列実行モードで同一フェーズ内のエージェントが並行実行され、フェーズ間の順序が保持されること

---

## Phase 8: User Story 4 - SIGINT/SIGTERM によるグレースフルシャットダウン (Priority: P2)

**Goal**: SIGINT/SIGTERM 受信時に実行中エージェントを安全に停止し、完了済み結果で部分レポートを生成する

**Independent Test**: レビュー実行中に SIGINT を送信し、完了済みエージェントの結果が部分レポートとして出力されることで検証可能

### Tests for User Story 4

- [ ] T038 [P] [US4] SignalHandler のテストを作成する（`tests/unit/engine/test_signal.py`）: install_signal_handlers() による SIGINT/SIGTERM ハンドラ登録、シグナル受信時の shutdown_event セット、uninstall_signal_handlers() によるクリーンアップを検証
- [ ] T039 [P] [US4] Executor のシャットダウンテストを追加する（`tests/unit/engine/test_executor.py` に追加）: 逐次実行中の shutdown_event チェック（残りスキップ）、並列実行中の TaskGroup キャンセル伝播を検証

### Implementation for User Story 4

- [ ] T040 [US4] SignalHandler を実装する（`src/hachimoku/engine/_signal.py`）: install_signal_handlers() / uninstall_signal_handlers() を実装（contracts/signal_handler.py / research.md R-008 準拠）
- [ ] T041 [US4] Executor に shutdown_event チェックを統合する（`src/hachimoku/engine/_executor.py` に追加）: 逐次実行の各エージェント前チェック、並列実行の TaskGroup キャンセル伝播
- [ ] T042 [US4] ReviewEngine に SignalHandler の install/uninstall を統合する（`src/hachimoku/engine/_engine.py` に追加）: run_review() の開始時に install、完了/エラー時に uninstall

**Checkpoint**: SIGINT/SIGTERM 受信時にグレースフルシャットダウンが動作し、完了済みエージェントの結果が部分レポートとして出力されること

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 全ユーザーストーリーにまたがる改善と最終検証

- [ ] T043 [P] engine パッケージの public モジュール・クラス・関数に Google-style docstring を追加する（`src/hachimoku/engine/` 全体）
- [ ] T044 全テスト・品質チェックの最終実行（`uv --directory $PROJECT_ROOT run ruff check --fix . && ruff format . && mypy . && pytest`）
- [ ] T045 quickstart.md の手順に沿った検証を実施する（`specs/005-review-engine/quickstart.md`）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 依存なし - 即座に開始可能
- **Foundational (Phase 2)**: Phase 1 完了に依存 - 全ユーザーストーリーをブロック
- **US5 (Phase 3)**: Phase 2 完了に依存（ReviewTarget / InstructionBuilder の基盤テスト・実装が完了していること）
- **US6 (Phase 4)**: Phase 2 完了に依存。US5 のエッジケース反映（T017）とは独立して開始可能
- **US1 (Phase 5)**: Phase 2, 4 完了に依存（AgentExecutionContext が必要）。US5 完了も推奨
- **US2 (Phase 6)**: Phase 5（US1）完了に依存（AgentRunner / ReviewEngine の基本実装が必要）
- **US3 (Phase 7)**: Phase 5（US1）完了に依存（SequentialExecutor が基盤）。US2 とは独立して開始可能
- **US4 (Phase 8)**: Phase 5（US1）完了に依存（Executor が基盤）。US2/US3 とは独立して開始可能
- **Polish (Phase 9)**: 全ユーザーストーリー完了に依存

### User Story Dependencies

- **US5 (P1)**: Phase 2 完了後に開始可能 - 他ストーリーへの依存なし
- **US6 (P1)**: Phase 2 完了後に開始可能 - US5 のエッジケースとは独立
- **US1 (P1)**: US6（AgentExecutionContext）完了が必須 - MVP の核
- **US2 (P1)**: US1（基本的な AgentRunner / ReviewEngine）完了が必須
- **US3 (P2)**: US1 完了後に開始可能 - US2 とは独立
- **US4 (P2)**: US1 完了後に開始可能 - US2/US3 とは独立

### Within Each User Story

- テストを先に作成し、Red 確認後に実装（TDD）
- モデル → サービス → 統合の順で実装
- ストーリー完了後にチェックポイントで独立検証

### Parallel Opportunities

- Phase 2: T003, T004, T005, T006, T007 のテスト作成は全て並列実行可能
- Phase 2: T011（ツール関数テスト）は T010 と並列可能
- Phase 5: T020, T021 のテスト作成は並列実行可能
- Phase 6: T029, T030 のテスト作成は並列実行可能
- Phase 8: T038, T039 のテスト作成は並列実行可能
- US3 と US4 は US1 完了後に並列で開始可能

---

## Parallel Example: Phase 2 (Foundational)

```bash
# 全基盤テストを並列で作成:
Task: "ReviewTarget テスト作成 in tests/unit/engine/test_target.py" (T003)
Task: "ToolCatalog テスト作成 in tests/unit/engine/test_catalog.py" (T004)
Task: "InstructionBuilder テスト作成 in tests/unit/engine/test_instruction.py" (T005)
Task: "ProgressReporter テスト作成 in tests/unit/engine/test_progress.py" (T006)
Task: "ReviewReport load_errors テスト作成 in tests/unit/models/test_report.py" (T007)
Task: "ツール関数テスト作成 in tests/unit/engine/test_tools.py" (T011)
```

## Parallel Example: US3 + US4 (after US1)

```bash
# US3 と US4 を同時に開始:
Task: "ParallelExecutor テスト作成 in tests/unit/engine/test_executor.py" (T034)
Task: "SignalHandler テスト作成 in tests/unit/engine/test_signal.py" (T038)
Task: "Executor シャットダウンテスト in tests/unit/engine/test_executor.py" (T039)
```

---

## Implementation Strategy

### MVP First (US5 + US6 + US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational（CRITICAL - 全ストーリーをブロック）
3. Complete Phase 3: US5（レビュー対象の取得と入力モード判別）
4. Complete Phase 4: US6（実行コンテキスト構築）
5. Complete Phase 5: US1（逐次実行によるマルチエージェントレビュー）
6. **STOP and VALIDATE**: 逐次実行モードでエンドツーエンドのレビューが動作すること

### Incremental Delivery

1. Setup + Foundational → 基盤完了
2. US5 + US6 → コンテキスト構築完了
3. **US1 → 逐次実行レビュー動作 → MVP!**
4. US2 → 失敗許容・部分レポート対応
5. US3 → 並列実行による高速化
6. US4 → グレースフルシャットダウン
7. Polish → docstring・最終検証

### Parallel Team Strategy

1. チーム全員で Setup + Foundational を完了
2. Foundational 完了後:
   - Developer A: US5 → US6 → US1（MVP パス）
   - Developer B: US5 完了後に US1 のテスト作成を先行
3. US1 完了後:
   - Developer A: US2（失敗許容）
   - Developer B: US3（並列実行）
   - Developer C: US4（シグナルハンドリング）

---

## Notes

- [P] タスク = 異なるファイル、依存なし
- [Story] ラベルはユーザーストーリーへのトレーサビリティを提供
- 各ユーザーストーリーは独立して完了・テスト可能
- テスト作成後に必ず Red（失敗）を確認してから実装に移る
- 各タスクまたは論理グループの完了後にコミット
- チェックポイントで独立的にストーリーを検証
- 品質チェック: `ruff check --fix . && ruff format . && mypy .` を各 Step 完了後に実行
