# Feature Specification: 設定管理

**Feature Branch**: `004-configuration`
**Created**: 2026-02-06
**Status**: Draft
**Input**: User description: "specs/README.mdと、親仕様specs/001-architecture-spec/spec.md を確認して 004-configuration を定義してください"
**Parent Spec**: [001-architecture-spec](../001-architecture-spec/spec.md)
**Priority**: P2（設定のカスタマイズ）
**Depends On**: [002-domain-models](../002-domain-models/spec.md)

## Clarifications

### Session 2026-02-06

- 親仕様 FR-010 および US5 を本仕様で実現する
- 親仕様 FR-012（CLAUDE.md 検出・注入）は本仕様のスコープ外とする。hachimoku のエージェントは内部的に `claude` CLI（Claude Code）を実行するため、CLAUDE.md はClaude Code の実行環境が自動的に読み込み・適用する。004-configuration での明示的な検出・注入は不要
- 設定ファイルフォーマットは TOML に統一（親仕様 Clarification Session の決定事項）
- 設定階層は5層: CLI > `.hachimoku/config.toml` > `pyproject.toml [tool.hachimoku]` > `~/.config/hachimoku/config.toml` > デフォルト
- `.hachimoku/config.toml` の探索はカレントディレクトリから親ディレクトリへ遡る（file モードの Git リポジトリ外実行に対応）
- 設定項目のうちエージェント個別設定（有効/無効、モデル上書き等）は `[agents.<name>]` セクションで管理する
- 設定モデル（HachimokuConfig）は 002-domain-models の HachimokuBaseModel を継承する
- 各設定項目には対応する CLI オプション名を定義する。006-cli-interface はこの対応表に基づいて CLI パーサーを構築する
- per-invocation オプション（`--issue`, `--force`, `--no-confirm`）は設定ファイルで永続化しない実行時パラメータであり、006-cli-interface の責務とする。本仕様のスコープ外
- FR-015（コスト表示）に対応する設定項目 `show_cost` を出力設定に追加する

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 設定ファイル階層による設定解決 (Priority: P1)

システムが5層の設定ソース（CLI オプション > プロジェクト設定ファイル > pyproject.toml > ユーザーグローバル設定 > デフォルト値）を階層的に解決し、最終的な設定を構築する。上位の設定ソースが下位を上書きし、未指定の項目はデフォルト値が適用される。

**Why this priority**: 設定の階層解決は全ての設定機能の基盤であり、この仕組みがなければ設定ファイルの読み込みやCLI オプションの反映が不可能。005-review-engine や 006-cli-interface が設定値に依存するため、最優先で実現する必要がある。

**Independent Test**: 複数の設定ソースに異なる値を配置し、設定リゾルバーが階層に従って正しい値を解決することで検証可能。

**Acceptance Scenarios**:

1. **Given** 設定ソースが何も存在しない状態, **When** 設定を解決する, **Then** 全項目がデフォルト値で構成された設定が返される
2. **Given** `.hachimoku/config.toml` に `base_branch = "develop"` が設定されている, **When** 設定を解決する, **Then** `base_branch` の値が `"develop"` に解決され、他の項目はデフォルト値が適用される
3. **Given** `.hachimoku/config.toml` と `pyproject.toml [tool.hachimoku]` の両方に `base_branch` が設定されている, **When** 設定を解決する, **Then** `.hachimoku/config.toml` の値が優先される
4. **Given** `~/.config/hachimoku/config.toml` にのみ設定がある状態, **When** 設定を解決する, **Then** ユーザーグローバル設定の値が適用される
5. **Given** CLI オプションで `--model sonnet` が指定され、`.hachimoku/config.toml` に `model = "opus"` が設定されている, **When** 設定を解決する, **Then** CLI オプションの `"sonnet"` が優先される
6. **Given** `pyproject.toml` に `[tool.hachimoku]` セクションが存在しない, **When** 設定を解決する, **Then** `pyproject.toml` の設定ソースはスキップされ、他のソースから解決される

---

### User Story 2 - プロジェクト設定ファイルの読み込みと検証 (Priority: P1)

システムが `.hachimoku/config.toml` を TOML 形式で読み込み、設定モデル（HachimokuConfig）として構築する。不正な設定値はバリデーションエラーとして検出される。

**Why this priority**: 設定ファイルの読み込みは階層解決（US1）の中核コンポーネントであり、設定をプロジェクトごとにカスタマイズするための必須機能。

**Independent Test**: 有効な設定ファイルと不正な設定ファイルを読み込み、バリデーションが正しく動作することで検証可能。

**Acceptance Scenarios**:

1. **Given** 有効な `.hachimoku/config.toml` が存在する, **When** 設定ファイルを読み込む, **Then** 全フィールドが正しくパースされ設定モデルが構築される
2. **Given** `.hachimoku/config.toml` に未知のキーが含まれる, **When** 設定ファイルを読み込む, **Then** バリデーションエラーが発生し、未知のキー名を含むエラーメッセージが生成される
3. **Given** `.hachimoku/config.toml` に型が不正な値（例: `timeout = "abc"`）が含まれる, **When** 設定ファイルを読み込む, **Then** バリデーションエラーが発生し、フィールド名と期待される型を含むエラーメッセージが生成される
4. **Given** `.hachimoku/config.toml` の TOML 構文が不正, **When** 設定ファイルを読み込む, **Then** パースエラーが発生し、ファイル名と具体的なエラー位置を含むメッセージが生成される
5. **Given** `.hachimoku/config.toml` が存在しない, **When** 設定を解決する, **Then** プロジェクト設定ソースはスキップされ、下位のソースから解決される（ファイル不在はエラーとしない）

---

### User Story 3 - エージェント個別設定によるレビュー動作制御 (Priority: P2)

開発者が設定ファイルで特定のエージェントを無効化したり、エージェント固有のモデルやタイムアウトを上書きする。エージェント個別設定は `[agents.<name>]` セクションで管理される。

**Why this priority**: エージェント個別設定はカスタマイズの重要な要素だが、まず設定ファイルの読み込みと階層解決（P1）が安定してから取り組む。

**Independent Test**: 設定ファイルでエージェントを無効化し、設定モデルの `agents` セクションに正しく反映されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 設定ファイルに `[agents.code-reviewer]` セクションで `enabled = false` が設定されている, **When** 設定を解決する, **Then** code-reviewer エージェントの設定が `enabled = false` として構成される
2. **Given** 設定ファイルに `[agents.code-reviewer]` セクションで `model = "haiku"` が設定されている, **When** 設定を解決する, **Then** code-reviewer エージェントのモデルが `"haiku"` に上書きされる
3. **Given** 設定ファイルに存在しないエージェント名のセクション `[agents.nonexistent]` がある, **When** 設定を読み込む, **Then** そのセクションは設定モデルに保持され、エージェント読み込み時に無視される（設定読み込み時点ではエラーとしない）

---

### User Story 4 - プロジェクト設定ディレクトリの探索 (Priority: P1)

システムがカレントディレクトリから親ディレクトリへ遡って `.hachimoku/` ディレクトリを探索し、プロジェクトルートを特定する。これにより、サブディレクトリからの実行時にもプロジェクト設定が正しく適用される。

**Why this priority**: ディレクトリ探索は設定ファイルの読み込み（US2）の前提であり、設定解決パイプラインの起点となる。

**Independent Test**: サブディレクトリからプロジェクト設定ディレクトリの探索を実行し、正しいプロジェクトルートが特定されることで検証可能。

**Acceptance Scenarios**:

1. **Given** カレントディレクトリに `.hachimoku/` が存在する, **When** プロジェクトルートを探索する, **Then** カレントディレクトリがプロジェクトルートとして返される
2. **Given** カレントディレクトリに `.hachimoku/` がなく親ディレクトリに存在する, **When** プロジェクトルートを探索する, **Then** 親ディレクトリがプロジェクトルートとして返される
3. **Given** ファイルシステムルートまで遡っても `.hachimoku/` が見つからない, **When** プロジェクトルートを探索する, **Then** プロジェクトルートなし（None）が返される（エラーとしない）

---

### Edge Cases

- `.hachimoku/config.toml` が空ファイルの場合、全項目がデフォルト値で構成された設定が返される
- `pyproject.toml` に `[tool.hachimoku]` セクションはあるが中身が空の場合、他のソースから解決される
- `~/.config/hachimoku/config.toml` のディレクトリが存在しない場合、ユーザーグローバル設定はスキップされる
- `.hachimoku/config.toml` の読み取り権限がない場合、明確なエラーメッセージとともにバリデーションエラーが報告される
- `timeout` に負の値が設定された場合、バリデーションエラーが発生する
- `max_files_per_review` に 0 以下の値が設定された場合、バリデーションエラーが発生する
- 設定ファイル内のエージェント個別設定でエージェント名の形式が不正（アルファベット小文字・数字・ハイフン以外を含む）な場合、バリデーションエラーが発生する
- 複数の設定ソースにエージェント個別設定がある場合、設定階層に従い上位のソースの値が優先される（項目単位でのマージ）
- `parallel` 設定が boolean 以外の値の場合、バリデーションエラーが発生する

## Requirements *(mandatory)*

### Functional Requirements

- **FR-CF-001**: システムは以下の5層の設定ソースを上位優先で階層的に解決し、最終的な設定モデル（HachimokuConfig）を構築できなければならない（親仕様 FR-010）:
  1. **CLI オプション**: コマンドライン引数で指定された値（最高優先）
  2. **プロジェクト設定**: `.hachimoku/config.toml`（カレントディレクトリから親方向に探索）
  3. **pyproject.toml**: `[tool.hachimoku]` セクション（カレントディレクトリから親方向に探索）
  4. **ユーザーグローバル設定**: `~/.config/hachimoku/config.toml`
  5. **デフォルト値**: コード内で定義されたデフォルト（最低優先）

  各設定ソースが存在しない場合はスキップされ、次のソースに進む。全設定フォーマットは TOML とする

- **FR-CF-002**: システムは以下の設定項目を管理しなければならない。各項目にはデフォルト値と対応する CLI オプション名が定義される。設定ファイルに記載がない場合はデフォルト値が適用される:

  **実行設定**:

  | 設定キー | CLI オプション | デフォルト | 型・制約 |
  |---------|--------------|----------|---------|
  | `model` | `--model` | `"sonnet"` | 文字列 |
  | `timeout` | `--timeout` | `300` | 正の整数 |
  | `max_turns` | `--max-turns` | `10` | 正の整数 |
  | `parallel` | `--parallel` | `false` | boolean |
  | `base_branch` | `--base-branch` | `"main"` | 文字列 |

  **出力設定**:

  | 設定キー | CLI オプション | デフォルト | 型・制約 |
  |---------|--------------|----------|---------|
  | `output_format` | `--format` | `"markdown"` | `"markdown"` \| `"json"` |
  | `save_reviews` | `--save-reviews` / `--no-save-reviews` | `true` | boolean |
  | `show_cost` | `--show-cost` / `--no-show-cost` | `false` | boolean |

  **ファイルモード設定**:

  | 設定キー | CLI オプション | デフォルト | 型・制約 |
  |---------|--------------|----------|---------|
  | `max_files_per_review` | `--max-files` | `100` | 正の整数 |

  **エージェント個別設定**（`[agents.<name>]` セクション、CLI からの上書き対象外）:
  - `enabled`: エージェントの有効/無効（デフォルト: `true`、boolean）
  - `model`: エージェント固有のモデル上書き（デフォルト: なし、グローバル `model` を使用）
  - `timeout`: エージェント固有のタイムアウト上書き（デフォルト: なし、グローバル `timeout` を使用）
  - `max_turns`: エージェント固有の最大ターン数上書き（デフォルト: なし、グローバル `max_turns` を使用）

  **per-invocation オプション（本仕様スコープ外、006-cli-interface で定義）**:
  - `--issue <番号>`: Issue コンテキスト注入（親仕様 FR-024）
  - `--force`: `init` コマンドでの強制上書き（親仕様 FR-028）
  - `--no-confirm`: file モードでの確認スキップ（親仕様 FR-032）

- **FR-CF-003**: システムは `.hachimoku/` ディレクトリをカレントディレクトリから親ディレクトリへ遡って探索し、プロジェクトルートを特定できなければならない。ファイルシステムルートまで遡っても見つからない場合は、プロジェクトルートなし（None）を返す

- **FR-CF-004**: システムは `.hachimoku/config.toml` を TOML 形式でパースし、HachimokuConfig モデルとしてバリデーションしなければならない。バリデーションは以下を検証する:
  - 未知のキーの拒否（厳格モード）
  - 各フィールドの型整合性
  - 数値制約（`timeout` > 0、`max_turns` > 0、`max_files_per_review` > 0）
  - `output_format` の列挙値（`"markdown"` または `"json"`）
  - エージェント個別設定のエージェント名形式（アルファベット小文字・数字・ハイフンのみ）

- **FR-CF-005**: システムは `pyproject.toml` の `[tool.hachimoku]` セクションを設定ソースとして読み込めなければならない。`pyproject.toml` はカレントディレクトリから親ディレクトリへ遡って探索する。`pyproject.toml` が存在しない場合、または `[tool.hachimoku]` セクションが存在しない場合はスキップする

- **FR-CF-006**: システムは `~/.config/hachimoku/config.toml` をユーザーグローバル設定として読み込めなければならない。ファイルまたはディレクトリが存在しない場合はスキップする

- **FR-CF-007**: 設定の階層解決は項目単位で行われなければならない。上位ソースで明示的に設定された項目のみが下位ソースの値を上書きし、上位ソースに記載のない項目は下位ソースの値が維持される

- **FR-CF-008**: エージェント個別設定の解決において、エージェント固有の値が未設定の場合はグローバル設定値が適用されなければならない。例: エージェント固有の `model` が未設定の場合、グローバルの `model` 値を使用する

- **FR-CF-009**: 設定モデル（HachimokuConfig）は HachimokuBaseModel を継承し、`extra="forbid"`（未知フィールド拒否）および `frozen=True`（不変性）の制約を持たなければならない

### Key Entities

- **HachimokuConfig（設定モデル）**: 全設定項目を統合した不変モデル。実行設定（model, timeout, max_turns, parallel, base_branch）、出力設定（output_format, save_reviews, show_cost）、ファイルモード設定（max_files_per_review）、エージェント個別設定（agents マップ）を持つ。HachimokuBaseModel を継承し、厳格モード・不変モードで動作する
- **AgentConfig（エージェント個別設定）**: エージェントごとの設定上書き情報を表す不変モデル。有効/無効フラグ（enabled）、モデル上書き（model）、タイムアウト上書き（timeout）、最大ターン数上書き（max_turns）を持つ。全フィールドはオプショナルで、未設定の場合はグローバル値が適用される
- **OutputFormat（出力形式）**: レビュー結果の出力形式を表す列挙型。markdown と json の2値
- **ConfigResolver（設定リゾルバー）**: 5層の設定ソースから最終的な HachimokuConfig を構築する処理。各ソースの読み込み・パース・バリデーションと、項目単位のマージロジックを提供する
- **ProjectLocator（プロジェクト探索）**: カレントディレクトリから `.hachimoku/` ディレクトリを探索し、プロジェクトルートを特定する処理。設定ファイル読み込みの起点として機能する

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-CF-001**: 5層の設定ソースが正しい優先順位で解決され、上位の設定が下位を確実に上書きする（親仕様 SC-008 の実現）
- **SC-CF-002**: 設定ファイルが存在しない状態でも、デフォルト値のみで有効な設定モデルが構築される
- **SC-CF-003**: `.hachimoku/config.toml` に不正な値が含まれる場合、具体的なフィールド名と期待される型を含むエラーメッセージが生成される
- **SC-CF-004**: プロジェクトのサブディレクトリからの実行時にも `.hachimoku/` が正しく検出され、設定が適用される
- **SC-CF-005**: エージェント個別設定で `enabled = false` と設定されたエージェントが、設定モデル上で無効として表現される
- **SC-CF-006**: `pyproject.toml` の `[tool.hachimoku]` セクションの値が `.hachimoku/config.toml` より低い優先度で正しく解決される

## Assumptions

- 設定ファイルの TOML パースには Python 標準ライブラリ `tomllib`（Python 3.11+）を使用する。外部ライブラリの追加は不要
- ユーザーグローバル設定のパスは `~/.config/hachimoku/config.toml` に固定する。XDG_CONFIG_HOME 環境変数への対応は将来の拡張とする
- CLI オプションの値は 006-cli-interface から辞書形式で渡される想定。本仕様では CLI のパース自体は扱わず、設定項目と CLI オプション名の対応表（FR-CF-002）を提供する。006-cli-interface はこの対応表に基づいてパーサーを構築する
- per-invocation オプション（`--issue`, `--force`, `--no-confirm`）は設定ファイルに永続化しない実行時パラメータであり、006-cli-interface の責務とする。本仕様のスコープ外
- 設定モデルの `model` フィールドの値は文字列として保持し、実際のモデル解決（存在確認等）は 005-review-engine が担当する
- エージェント個別設定のエージェント名は、003-agent-definition で定義されたエージェント名と一致する必要があるが、その検証は設定読み込み時点では行わない（エージェントローダーとの統合時に検証）
