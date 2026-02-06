# Feature Specification: ドメインモデル・出力スキーマ定義

**Feature Branch**: `002-domain-models`
**Created**: 2026-02-06
**Status**: Draft
**Input**: User description: "specs/README.md と親仕様 specs/001-architecture-spec/spec.md をもとに 002-domain-models を定義"
**Parent Spec**: [001-architecture-spec](../001-architecture-spec/spec.md)
**Priority**: P0（全仕様の共通基盤）

## Clarifications

### Session 2026-02-06

- 親仕様 FR-004 に基づき、出力スキーマは6種（ScoredIssues, SeverityClassified, TestGapAssessment, MultiDimensionalAnalysis, CategoryClassification, ImprovementSuggestions）とする
- README.md の「スキーマの所属境界」に基づき、SCHEMA_REGISTRY と各エージェントの出力スキーマはすべて 002-domain-models に含める。出力フォーマット（007）はフォーマッター・ストレージのみを担当する
- Severity のマッピング（重大度の定義と対応する終了コード）は 002 で定義する
- Q: ドメインモデルの実装技術に制約はあるか？ → A: エージェント実行基盤として pydantic-ai を採用しており、`result_type` による構造化出力制御に Pydantic モデルを必要とする。このアーキテクチャ制約により、ドメインモデル・出力スキーマは Pydantic モデルとして実装される
- Q: AgentResult のステータス（成功/エラー/タイムアウト）をどのパターンで表現するか？ → A: ステータス列挙型（success/error/timeout）＋ 状態ごとのオプショナルフィールドで表現する
- Q: 6種の出力スキーマに共通ベースモデルを設けるか？ → A: 共通ベースモデル（サマリーテキスト・ReviewIssue リスト）を定義し、全スキーマが継承する。ReviewReport への集約時に共通インターフェースでアクセスでき、新スキーマ追加時も一貫性が保証される

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 共通ドメインモデルによるエージェント結果の型安全な表現 (Priority: P1)

エージェント開発者（003-agent-definition, 005-review-engine）が、レビュー結果を型安全に表現・検証するための共通モデルを利用する。Severity、ReviewIssue、AgentResult、ReviewReport 等の共通モデルにより、全エージェントが統一された構造でレビュー結果を出力できる。

**Why this priority**: ドメインモデルは全レイヤーの基盤であり、これがなければエージェント結果の構造化も集約も不可能。最小限のMVPとしてこのモデル定義があれば、他の仕様が型安全に開発を進められる。

**Independent Test**: モデルクラスをインポートし、各フィールドの型検証・制約検証（Severity の列挙値、ReviewIssue の必須フィールド等）が正しく動作することで検証可能。

**Acceptance Scenarios**:

1. **Given** Severity モデルが定義されている状態, **When** 定義された列挙値（Critical, Important, Suggestion, Nitpick）以外の値を設定しようとする, **Then** バリデーションエラーが発生する
2. **Given** ReviewIssue モデルが定義されている状態, **When** 必須フィールド（エージェント名、重大度、説明）を省略してインスタンスを生成しようとする, **Then** バリデーションエラーが発生する
3. **Given** AgentResult モデルが定義されている状態, **When** 正常完了時の結果（レビュー問題リスト・所要時間）を設定する, **Then** 型検証に成功しインスタンスが生成される
4. **Given** AgentResult モデルが定義されている状態, **When** エラー発生時の結果（エラー情報・タイムアウト情報）を設定する, **Then** 型検証に成功しインスタンスが生成される
5. **Given** ReviewReport モデルが定義されている状態, **When** 複数の AgentResult を集約する, **Then** 重大度別のグループ化と全体サマリー情報を保持したレポートが構成される

---

### User Story 2 - 出力スキーマによるエージェント出力の型検証 (Priority: P1)

エージェント開発者が、6種の出力スキーマを利用して各エージェントの出力形式を規定する。スキーマレジストリにより名前からスキーマを解決でき、不正な出力は型検証で自動的に検出される。

**Why this priority**: 出力スキーマは FR-004（出力スキーマによる型検証）の実現に直接必要であり、エージェント実行パイプラインの信頼性を担保する基盤。共通モデルと同等の優先度。

**Independent Test**: 各出力スキーマに対して有効なデータと無効なデータを入力し、スキーマバリデーションが正しく成功・失敗することで検証可能。

**Acceptance Scenarios**:

1. **Given** ScoredIssues スキーマが定義されている状態, **When** スコアと問題リストを含む有効なデータを入力する, **Then** バリデーションに成功する
2. **Given** SeverityClassified スキーマが定義されている状態, **When** 重大度別に分類された問題データを入力する, **Then** バリデーションに成功する
3. **Given** 6種のスキーマが SCHEMA_REGISTRY に登録されている状態, **When** スキーマ名で検索する, **Then** 対応するスキーマが取得される
4. **Given** SCHEMA_REGISTRY に登録されていないスキーマ名を指定した状態, **When** スキーマ名で検索する, **Then** 明確なエラーが発生する（存在しないスキーマは検出される）
5. **Given** いずれかの出力スキーマが定義されている状態, **When** 必須フィールドが欠損したデータを入力する, **Then** バリデーションエラーが発生し、どのフィールドが不正かが特定できる

---

### User Story 3 - Severity マッピングによる終了コード決定 (Priority: P2)

CLI やレビューエンジン（006-cli-interface, 005-review-engine）が、レビュー結果の最大重大度から終了コードを一意に決定する。Severity から終了コードへのマッピングが定義されており、判定ロジックの一貫性が保証される。

**Why this priority**: 終了コードは CI/CD 統合（US4）の要であるが、まず基本モデルとスキーマ（P1）が安定してから取り組む。

**Independent Test**: 各 Severity 値に対してマッピングを適用し、親仕様 FR-009 で定義された終了コード（0, 1, 2）が正しく返されることで検証可能。

**Acceptance Scenarios**:

1. **Given** レビュー結果に Critical の問題が含まれる, **When** 最大重大度から終了コードを決定する, **Then** 終了コード 1 が返される
2. **Given** レビュー結果に Important の問題のみ含まれる（Critical なし）, **When** 最大重大度から終了コードを決定する, **Then** 終了コード 2 が返される
3. **Given** レビュー結果に Suggestion と Nitpick のみ含まれる, **When** 最大重大度から終了コードを決定する, **Then** 終了コード 0 が返される
4. **Given** レビュー結果が空（問題なし）, **When** 終了コードを決定する, **Then** 終了コード 0 が返される

---

### Edge Cases

- ReviewIssue のファイル位置（ファイルパス・行番号）はオプショナルであり、ファイル位置なしでもモデルは有効である（エージェントが行番号を特定できないケースに対応）
- AgentResult の所要時間は正の値でなければならない。0以下の値はバリデーションエラーとなる
- SCHEMA_REGISTRY に同名のスキーマを重複登録しようとした場合、明確なエラーが発生する
- 出力スキーマのフィールドに想定外の追加フィールドが含まれる場合の扱い（厳格モード: 追加フィールドを拒否する）
- Severity の列挙値は大文字・小文字を区別せずに受け付けるが、内部表現は統一された形式で保持する
- ReviewReport に AgentResult が0件の場合でもレポートは生成可能である（全エージェント失敗時の部分レポート対応、親仕様 SC-006）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-DM-001**: システムは重大度（Severity）を Critical、Important、Suggestion、Nitpick の4段階で定義し、上位の重大度ほど優先度が高い順序関係を持たなければならない
- **FR-DM-002**: システムはレビュー問題（ReviewIssue）を統一的に表現するモデルを提供しなければならない。必須属性はエージェント名、重大度、説明とし、オプション属性としてファイルパス、行番号、推奨アクション、カテゴリを持つ
- **FR-DM-003**: システムは単一エージェントの実行結果（AgentResult）を表現するモデルを提供しなければならない。ステータス列挙型（success/error/timeout）で状態を表し、正常完了時はレビュー問題リストと所要時間を、エラー時はエラー情報を、タイムアウト時はタイムアウト情報を状態ごとのオプショナルフィールドとして格納する
- **FR-DM-004**: システムは全エージェントの結果を集約したレビューレポート（ReviewReport）を表現するモデルを提供しなければならない。レポートはレビュー問題の重大度別グループ化、エージェントごとのステータス・所要時間・コスト情報を含まなければならない
- **FR-DM-005**: システムは共通ベースモデル（BaseAgentOutput: サマリーテキスト・ReviewIssue リスト）を定義し、以下の6種の出力スキーマはすべてこのベースモデルを継承しなければならない。各スキーマは固有フィールドを追加する
  - **ScoredIssues**: スコア付き問題リスト（code-reviewer 等が使用）
  - **SeverityClassified**: 重大度分類問題リスト（silent-failure-hunter 等が使用）
  - **TestGapAssessment**: テストギャップ評価（pr-test-analyzer が使用）
  - **MultiDimensionalAnalysis**: 多次元分析（type-design-analyzer が使用）
  - **CategoryClassification**: カテゴリ分類（comment-analyzer が使用）
  - **ImprovementSuggestions**: 改善提案リスト（code-simplifier が使用）
- **FR-DM-006**: システムはスキーマレジストリ（SCHEMA_REGISTRY）を提供し、スキーマ名から対応するスキーマモデルを取得できなければならない。存在しないスキーマ名を指定した場合は明確なエラーを発生させなければならない
- **FR-DM-007**: システムは各出力スキーマでエージェントの出力を型検証し、必須フィールドの欠損・型不一致・制約違反を検出できなければならない（親仕様 FR-004 の実現）
- **FR-DM-008**: システムは Severity から終了コードへのマッピングを定義しなければならない。Critical → 1、Important → 2、Suggestion/Nitpick/問題なし → 0 とする（親仕様 FR-009 の基盤）
- **FR-DM-009**: 全モデルおよびスキーマは追加フィールドを拒否する厳格モードで動作しなければならない（想定外のデータ混入を防止する）
- **FR-DM-010**: Severity の列挙値は入力時に大文字・小文字を区別せず受け付け、内部的には統一された正規形で保持しなければならない
- **FR-DM-011**: JSONL 蓄積用のレビュー履歴レコード（ReviewHistoryRecord）を定義しなければならない。コミットハッシュ、ブランチ名、レビュー結果、エージェント情報をメタデータとして含む（親仕様 FR-026 の基盤）

### Key Entities

- **Severity（重大度）**: レビュー問題の深刻度を表す列挙型。Critical（重大）、Important（重要）、Suggestion（提案）、Nitpick（些細）の4段階。順序関係を持ち、終了コードへのマッピングを定義する
- **ReviewIssue（レビュー問題）**: 各エージェントが検出した問題の統一表現。エージェント名・重大度・説明（必須）、ファイルパス・行番号・推奨アクション・カテゴリ（オプション）を持つ
- **AgentResult（エージェント結果）**: 単一エージェントの実行結果。エージェント名とステータス列挙型（success/error/timeout）を必須属性とし、成功時のレビュー問題リスト・所要時間、エラー時のエラー情報、タイムアウト時のタイムアウト情報を状態ごとのオプショナル属性として持つ
- **ReviewReport（レビューレポート）**: 全エージェントの結果を集約した最終出力。AgentResult のリスト、重大度別に分類された ReviewIssue、全体サマリー（総問題数、最大重大度、総実行時間、総コスト）を含む
- **ReviewHistoryRecord（レビュー履歴レコード）**: JSONL 蓄積用のレコード。コミットハッシュ、ブランチ名、レビュー実行日時、レビューモード（diff/PR）、PR 番号（PR モード時）、AgentResult リスト、全体サマリーを含む
- **BaseAgentOutput（出力ベースモデル）**: 全出力スキーマの共通ベースモデル。サマリーテキストと ReviewIssue リストを共通属性として持つ。6種の出力スキーマはすべてこのベースを継承し、固有フィールドを追加する。ReviewReport への集約時に共通インターフェースとして機能する
- **ScoredIssues（スコア付き問題）**: BaseAgentOutput を継承。数値スコアとレビュー問題のリストを組み合わせた出力スキーマ。コードレビューエージェント等が使用する
- **SeverityClassified（重大度分類問題）**: BaseAgentOutput を継承。重大度でグループ化されたレビュー問題リストの出力スキーマ。サイレント障害検出エージェント等が使用する
- **TestGapAssessment（テストギャップ評価）**: BaseAgentOutput を継承。テストカバレッジの欠落を評価する出力スキーマ。テスト分析エージェントが使用する
- **MultiDimensionalAnalysis（多次元分析）**: BaseAgentOutput を継承。複数の評価軸でスコアリングする出力スキーマ。型設計分析エージェントが使用する
- **CategoryClassification（カテゴリ分類）**: BaseAgentOutput を継承。カテゴリ別に問題を分類する出力スキーマ。コメント分析エージェントが使用する
- **ImprovementSuggestions（改善提案）**: BaseAgentOutput を継承。具体的な改善提案のリストを提供する出力スキーマ。コード簡潔化エージェントが使用する
- **SCHEMA_REGISTRY（スキーマレジストリ）**: スキーマ名から対応するスキーマモデルへのマッピングを管理するレジストリ。エージェント定義ファイルの `output_schema` フィールドからスキーマを解決する際に使用する

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-DM-001**: 全ドメインモデル（Severity, ReviewIssue, AgentResult, ReviewReport, ReviewHistoryRecord）に対して、有効なデータで型検証が成功し、無効なデータで明確なバリデーションエラーが発生する
- **SC-DM-002**: 6種の出力スキーマすべてがスキーマレジストリに登録され、名前で検索・取得できる
- **SC-DM-003**: Severity のマッピングにより、全パターン（Critical/Important/Suggestion/Nitpick/問題なし）の終了コードが親仕様 FR-009 の定義と一致する
- **SC-DM-004**: 出力スキーマで必須フィールドが欠損したデータを検証した場合、どのフィールドが不正かを特定可能なエラーメッセージが生成される
- **SC-DM-005**: 全モデル・スキーマが厳格モードで動作し、定義外の追加フィールドを含むデータがバリデーションエラーとなる
- **SC-DM-006**: 依存先の仕様（003-agent-definition, 005-review-engine, 007-output-format）が必要とする全モデル・スキーマが過不足なく定義されている

## Assumptions

- pydantic-ai の `result_type` が Pydantic モデルを要求するため、本仕様の全モデル・スキーマは Pydantic 互換である必要がある。これは実装上の選択ではなくフレームワークによるアーキテクチャ制約である
- 出力スキーマの具体的なフィールド構成は、各ビルトインエージェント（003-agent-definition で定義予定）の要件に基づいて最終確定する。本仕様では親仕様の Key Entities と6種のスキーマ分類に基づくフレームワークを定義する
- コスト情報（AgentResult・ReviewReport に含む）の具体的な構造（トークン数、API コスト等）は、利用する LLM プロバイダの仕様に依存するため、最小限の共通構造（入力トークン数、出力トークン数、合計コスト）で定義する
- ReviewHistoryRecord の直列化フォーマット（JSON フィールド名、日時形式等）は 007-output-format との協調で最終決定するが、モデル構造は本仕様で定義する
