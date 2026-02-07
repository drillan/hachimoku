# Feature Specification: CLI インターフェース・初期化

**Feature Branch**: `docs/006-cli-interface`
**Created**: 2026-02-07
**Status**: Draft
**Input**: User description: "specs/README.mdをもとに、specs/001-architecture-spec/spec.mdを親仕様とした006-cli-interfaceを定義してください"
**Parent Spec**: [001-architecture-spec](../001-architecture-spec/spec.md)
**Priority**: P1-P3（P1: 基本 CLI・レビュー実行、P2: init・file モード、P3: agents 管理コマンド）
**Depends On**: [005-review-engine](../005-review-engine/spec.md)

## Clarifications

### Session 2026-02-07

- 親仕様 FR-008（CLI 部分: 出力形式選択）、FR-009、FR-016、FR-017、FR-018（CLI 部分: ストリーム分離の最上位制御）、FR-021、FR-024（CLI 部分: `--issue` オプションの提供。Issue 詳細取得は 008-github-integration の担当）、FR-027、FR-028、FR-029、FR-031、FR-032 および US7、US8、US9（CLI 部分）を本仕様で実現する
- README.md の依存関係に基づき、005-review-engine に依存する。005 を通じて 002（ドメインモデル）、003（エージェント定義）、004（設定）を間接的に利用する
- CLI フレームワークとして Typer を採用する（CLAUDE.md の Tech Stack に記載）。Typer のサブコマンド機構を直接使用し、不必要なラッパーは作成しない
- FR-008（Markdown/JSON 出力）は 006 と 007 の共同実現: 006 は `--format` CLI オプションの提供と出力形式の選択を担当し、007 は実際のフォーマッティング処理を担当する
- FR-018（stdout/stderr 分離）は 006 と 005 の共同実現: 006 はレビューレポートの stdout 出力を担当し、005 は実行中の進捗情報の stderr 出力を担当する（FR-RE-015）
- 004-configuration の FR-CF-002 で定義された CLI オプション名の対応表に基づいて CLI パーサーを構築する。設定値の解決自体は 004 の ConfigResolver に委譲する
- per-invocation オプション（`--issue`、`--force`、`--no-confirm`）は設定ファイルに永続化しない実行時パラメータであり、本仕様のスコープ内で定義する（004-configuration Assumptions で明記）
- 親仕様 FR-021 のサブコマンド文字列に `config` が含まれるが、v0.1 では `init` と `agents` のみ実装する。`config` は Typer に予約サブコマンドとして登録し、実行時は未実装エラー（終了コード 4）を返す
- デュアルコマンド名（`8moku` / `hachimoku`）は `pyproject.toml` の `[project.scripts]` に2つのエントリポイントを登録することで実現する。両エントリポイントは同一の Typer app インスタンスを参照する
- `8moku init` は Git リポジトリ内でのみ動作する（親仕様 US8 Acceptance Scenario 4）。Git リポジトリの判定は `.git` ディレクトリの存在確認で行う
- 終了コードの決定: 入力エラー（終了コード 4）は 006 が直接判定する（引数パース失敗・ファイル未発見等）。実行エラー（終了コード 3）と重大度ベースの終了コード（0/1/2）は 005-review-engine の ReviewReport から決定する
- `8moku agents` の一覧表示は stdout に出力する（レビューレポートではないため stderr 分離ルールの対象外）。`agents` コマンドは `--format` オプションをサポートしない（人間向け表示のみ）
- Typer のサブコマンド機構により、`init` や `agents` という文字列が自動的にサブコマンドとして認識される。ファイル名が `init` や `agents` と同名の場合、file モードとして扱うには `./init` のようにパスセパレータを含めて指定する

## User Scenarios & Testing *(mandatory)*

### User Story 1 - デュアルコマンド名と入力モード判定 (Priority: P1)

システムが `8moku` と `hachimoku` の両方のコマンド名で同一機能を提供し、位置引数からレビューモード（diff / PR / file）またはサブコマンド（init / agents）を自動判定する。

**Why this priority**: CLI エントリポイントは全機能の入口であり、この機能なしにはユーザーがツールを利用できない。モード判定のルールが正しく動作しなければ、意図しないレビューが実行される。

**Independent Test**: `8moku` と `hachimoku` の両方のコマンドで同一の引数を渡し、同じモード判定結果が得られることで検証可能。

**Acceptance Scenarios**:

1. **Given** ツールがインストールされた状態, **When** `8moku --help` を実行, **Then** コマンドのヘルプ情報が表示される。`hachimoku --help` でも同一の内容が表示される
2. **Given** 引数なしで実行する状態, **When** `8moku` を実行, **Then** diff モードとして判定される
3. **Given** 整数のみの位置引数を指定する状態, **When** `8moku 123` を実行, **Then** PR モード（PR #123）として判定される
4. **Given** パスセパレータを含む位置引数を指定する状態, **When** `8moku src/auth.py` を実行, **Then** file モードとして判定される
5. **Given** glob パターンを含む位置引数を指定する状態, **When** `8moku "src/**/*.py"` を実行, **Then** file モードとして判定される
6. **Given** ファイルシステム上に存在するファイル名を指定する状態, **When** `8moku Makefile` を実行（`Makefile` が存在する場合）, **Then** file モードとして判定される
7. **Given** サブコマンドでもファイルでもない文字列を指定する状態, **When** `8moku unknown_string` を実行（ファイルシステム上に存在しない場合）, **Then** エラーメッセージが表示され終了コード 4 で終了する
8. **Given** 複数の位置引数を指定する状態, **When** `8moku src/auth.py src/api/client.py` を実行, **Then** file モードとして判定され、両方のファイルがレビュー対象となる

---

### User Story 2 - レビュー実行とストリーム分離・終了コード (Priority: P1)

CLI がレビュー実行を 005-review-engine に委譲し、結果を stdout に出力する。進捗情報は stderr に出力される。レビュー結果の重大度に応じた終了コードが返される。

**Why this priority**: レビュー結果の出力と終了コードはツールの根幹的な価値提供であり、CI/CD 統合やパイプ利用の前提となる。

**Independent Test**: レビューを実行し、stdout にはレビューレポートのみ、stderr には進捗情報のみが出力され、適切な終了コードが返されることで検証可能。

**Acceptance Scenarios**:

1. **Given** レビュー結果に Critical 問題が含まれる状態, **When** レビューが完了する, **Then** 終了コード 1 が返される
2. **Given** レビュー結果に Important 問題のみ含まれる状態（Critical なし）, **When** レビューが完了する, **Then** 終了コード 2 が返される
3. **Given** レビュー結果に問題がない状態, **When** レビューが完了する, **Then** 終了コード 0 が返される
4. **Given** 全エージェントが実行失敗した状態, **When** レビューが完了する, **Then** 終了コード 3 が返される
5. **Given** `8moku > result.md` のようにリダイレクトする状態, **When** レビューが完了する, **Then** `result.md` にはレビューレポートのみが含まれ、進捗情報は含まれない
6. **Given** CLI オプション `--model sonnet --timeout 600` を指定する状態, **When** レビューを実行する, **Then** CLI オプションの値が設定階層の最高優先として適用される
7. **Given** `--format json` を指定する状態, **When** レビューが完了する, **Then** JSON 形式のレビューレポートが stdout に出力される
8. **Given** diff モードで `--issue 122` を指定する状態, **When** `8moku --issue 122` を実行, **Then** diff レビューに Issue #122 のコンテキストが含まれる
9. **Given** PR モードで `--issue 50` を指定する状態, **When** `8moku 123 --issue 50` を実行, **Then** PR #123 のレビューに Issue #50 のコンテキストが含まれる
10. **Given** `--show-cost` を指定する状態, **When** レビューが完了する, **Then** コスト情報が stdout のレビューレポートに含まれる（007-output-format がフォーマッティングを担当）

---

### User Story 3 - init サブコマンド (Priority: P2)

開発者が `8moku init` を実行して `.hachimoku/` ディレクトリを作成し、デフォルトの設定ファイル・エージェント定義ファイル・レビュー蓄積ディレクトリを生成する。

**Why this priority**: 初期セットアップはカスタマイズの起点であり、ユーザーの最初の体験に直結する。ただし init なしでもビルトインエージェントとデフォルト設定で動作するため、基本レビュー実行（P1）より後に実装する。

**Independent Test**: `8moku init` を実行し、`.hachimoku/` 配下に設定ファイル・エージェント定義・レビューディレクトリが生成されることで検証可能。

**Acceptance Scenarios**:

1. **Given** `.hachimoku/` ディレクトリが存在しない Git リポジトリ内, **When** `8moku init` を実行, **Then** 以下が生成される:
   - `.hachimoku/config.toml`（コメント付きデフォルト設定）
   - `.hachimoku/agents/` にビルトイン6エージェントの定義ファイル
   - `.hachimoku/reviews/` ディレクトリ
2. **Given** `.hachimoku/` ディレクトリが既に存在し一部ファイルがカスタマイズ済み, **When** `8moku init` を実行, **Then** 既存ファイルはスキップされ、不足ファイルのみが追加生成される。スキップされたファイルの情報が stderr に表示される
3. **Given** `.hachimoku/` ディレクトリが既に存在する, **When** `8moku init --force` を実行, **Then** 全ファイルがデフォルト内容で上書きされる
4. **Given** Git リポジトリ外で実行する, **When** `8moku init` を実行, **Then** Git リポジトリ内でのみ実行可能である旨のエラーメッセージが表示され、終了コード 4 で終了する
5. **Given** 正常に init が完了した状態, **When** 生成された `config.toml` を確認する, **Then** 全設定項目がコメントとして記載されており、ユーザーが設定可能な項目を理解できる

---

### User Story 4 - file モードの入力解決と確認 (Priority: P2)

CLI が file モードの位置引数（ファイル・ディレクトリ・glob パターン）を解決し、設定項目 `max_files_per_review` を超過する場合にユーザーに確認を求める。

**Why this priority**: file モードは diff/PR モードの自然な拡張であり、Git 管理外のドキュメントレビューという新しいユースケースを開拓する。ただし基本的なレビュー実行（P1）が動作してから取り組む。

**Independent Test**: 各種入力形式（単一ファイル・複数ファイル・ディレクトリ・glob パターン）でファイルパスが正しく解決され、`max_files_per_review` 超過時に確認プロンプトが表示されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 単一ファイルパスを指定する状態, **When** `8moku src/auth.py` を実行, **Then** 指定ファイルがレビュー対象として 005-review-engine に渡される
2. **Given** ディレクトリを指定する状態, **When** `8moku src/` を実行, **Then** `src/` 配下の全ファイルが再帰的に探索され、レビュー対象として渡される
3. **Given** glob パターンを指定する状態, **When** `8moku "src/**/*.py"` を実行, **Then** パターンにマッチする全ファイルがレビュー対象として渡される
4. **Given** 存在しないファイルパスを指定する状態, **When** `8moku nonexistent.py` を実行, **Then** ファイルが見つからない旨のエラーメッセージが表示され、終了コード 4 で終了する
5. **Given** 展開後のファイル数が `max_files_per_review` を超過する状態, **When** `8moku "src/**/*.py"` を実行, **Then** 警告メッセージとファイル数が表示され、続行するかの確認が求められる
6. **Given** 確認プロンプトでユーザーが拒否する状態, **When** 確認を拒否する, **Then** レビューは実行されず正常終了する（終了コード 0）
7. **Given** `--no-confirm` オプションが指定されている状態, **When** `8moku "src/**/*.py" --no-confirm` を実行, **Then** ファイル数超過の確認プロンプトが表示されず、そのままレビューが実行される
8. **Given** file モードで `--issue 122` を指定する状態, **When** `8moku src/auth.py --issue 122` を実行, **Then** Issue 番号がプロンプトコンテキストに含まれた状態でレビューが実行される
9. **Given** Git リポジトリ外でファイルパスを指定する状態, **When** `8moku document.md` を実行, **Then** Git に依存せずレビューが実行される
10. **Given** シンボリックリンクによる循環参照が存在するディレクトリを指定する状態, **When** `8moku src/` を実行, **Then** 循環参照リンクがスキップされ、警告メッセージが stderr に表示される

---

### User Story 5 - agents サブコマンド (Priority: P3)

開発者が `8moku agents` でエージェント一覧を表示し、`8moku agents <name>` で特定エージェントの詳細情報を確認する。

**Why this priority**: 利便性機能であり、レビュー機能自体が動作した後に付加価値として提供する。

**Independent Test**: `8moku agents` でビルトインとカスタムエージェントの一覧が表示され、`8moku agents code-reviewer` で詳細情報が表示されることで検証可能。

**Acceptance Scenarios**:

1. **Given** ビルトインエージェントのみが存在する状態, **When** `8moku agents` を実行, **Then** 6つのビルトインエージェントの名前・モデル・フェーズ・出力スキーマが一覧表示される
2. **Given** ビルトインエージェントとカスタムエージェントの両方が存在する状態, **When** `8moku agents` を実行, **Then** 全エージェントが一覧表示され、カスタムエージェントには `[custom]` マーカーが付与される
3. **Given** 特定のエージェント名を指定する状態, **When** `8moku agents code-reviewer` を実行, **Then** code-reviewer の全設定情報（説明・モデル・フェーズ・出力スキーマ・適用条件・許可ツール・システムプロンプト概要）が表示される
4. **Given** 存在しないエージェント名を指定する状態, **When** `8moku agents nonexistent` を実行, **Then** エージェントが見つからない旨のエラーメッセージが表示され、終了コード 4 で終了する
5. **Given** カスタムエージェント定義に不正なファイルが存在する状態, **When** `8moku agents` を実行, **Then** 正常なエージェントのみ一覧表示され、不正な定義の情報が stderr に警告として表示される

---

### Edge Cases

- PR 番号とファイルパスの同時指定（`8moku 123 src/auth.py`）は不可。複数の位置引数のうち整数が混在する場合はエラー（終了コード 4）
- 位置引数が `init` や `agents` と同名のファイルの場合、Typer のサブコマンド機構によりサブコマンドとして解釈される。file モードとして扱うにはパスセパレータを含める（`./init`）
- `8moku --help` は全コマンドのヘルプを表示する。`8moku init --help` や `8moku agents --help` はサブコマンド固有のヘルプを表示する
- diff モード・PR モードにおいて Git リポジトリ外で実行した場合、エラーメッセージとともに終了コード 4 で終了する（file モードは Git リポジトリ外でも動作可能）
- `--format` オプションの値が `markdown` でも `json` でもない場合、バリデーションエラーとして終了コード 4 で終了する
- `--timeout` に負の値や 0 を指定した場合、バリデーションエラーとして終了コード 4 で終了する
- `--issue` に負の値や 0 を指定した場合、バリデーションエラーとして終了コード 4 で終了する
- file モードで `.hachimoku/` ディレクトリが見つからない場合（Git リポジトリ外での実行を含む）、004-configuration の設定階層解決により最終的にビルトインデフォルト値が適用される（設定ファイル未発見は設定階層の正常な解決パスであり、明示的なデフォルト値の適用である）。警告メッセージを stderr に表示する
- file モードで指定されたディレクトリが空の場合、レビュー対象がない旨を通知して正常終了する（終了コード 0）
- file モードで指定された glob パターンにマッチするファイルがない場合、レビュー対象がない旨を通知して正常終了する（終了コード 0）
- file モードでは相対パスと絶対パスの両方をサポートする。相対パスは現在の作業ディレクトリから解決される
- `--parallel` / `--no-parallel` は Typer のフラグペアとして実装する。`--parallel` で明示的に有効化、`--no-parallel` で明示的に無効化、未指定時は設定ファイルのデフォルト（`true`）に従う
- `--save-reviews` / `--no-save-reviews` と `--show-cost` / `--no-show-cost` も同様にフラグペアとして実装する
- `8moku init --force` 実行時、既存のカスタマイズ済みファイルはデフォルト内容で上書きされる（ユーザーの責任。バックアップは行わない）
- `8moku agents` の出力は `--format` オプションの影響を受けない（常に人間可読形式）
- 入力エラー時のエラーメッセージには解決方法のヒントを含める（憲法 Art.3: エラーメッセージに解決方法を含める）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-CLI-001**: システムは `8moku`（推奨短縮名）および `hachimoku`（互換フルネーム）の両方のコマンド名で同一の CLI アプリケーションを提供しなければならない（親仕様 FR-017）。両コマンド名は `pyproject.toml` の `[project.scripts]` に登録され、同一の Typer app インスタンスを参照する

- **FR-CLI-002**: システムは位置引数からレビューモードまたはサブコマンドを以下の優先順で自動判定しなければならない（親仕様 FR-021）:
  1. **サブコマンド文字列**（`init`, `agents`, `config`）→ 対応するサブコマンドを実行（`config` は v0.1 では未実装エラー（終了コード 4）を返す）
  2. **整数のみ**（`8moku 123`）→ PR モード（指定 PR のレビュー）
  3. **パスライク文字列**（`/`, `\`, `*`, `?`, `.` のいずれかを含む）→ file モード
  4. **ファイルシステム上に存在するパス**（`Makefile`, `Dockerfile` 等の拡張子なしファイル名）→ file モード
  5. **引数なし**（`8moku`）→ diff モード（現在ブランチの変更差分レビュー）
  6. **上記のいずれにも該当しない** → エラー（終了コード 4）

  PR 番号とファイルパスの同時指定は不可とする。複数の位置引数のうち整数が混在する場合はエラーとする

- **FR-CLI-003**: システムはレビュー結果の重大度に応じた以下の終了コードを返さなければならない（親仕様 FR-009）:
  - **0**: 問題なし、またはレビュー対象がない場合の正常終了
  - **1**: Critical 重大度の問題が検出された
  - **2**: Important 重大度の問題が検出された（Critical なし）
  - **3**: 実行エラー（全エージェント失敗）
  - **4**: 入力エラー（PR 未発見・Git リポジトリ外での diff/PR 実行・ファイル未発見・引数解析エラー・`gh` 未認証・`--format` 不正値・`--timeout` 不正値・`--issue` 不正値・未実装サブコマンド等）

  入力エラー（4）は CLI 層で直接判定する。実行エラー（3）と重大度ベースの終了コード（0/1/2）は 005-review-engine の ReviewReport から決定する

- **FR-CLI-004**: システムはレビューレポートを stdout に出力し、進捗情報・エラー情報・警告を stderr に出力しなければならない（親仕様 FR-018）。これにより `8moku > result.md` のようなリダイレクト・パイプ利用時にレポートのみを取得可能にする。レポートのフォーマッティングは 007-output-format に委譲し、006 は出力先（stdout）の制御を担当する

- **FR-CLI-005**: システムは `--format` CLI オプションで出力形式（`markdown` / `json`）を選択可能にしなければならない（親仕様 FR-008 の CLI 部分）。選択された出力形式は 007-output-format のフォーマッターに渡される。デフォルト値は 004-configuration FR-CF-002 で定義された `"markdown"` とする

- **FR-CLI-006**: システムは 004-configuration FR-CF-002 で定義された CLI オプション名の対応表に基づいて、以下の CLI オプションを提供しなければならない:

  **設定上書きオプション**（設定ファイルの値を上書き、ConfigResolver に辞書形式で渡す）:

  | CLI オプション | 対応設定キー | 型 |
  |--------------|------------|-----|
  | `--model` | `model` | 文字列 |
  | `--timeout` | `timeout` | 正の整数 |
  | `--max-turns` | `max_turns` | 正の整数 |
  | `--parallel` / `--no-parallel` | `parallel` | boolean |
  | `--base-branch` | `base_branch` | 文字列 |
  | `--format` | `output_format` | `"markdown"` \| `"json"` |
  | `--save-reviews` / `--no-save-reviews` | `save_reviews` | boolean |
  | `--show-cost` / `--no-show-cost` | `show_cost` | boolean |
  | `--max-files` | `max_files_per_review` | 正の整数 |

  **per-invocation オプション**（設定ファイルに永続化しない実行時パラメータ）:

  | CLI オプション | 用途 | 対象コマンド |
  |--------------|------|------------|
  | `--issue <番号>` | Issue コンテキスト注入（親仕様 FR-024） | レビュー（全モード） |
  | `--force` | init での全ファイル強制上書き（親仕様 FR-028） | `init` |
  | `--no-confirm` | file モードでの確認スキップ（親仕様 FR-032） | レビュー（file モード） |

- **FR-CLI-007**: `8moku init` コマンドは以下を実行しなければならない（親仕様 FR-027）:
  1. Git リポジトリ内であることを確認する（`.git` ディレクトリの存在確認）。Git リポジトリ外ではエラー（終了コード 4）
  2. `.hachimoku/` ディレクトリを作成する
  3. `.hachimoku/config.toml` を生成する（全設定項目をコメントとして記載したテンプレート）
  4. `.hachimoku/agents/` にビルトイン6エージェントの定義ファイルをコピーする（003-agent-definition のパッケージ内バンドルから取得）
  5. `.hachimoku/reviews/` ディレクトリを作成する

- **FR-CLI-008**: `8moku init` は既存ファイルをスキップし不足ファイルのみ生成しなければならない。`--force` オプション指定時は全ファイルをデフォルト内容で上書きする（親仕様 FR-028）。スキップされたファイルの情報は stderr に表示する

- **FR-CLI-009**: file モードの CLI は以下の入力形式をサポートしなければならない（親仕様 FR-029）:
  - **単一ファイル**: `8moku src/auth.py`
  - **複数ファイル**: `8moku src/auth.py src/api/client.py`（位置引数として複数指定）
  - **ディレクトリ**: `8moku src/`（再帰的に全ファイルを探索、深さ制限なし）
  - **glob パターン**: `8moku "src/**/*.py"`（シェル展開を避けるためクォート推奨）

  相対パスは現在の作業ディレクトリから解決する。絶対パスもサポートする。指定されたファイルパスが存在しない場合は終了コード 4（入力エラー）で終了する。シンボリックリンクはリンク先の実体ファイルをレビュー対象とし、循環参照が検出された場合は当該リンクをスキップし警告を stderr に表示する

- **FR-CLI-010**: file モードは `--issue` オプションと併用可能としなければならない（親仕様 FR-031）。Issue 番号は 005-review-engine を通じてエージェントのプロンプトコンテキストに含まれる

- **FR-CLI-011**: file モードで展開後のファイル数が設定項目 `max_files_per_review` を超過する場合、警告メッセージと対象ファイル数を表示し、ユーザーに続行確認を求めなければならない（親仕様 FR-032）。`--no-confirm` オプション指定時は確認をスキップする。ユーザーが拒否した場合はレビューを実行せず正常終了する（終了コード 0）

- **FR-CLI-012**: `8moku agents` コマンドは以下を提供しなければならない（親仕様 FR-016）:
  - **引数なし**（`8moku agents`）: 全エージェントの一覧を表示する。各エージェントの名前・モデル・フェーズ・出力スキーマを表形式で表示し、カスタムエージェントには `[custom]` マーカーを付与する
  - **エージェント名指定**（`8moku agents <name>`）: 指定エージェントの全設定情報（説明・モデル・フェーズ・出力スキーマ・適用条件・許可ツール・システムプロンプト概要）を表示する

  エージェント定義の読み込みは 003-agent-definition の AgentLoader に委譲する。存在しないエージェント名が指定された場合はエラー（終了コード 4）

- **FR-CLI-013**: 全コマンドとサブコマンドに `--help` オプションを提供しなければならない（憲法 Art.3）。ヘルプにはコマンドの概要・使用方法・利用可能なオプションが含まれる

- **FR-CLI-014**: 入力エラー時のエラーメッセージは以下を含まなければならない（憲法 Art.3）:
  - エラーの内容（何が問題か）
  - 解決方法のヒント（どうすれば解決できるか）

  例: `Error: PR #999 not found. Verify the PR number exists on the remote repository.`
  例: `Error: File 'nonexistent.py' not found. Check the file path and try again.`

### Key Entities

- **CliApp（CLI アプリケーション）**: Typer で構築されたコマンドラインアプリケーション。`8moku` と `hachimoku` の2つのエントリポイントから呼び出される。デフォルト動作（レビュー）のコールバックと、`init`・`agents` のサブコマンドを持つ。CLI オプションの解析と入力モード判定を担当し、ビジネスロジックは各ハンドラーに委譲する
- **ExitCode（終了コード）**: レビュー結果と入力状態に応じた終了コードを表す IntEnum。SUCCESS(0)、CRITICAL(1)、IMPORTANT(2)、EXECUTION_ERROR(3)、INPUT_ERROR(4) の5値。005-review-engine の ReviewReport の最大重大度から決定されるか（0/1/2/3）、CLI 層で直接判定される（4）
- **InputModeResolver（入力モード判定）**: 位置引数の解析結果からレビューモード（diff / PR / file）を決定する処理。FR-CLI-002 の優先順ルールを適用する。PR 番号とファイルパスの同時指定を検出してエラーを返す機能を含む
- **FileTargetResolver（ファイルターゲット解決）**: file モードの位置引数（ファイルパス・ディレクトリ・glob パターン）を具体的なファイルパスリストに展開する処理。相対パスの解決、ディレクトリの再帰探索、glob パターンの展開、シンボリックリンクの循環参照検出を担当する。`max_files_per_review` との比較と確認プロンプトの表示も担当する
- **InitHandler（init ハンドラー）**: `8moku init` コマンドのビジネスロジック。Git リポジトリ確認、`.hachimoku/` ディレクトリ構造の作成、設定テンプレート生成、ビルトインエージェント定義のコピー（003-agent-definition のパッケージ内バンドルから）を担当する。`--force` オプションによる上書き制御を含む

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-CLI-001**: `8moku` と `hachimoku` の両方のコマンドで同一の機能が提供され、全てのオプション・サブコマンドが同一の動作をする（親仕様 FR-017）
- **SC-CLI-002**: 位置引数による入力モード判定が FR-CLI-002 の優先順ルールに100%準拠し、全パターン（整数・パスライク・ファイル存在・引数なし・不明文字列）で正しいモードが選択される
- **SC-CLI-003**: `8moku > result.md` のようなリダイレクト時に、出力ファイルにはレビューレポートのみが含まれ、進捗情報が混入しない（親仕様 SC-009）
- **SC-CLI-004**: 終了コードが ReviewReport の最大重大度に正しく対応し、CI/CD パイプラインの判定基準として利用可能である
- **SC-CLI-005**: `8moku init` 実行後、`.hachimoku/` 配下に config.toml（コメント付き）・6エージェント定義ファイル・reviews ディレクトリが生成される
- **SC-CLI-006**: file モードで `max_files_per_review` 超過時に確認プロンプトが表示され、`--no-confirm` で確認をスキップできる
- **SC-CLI-007**: `8moku agents` で全ビルトイン・カスタムエージェントの一覧が表示され、カスタムエージェントが明確に区別される
- **SC-CLI-008**: 入力エラー時のエラーメッセージが具体的な問題と解決方法のヒントを含む

## Assumptions

- CLI フレームワークとして Typer を使用する（CLAUDE.md の Tech Stack に記載）。Typer の `callback(invoke_without_command=True)` 機構でデフォルト動作（レビュー）を実装し、`command()` デコレータで `init`・`agents` サブコマンドを登録する
- デュアルコマンド名は `pyproject.toml` の `[project.scripts]` に `8moku` と `hachimoku` の2エントリを登録することで実現する。両エントリは同一の Python 関数を参照する
- CLI オプションの値は辞書形式で 004-configuration の ConfigResolver に渡す。ConfigResolver が設定階層の解決を行い、最終的な HachimokuConfig を返す（004-configuration Assumptions で定義済み）
- init コマンドでコピーするビルトインエージェント定義ファイルは、003-agent-definition でパッケージ内にバンドルされたファイルを `importlib.resources` で取得する
- file モードのディレクトリ再帰探索と glob パターン展開には Python 標準ライブラリ（`pathlib.Path.rglob()`・`glob.glob()`）を使用する。外部ライブラリの追加は不要
- file モードでの循環参照検出には `pathlib.Path.resolve()` によるシンボリックリンクの実体パス解決と、探索済みディレクトリのセットによる重複検出を使用する
- file モードの入力解決（glob パターン展開・ディレクトリ再帰探索・シンボリックリンク解決）は CLI 層の FileTargetResolver が担当し、展開後のファイルパスリストを 005-review-engine に渡す。005 のエージェントが `file_read` ツールで行うのはレビュー対象ファイルのコンテンツ読み込みであり、ターゲット解決ではない
- `config` サブコマンドは v0.1 では実装しない。ただし親仕様 FR-021 との整合性のため Typer に予約サブコマンドとして登録し、実行時は未実装である旨のエラーメッセージ（終了コード 4）を返す。将来の拡張として位置づける
- 確認プロンプト（`max_files_per_review` 超過時）は stderr に表示し、stdin からの入力を受け付ける。CI/CD 環境等で stdin が利用不可の場合は `--no-confirm` の使用を推奨する
- `agents` サブコマンドの出力形式は人間可読テキスト（テーブル形式）に固定する。JSON 出力はサポートしない
