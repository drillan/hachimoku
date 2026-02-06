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
- Q: AgentResult のステータス（成功/エラー/タイムアウト）をどのパターンで表現するか？ → A: 判別共用体（Discriminated Union）パターンを採用する。成功（AgentSuccess）・エラー（AgentError）・タイムアウト（AgentTimeout）を個別モデルとして定義し、判別キー（status フィールドの固定値）で型を一意に特定する。AgentResult はこれら3型の Union 型とする。これにより不可能な状態を型レベルで排除し、パターンマッチングによる型安全な分岐を可能にする
- Q: 6種の出力スキーマに共通ベースモデルを設けるか？ → A: 共通ベースモデル（ReviewIssue リスト）を定義し、全スキーマが継承する。ReviewReport への集約時に共通インターフェースでアクセスでき、新スキーマ追加時も一貫性が保証される

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 共通ドメインモデルによるエージェント結果の型安全な表現 (Priority: P1)

エージェント開発者（003-agent-definition, 005-review-engine）が、レビュー結果を型安全に表現・検証するための共通モデルを利用する。Severity、ReviewIssue、AgentResult（判別共用体）、ReviewReport 等の共通モデルにより、全エージェントが統一された構造でレビュー結果を出力できる。

**Why this priority**: ドメインモデルは全レイヤーの基盤であり、これがなければエージェント結果の構造化も集約も不可能。最小限のMVPとしてこのモデル定義があれば、他の仕様が型安全に開発を進められる。

**Independent Test**: モデルクラスをインポートし、各フィールドの型検証・制約検証（Severity の列挙値、ReviewIssue の必須フィールド等）が正しく動作することで検証可能。

**Acceptance Scenarios**:

1. **Given** Severity モデルが定義されている状態, **When** 定義された列挙値（Critical, Important, Suggestion, Nitpick）以外の値を設定しようとする, **Then** バリデーションエラーが発生する
2. **Given** ReviewIssue モデルが定義されている状態, **When** 必須フィールド（エージェント名、重大度、説明）を省略してインスタンスを生成しようとする, **Then** バリデーションエラーが発生する
3. **Given** AgentSuccess モデルが定義されている状態, **When** 正常完了時の結果（レビュー問題リスト・所要時間）を設定する, **Then** 型検証に成功しインスタンスが生成される
4. **Given** AgentSuccess モデルが定義されている状態, **When** 必須フィールド（issues, elapsed_time）を省略する, **Then** バリデーションエラーが発生する（不完全な成功状態は型レベルで不可能）
5. **Given** AgentError モデルが定義されている状態, **When** エラー情報を設定する, **Then** 型検証に成功しインスタンスが生成される
6. **Given** AgentTimeout モデルが定義されている状態, **When** タイムアウト情報を設定する, **Then** 型検証に成功しインスタンスが生成される
7. **Given** ReviewReport モデルが定義されている状態, **When** 複数の AgentResult（AgentSuccess・AgentError 混在）を集約する, **Then** 重大度別のグループ化と全体サマリー情報を保持したレポートが構成される
8. **Given** DiffReviewRecord モデルが定義されている状態, **When** コミットハッシュ・ブランチ名・AgentResult リストを設定する, **Then** 型検証に成功し review_mode="diff" のインスタンスが生成される
9. **Given** PRReviewRecord モデルが定義されている状態, **When** コミットハッシュ・PR 番号・AgentResult リストを設定する, **Then** 型検証に成功し review_mode="pr" のインスタンスが生成される
10. **Given** FileReviewRecord モデルが定義されている状態, **When** ファイルパスリスト・実行日時・作業ディレクトリ・AgentResult リストを設定する, **Then** 型検証に成功し review_mode="file" のインスタンスが生成される
11. **Given** ReviewHistoryRecord の JSON データが存在する状態, **When** review_mode フィールドの値でデシリアライズする, **Then** 正しいバリアントモデル（DiffReviewRecord/PRReviewRecord/FileReviewRecord）が自動選択される

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

- ReviewIssue のファイル位置（FileLocation）はオプショナルであり、ファイル位置なしでもモデルは有効である（エージェントが行番号を特定できないケースに対応）
- AgentSuccess の所要時間は正の値でなければならない。0以下の値はバリデーションエラーとなる
- SCHEMA_REGISTRY に同名のスキーマを重複登録しようとした場合、明確なエラーが発生する
- 出力スキーマのフィールドに想定外の追加フィールドが含まれる場合の扱い（厳格モード: 追加フィールドを拒否する）
- ReviewReport に AgentResult が0件の場合でもレポートは生成可能である（全エージェント失敗時の部分レポート対応、親仕様 SC-006）
- AgentResult の JSON デシリアライズ時、判別キー（status フィールド）の値により正しいモデル（AgentSuccess/AgentError/AgentTimeout）が自動選択される
- ReviewHistoryRecord の JSON デシリアライズ時、判別キー（review_mode フィールド）の値により正しいモデル（DiffReviewRecord/PRReviewRecord/FileReviewRecord）が自動選択される
- FileReviewRecord の作業ディレクトリは絶対パスとして保存される。相対パスで指定されたファイルパスも、ファイルパスリスト内では作業ディレクトリからの相対パスとして保持される

## Requirements *(mandatory)*

### Functional Requirements

- **FR-DM-001**: システムは重大度（Severity）を Critical、Important、Suggestion、Nitpick の4段階で定義し、上位の重大度ほど優先度が高い順序関係を持たなければならない
- **FR-DM-002**: システムはレビュー問題（ReviewIssue）を統一的に表現するモデルを提供しなければならない。必須属性はエージェント名、重大度、説明とし、オプション属性としてファイル位置（FileLocation: ファイルパスと行番号の組）、推奨アクション、カテゴリを持つ。ファイルパスと行番号は FileLocation として一体で管理し、行番号がファイルパスなしに存在する不整合を型で防止する
- **FR-DM-003**: システムは単一エージェントの実行結果を判別共用体（Discriminated Union）として提供しなければならない。以下の3つの状態モデルを定義し、判別キー（status フィールドの固定値）で型を一意に特定する:
  - **AgentSuccess**: status="success"、エージェント名、レビュー問題リスト（必須）、所要時間（必須、正の値）
  - **AgentError**: status="error"、エージェント名、エラー情報（必須）
  - **AgentTimeout**: status="timeout"、エージェント名、タイムアウト情報（必須）
  - **AgentResult** はこれら3型の Union 型とする
- **FR-DM-004**: システムは全エージェントの結果を集約したレビューレポート（ReviewReport）を表現するモデルを提供しなければならない。レポートは AgentResult のリスト、エージェントごとのステータス・所要時間・コスト情報を含み、重大度別の ReviewIssue グループ化は AgentResult から計算導出するものとする
- **FR-DM-005**: システムは共通ベースモデル（BaseAgentOutput: ReviewIssue リスト）を定義し、以下の6種の出力スキーマはすべてこのベースモデルを継承しなければならない。各スキーマは固有フィールドを追加する
  - **ScoredIssues**: スコア付き問題リスト（code-reviewer 等が使用）
  - **SeverityClassified**: 重大度分類問題リスト（silent-failure-hunter 等が使用）
  - **TestGapAssessment**: テストギャップ評価（pr-test-analyzer が使用）
  - **MultiDimensionalAnalysis**: 多次元分析（type-design-analyzer が使用）
  - **CategoryClassification**: カテゴリ分類（comment-analyzer が使用）
  - **ImprovementSuggestions**: 改善提案リスト（code-simplifier が使用）
- **FR-DM-006**: システムはスキーマレジストリ（SCHEMA_REGISTRY）を提供し、スキーマ名から対応するスキーマモデルを取得できなければならない。存在しないスキーマ名を指定した場合は明確なエラーを発生させなければならない
- **FR-DM-007**: システムは各出力スキーマでエージェントの出力を型検証し、必須フィールドの欠損・型不一致・制約違反を検出できなければならない（親仕様 FR-004 の実現）
- **FR-DM-008**: システムは Severity から終了コードへのマッピングを定義しなければならない。Critical → 1、Important → 2、Suggestion/Nitpick/問題なし → 0 とする（親仕様 FR-009 の基盤）。なお、実行エラー（終了コード 3）と入力エラー（終了コード 4）は Severity とは独立したエラー状態であり、005-review-engine および 006-cli-interface がそれぞれ定義する
- **FR-DM-009**: 全モデルおよびスキーマは追加フィールドを拒否する厳格モードで動作しなければならない（想定外のデータ混入を防止する）
- **FR-DM-010**: Severity の列挙値はすべての入力経路で大文字・小文字を区別せず受け付けなければならない。内部表現は PascalCase（Critical, Important, Suggestion, Nitpick）で統一して保持する
- **FR-DM-011**: JSONL 蓄積用のレビュー履歴レコード（ReviewHistoryRecord）を判別共用体（Discriminated Union）として定義しなければならない。以下の3つのバリアントモデルを定義し、判別キー（`review_mode` フィールドの固定値）で型を一意に特定する:
  - **DiffReviewRecord**: review_mode="diff"、コミットハッシュ（必須）、ブランチ名（必須）、レビュー実行日時（必須）、AgentResult リスト（必須）、全体サマリー（必須）
  - **PRReviewRecord**: review_mode="pr"、コミットハッシュ（必須）、PR 番号（必須）、レビュー実行日時（必須）、AgentResult リスト（必須）、全体サマリー（必須）
  - **FileReviewRecord**: review_mode="file"、ファイルパスリスト（必須）、レビュー実行日時（必須）、作業ディレクトリ（必須、絶対パス）、AgentResult リスト（必須）、全体サマリー（必須）
  - **ReviewHistoryRecord** はこれら3型の Union 型とする

  これにより各レビューモードで不要なフィールドが存在しない型安全な設計を実現する（親仕様 FR-026, FR-030 の基盤）

### Key Entities

- **Severity（重大度）**: レビュー問題の深刻度を表す列挙型。Critical（重大）、Important（重要）、Suggestion（提案）、Nitpick（些細）の4段階。順序関係を持ち、終了コードへのマッピングを定義する。内部表現は PascalCase
- **FileLocation（ファイル位置）**: レビュー問題のファイル内位置を表す値オブジェクト。ファイルパス（必須）と行番号（必須、正の整数）の組。ReviewIssue のオプション属性として使用し、行番号がファイルパスなしに存在する不整合を型で防止する
- **ReviewIssue（レビュー問題）**: 各エージェントが検出した問題の統一表現。エージェント名・重大度・説明（必須）、ファイル位置（FileLocation、オプション）・推奨アクション・カテゴリ（オプション）を持つ
- **AgentSuccess（エージェント成功結果）**: 判別共用体の成功バリアント。status="success"（判別キー）、エージェント名、レビュー問題リスト（必須）、所要時間（必須、正の値）を持つ
- **AgentError（エージェントエラー結果）**: 判別共用体のエラーバリアント。status="error"（判別キー）、エージェント名、エラー情報（必須）を持つ
- **AgentTimeout（エージェントタイムアウト結果）**: 判別共用体のタイムアウトバリアント。status="timeout"（判別キー）、エージェント名、タイムアウト情報（必須）を持つ
- **AgentResult（エージェント結果）**: AgentSuccess | AgentError | AgentTimeout の判別共用体（Discriminated Union）。status フィールドの固定値で型を一意に特定する
- **ReviewReport（レビューレポート）**: 全エージェントの結果を集約した最終出力。AgentResult のリスト、全体サマリー（総問題数、最大重大度、総実行時間、総コスト）を含む。重大度別の ReviewIssue グループ化は AgentResult から計算導出する
- **DiffReviewRecord（diff レビューレコード）**: 判別共用体のバリアント。review_mode="diff"（判別キー）、コミットハッシュ、ブランチ名、レビュー実行日時、AgentResult リスト、全体サマリーを持つ
- **PRReviewRecord（PR レビューレコード）**: 判別共用体のバリアント。review_mode="pr"（判別キー）、コミットハッシュ、PR 番号、レビュー実行日時、AgentResult リスト、全体サマリーを持つ
- **FileReviewRecord（file レビューレコード）**: 判別共用体のバリアント。review_mode="file"（判別キー）、ファイルパスリスト、レビュー実行日時、作業ディレクトリ（絶対パス）、AgentResult リスト、全体サマリーを持つ
- **ReviewHistoryRecord（レビュー履歴レコード）**: DiffReviewRecord | PRReviewRecord | FileReviewRecord の判別共用体（Discriminated Union）。`review_mode` フィールドの固定値で型を一意に特定する。JSONL 蓄積時に使用される
- **BaseAgentOutput（出力ベースモデル）**: 全出力スキーマの共通ベースモデル。ReviewIssue リストを共通属性として持つ。6種の出力スキーマはすべてこのベースを継承し、固有フィールドを追加する。ReviewReport への集約時に共通インターフェースとして機能する
- **ScoredIssues（スコア付き問題）**: BaseAgentOutput を継承。数値スコアとレビュー問題のリストを組み合わせた出力スキーマ。コードレビューエージェント等が使用する
- **SeverityClassified（重大度分類問題）**: BaseAgentOutput を継承。重大度でグループ化されたレビュー問題リストの出力スキーマ。サイレント障害検出エージェント等が使用する
- **TestGapAssessment（テストギャップ評価）**: BaseAgentOutput を継承。テストカバレッジの欠落を評価する出力スキーマ。テスト分析エージェントが使用する
- **MultiDimensionalAnalysis（多次元分析）**: BaseAgentOutput を継承。複数の評価軸でスコアリングする出力スキーマ。型設計分析エージェントが使用する
- **CategoryClassification（カテゴリ分類）**: BaseAgentOutput を継承。カテゴリ別に問題を分類する出力スキーマ。コメント分析エージェントが使用する
- **ImprovementSuggestions（改善提案）**: BaseAgentOutput を継承。具体的な改善提案のリストを提供する出力スキーマ。コード簡潔化エージェントが使用する
- **SCHEMA_REGISTRY（スキーマレジストリ）**: スキーマ名から対応するスキーマモデルへのマッピングを管理するレジストリ。エージェント定義ファイルの `output_schema` フィールドからスキーマを解決する際に使用する

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-DM-001**: 全ドメインモデル（Severity, FileLocation, ReviewIssue, AgentSuccess, AgentError, AgentTimeout, ReviewReport, DiffReviewRecord, PRReviewRecord, FileReviewRecord）に対して、有効なデータで型検証が成功し、無効なデータで明確なバリデーションエラーが発生する
- **SC-DM-002**: 6種の出力スキーマすべてがスキーマレジストリに登録され、名前で検索・取得できる
- **SC-DM-003**: Severity のマッピングにより、全パターン（Critical/Important/Suggestion/Nitpick/問題なし）の終了コードが親仕様 FR-009 の定義と一致する
- **SC-DM-004**: 出力スキーマで必須フィールドが欠損したデータを検証した場合、どのフィールドが不正かを特定可能なエラーメッセージが生成される
- **SC-DM-005**: 全モデル・スキーマが厳格モードで動作し、定義外の追加フィールドを含むデータがバリデーションエラーとなる
- **SC-DM-006**: 親仕様 001 で定義された全 Key Entities（Severity, ReviewIssue, AgentResult, ReviewReport, ReviewHistoryRecord（DiffReviewRecord/PRReviewRecord/FileReviewRecord の判別共用体）, 6種の出力スキーマ, SCHEMA_REGISTRY）に対応するモデルが本仕様で定義されている

## Assumptions

- pydantic-ai の `result_type` が Pydantic モデルを要求するため、本仕様の全モデル・スキーマは Pydantic 互換である必要がある。これは実装上の選択ではなくフレームワークによるアーキテクチャ制約である
- 出力スキーマの具体的なフィールド構成は、各ビルトインエージェント（003-agent-definition で定義予定）の要件に基づいて最終確定する。本仕様では親仕様の Key Entities と6種のスキーマ分類に基づくフレームワークを定義する
- BaseAgentOutput のサマリーテキスト属性の要否は、003-agent-definition で各エージェントの出力要件が確定した段階で再検討する。現時点では ReviewIssue リストのみを共通属性とする
- コスト情報（AgentSuccess・ReviewReport に含む）はオプショナル属性とする。LLM プロバイダによっては取得できない場合があるため。構造は最小限の共通構造（入力トークン数、出力トークン数、合計コスト）とする
- ReviewHistoryRecord の直列化フォーマット（JSON フィールド名、日時形式等）は 007-output-format との協調で最終決定するが、モデル構造は本仕様で定義する
