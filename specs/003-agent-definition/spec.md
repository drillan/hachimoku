# Feature Specification: エージェント定義・ローダー

**Feature Branch**: `003-agent-definition`
**Created**: 2026-02-06
**Status**: Draft
**Input**: User description: "specs/001-architecture-spec/spec.md を親仕様とし、specs/README.mdの003-agent-definitionの仕様を策定してください"
**Parent Spec**: [001-architecture-spec](../001-architecture-spec/spec.md)
**Priority**: P1（基本レビュー実行に必須）
**Depends On**: [002-domain-models](../002-domain-models/spec.md)

## Clarifications

### Session 2026-02-06

- 親仕様 FR-003, FR-011, FR-014 および US3 を本仕様で実現する（FR-005 は Issue #64 により 005-review-engine に移管）
- README.md のスキーマ所属境界に基づき、出力スキーマの定義は 002-domain-models に含まれる。本仕様ではエージェント定義の `output_schema` フィールドから SCHEMA_REGISTRY を参照してスキーマを解決する
- エージェント定義ファイルのフォーマットは TOML に統一（親仕様 Clarification Session の決定事項）
- ビルトイン6エージェントの定義ファイルは Python パッケージ内にバンドルし、`8moku init` 時にプロジェクトへコピーする（親仕様 US8）
- エージェントのローダーはビルトイン定義とカスタム定義の両方を読み込み、同名の場合はカスタム定義がビルトインを上書きする（親仕様 US3 Acceptance Scenario 2）

### Session 2026-02-07

- Q: Issue #64 により AgentSelector が pydantic-ai エージェント（SelectorAgent）に再設計されるが、003 の AgentSelector の扱いは？ → A: 003 から AgentSelector を完全に削除し、セレクター責務は 005-review-engine の SelectorAgent に一本化する。003 のスコープはエージェント定義・ローダーのみとする。`file_patterns` / `content_patterns` は TOML フィールドとして残り、005 の SelectorAgent が判断ガイダンスとして参照する
- Q: SelectorAgent がパターンを判断ガイダンスとして参照する新設計で、`content_patterns` の正規表現構文チェックは維持すべきか？ → A: 維持する。SelectorAgent の判断ガイダンスとしての役割に変わっても、無効な正規表現はユーザーの意図が不明確であることを示すため、定義読み込み時のバリデーションエラーとして早期フィードバックを提供する
- Q: 既存の `selector.py`（メカニカルマッチング実装）と対応テストの扱いは？ → A: 削除する。005-review-engine で SelectorAgent として完全に再設計されるため、旧実装は不要。`src/hachimoku/agents/selector.py` と `tests/test_selector.py` を Issue #64 の実装時に削除する
- Q: 003 の定義読み込み時に `allowed_tools` のバリデーションをどのレベルまで行うか？ → A: 型バリデーション（`list[str]`）のみ。カテゴリ名の妥当性チェック（ToolCatalog との照合）は 005-review-engine が担当する。003 は TOML 定義のデータ構造保証に集中し、ToolCatalog のドメイン知識を持ち込まない
- Q: 親仕様 FR-005（エージェント選択機能）の実現帰属はどうするか？ → A: FR-005 を 003 の実現対象から除外し、005-review-engine の実現対象に移す。003 が実現する親仕様は FR-003, FR-011, FR-014 のみとなる

## User Scenarios & Testing *(mandatory)*

### User Story 1 - TOML 定義ファイルからのエージェント読み込み (Priority: P1)

システムが TOML 形式のエージェント定義ファイルを読み込み、レビューエージェントの構成情報（名前・モデル・プロンプト・出力スキーマ・適用条件等）を AgentDefinition モデルとして構築する。ローダーはビルトインエージェントとカスタムエージェントを統合して提供する。

**Why this priority**: エージェント定義の読み込みはレビュー実行の前提であり、この機能なしにはエージェントの構築・実行が不可能。基本レビュー実行（US1）の直接的な依存先。

**Independent Test**: ビルトインエージェント定義ファイルをローダーに渡し、6つの AgentDefinition モデルが正しく構築されることで検証可能。

**Acceptance Scenarios**:

1. **Given** ビルトインエージェント定義ファイルが存在する状態, **When** ローダーがエージェント定義を読み込む, **Then** 6つの AgentDefinition モデルが構築され、各モデルの全フィールド（名前・説明・モデル・許可ツール・出力スキーマ・システムプロンプト・適用条件）が TOML ファイルの内容と一致する
2. **Given** エージェント定義ファイルにスキーマレジストリに登録されている `output_schema` 名が指定されている, **When** ローダーが定義を読み込む, **Then** SCHEMA_REGISTRY から対応するスキーマモデルが解決される
3. **Given** エージェント定義ファイルにスキーマレジストリに存在しない `output_schema` 名が指定されている, **When** ローダーが定義を読み込む, **Then** バリデーションエラーが発生し、存在しないスキーマ名を含む明確なエラーメッセージが生成される
4. **Given** エージェント定義ファイルの TOML が構文的に不正, **When** ローダーが読み込みを試行する, **Then** パースエラーが発生し、ファイル名と具体的なエラー内容を含むメッセージが生成される
5. **Given** エージェント定義ファイルの必須フィールドが欠損している, **When** ローダーが読み込みを試行する, **Then** バリデーションエラーが発生し、欠損フィールド名を含む明確なエラーメッセージが生成される

---

### ~~User Story 2 - 変更内容に基づくエージェント自動選択~~ (削除: 005-review-engine へ移管)

> **移管理由**: Issue #64 により AgentSelector が pydantic-ai エージェント（SelectorAgent）に再設計されたため、エージェント選択の全責務は 005-review-engine に移管された。`file_patterns` / `content_patterns` / `phase` は TOML 定義フィールドとして本仕様に残り、005 の SelectorAgent の判断ガイダンスとして機能する。受入シナリオは 005-review-engine の SelectorAgent 仕様で定義される。

---

### User Story 3 - カスタムエージェント定義によるレビュー拡張 (Priority: P2)

開発者がプロジェクト固有のレビューエージェントを `.hachimoku/agents/` に TOML ファイルとして追加し、ビルトインエージェントと共にレビューに参加させる。同名のカスタム定義はビルトイン定義を上書きする。

**Why this priority**: カスタマイズ性はツールの長期的な価値に直結するが、まずビルトインエージェントの読み込みと選択（P1）が安定してから取り組む。

**Independent Test**: プロジェクトの `.hachimoku/agents/` にカスタム TOML ファイルを配置し、ローダーがカスタムエージェントをビルトインエージェントと共に読み込むことで検証可能。

**Acceptance Scenarios**:

1. **Given** `.hachimoku/agents/` にカスタムエージェント定義ファイルが配置されている, **When** ローダーがエージェント定義を読み込む, **Then** カスタムエージェントがビルトインエージェントと共に読み込まれる
2. **Given** カスタムエージェントがビルトインエージェントと同名で定義されている, **When** ローダーがエージェント定義を読み込む, **Then** カスタム定義がビルトイン定義を上書きする
3. **Given** カスタムエージェント定義ファイルに不正な形式のデータがある, **When** ローダーが読み込みを試行する, **Then** 不正なエージェントのみスキップされ、ファイル名と具体的なエラー内容を含むエラーメッセージが生成され、他のエージェントは正常に読み込まれる。ただし、不正なカスタム定義がビルトインエージェントと同名の場合、上書きは行われずビルトイン定義がそのまま使用される
4. **Given** `.hachimoku/agents/` ディレクトリが存在しない, **When** ローダーがエージェント定義を読み込む, **Then** ビルトインエージェントのみが読み込まれる（カスタムディレクトリの不在はエラーとしない）

---

### User Story 4 - ビルトイン6エージェントの定義提供 (Priority: P1)

システムが6つの専門レビューエージェント（コードレビュー、サイレント障害検出、テスト分析、型設計分析、コメント分析、コード簡潔化）を TOML 定義ファイルとして標準提供する。各エージェントは専門領域に特化した適用ルールとシステムプロンプトを持つ。

**Why this priority**: ビルトインエージェントは基本レビュー実行の構成要素であり、エンドユーザーが何も設定しなくても有用なレビューが得られるために必須。

**Independent Test**: 6つのビルトイン定義ファイルがローダーで正常に読み込まれ、各エージェントの適用ルール・出力スキーマが正しいことで検証可能。

**Acceptance Scenarios**:

1. **Given** ビルトイン定義ファイルが存在する状態, **When** ローダーが読み込む, **Then** 6つのエージェント（code-reviewer, silent-failure-hunter, pr-test-analyzer, type-design-analyzer, comment-analyzer, code-simplifier）が読み込まれる
2. **Given** 各ビルトインエージェントが読み込まれた状態, **When** 各エージェントの出力スキーマを確認する, **Then** 002-domain-models で定義された対応するスキーマと一致する（code-reviewer → scored_issues, silent-failure-hunter → severity_classified, pr-test-analyzer → test_gap_assessment, type-design-analyzer → multi_dimensional_analysis, comment-analyzer → category_classification, code-simplifier → improvement_suggestions）
3. **Given** 各ビルトインエージェントが読み込まれた状態, **When** 各エージェントの適用ルールを確認する, **Then** 各エージェントの専門領域に適したファイルパターンまたはコンテンツパターンが設定されている
4. **Given** 各ビルトインエージェントが読み込まれた状態, **When** 各エージェントの実行フェーズを確認する, **Then** 各エージェントに適切なフェーズ（early/main/final）が割り当てられている

---

### Edge Cases

- エージェント定義ファイルで参照されたスキーマが SCHEMA_REGISTRY に存在しない場合、バリデーションエラーとしてスキップし明確なエラーメッセージを表示する（親仕様 Edge Cases）
- エージェント定義の `file_patterns` や `content_patterns` が空リストであってもバリデーションエラーとはしない（有効なデータ状態として許容する）。空リスト時の選択挙動は 005-review-engine の SelectorAgent が判断する
- `content_patterns` に無効な正規表現が含まれる場合、定義読み込み時にバリデーションエラーが発生し、具体的なエラーメッセージが表示される
- `.hachimoku/agents/` に `.toml` 以外のファイルが存在する場合、それらは無視される
- ビルトインとカスタムの両方にエージェント定義が存在し、カスタム側がバリデーションエラーの場合、ビルトイン定義がそのまま使用される（上書きは成功したカスタム定義にのみ適用）
- `file_patterns` は fnmatch 互換のグロブパターン記法で記述する（`*`, `?`, `[seq]`, `[!seq]`）。バリデーション時の構文チェック対象であり、実際のマッチング評価は 005-review-engine の SelectorAgent が判断ガイダンスとして参照する
- `content_patterns` は Python `re` 互換の正規表現記法で記述する。バリデーション時の構文チェック対象であり、実際のマッチング評価は 005-review-engine の SelectorAgent が判断ガイダンスとして参照する
- `phase` フィールドが省略された場合、デフォルト値 `main` が適用される
- エージェント名に使用できる文字はアルファベット小文字・数字・ハイフンのみとする。これ以外の文字を含む名前はバリデーションエラーとなる
- `allowed_tools` フィールドが空リストの場合、エージェントはツールなしで実行される（有効な状態）
- 同じフェーズ内の複数エージェントの実行順序は 005-review-engine の SelectorAgent が決定する（003 ではフェーズと名前のデータのみ保持）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-AD-001**: システムは TOML 形式のエージェント定義ファイルを読み込み、AgentDefinition モデルとして構築できなければならない。定義ファイルは以下の必須フィールドを含む:
  - `name`: エージェント名（アルファベット小文字・数字・ハイフンのみ、一意）
  - `description`: エージェントの説明
  - `model`: 使用する LLM モデル名
  - `output_schema`: SCHEMA_REGISTRY に登録されたスキーマ名（002-domain-models で定義）
  - `system_prompt`: エージェントのシステムプロンプト

  以下のオプションフィールドを含む:
  - `allowed_tools`: 許可するツールのリスト（デフォルト: 空リスト）
  - `applicability`: 適用ルール（ApplicabilityRule）。TOML に `[applicability]` セクションが存在しない場合、`{always: true}` がデフォルトとして適用される（エージェントは常に実行対象となる）
  - `phase`: 実行フェーズ（"early", "main", "final" のいずれか、デフォルト: "main"）

- **FR-AD-002**: エージェント定義の ApplicabilityRule は、005-review-engine の SelectorAgent が参照する判断ガイダンスとして以下のフィールドを持つ。本仕様ではデータモデルの定義とバリデーションのみを担当し、実際の評価ロジック（エージェント選択）は 005-review-engine の SelectorAgent が担当する:
  - `always`: 常時適用フラグ（デフォルト: false）。true の場合、SelectorAgent は他の条件に関わらず当該エージェントを選択すべきことを示すガイダンス
  - `file_patterns`: ファイル名パターンのリスト（fnmatch 互換グロブパターン記法）。SelectorAgent がレビュー対象のファイルとの関連性を判断する際のガイダンス
  - `content_patterns`: コンテンツパターンのリスト（Python `re` 互換正規表現記法）。SelectorAgent がレビュー対象のコンテンツとの関連性を判断する際のガイダンス

- **FR-AD-003**: システムはビルトインエージェント定義ファイルを Python パッケージ内にバンドルし、ローダーが常にアクセスできなければならない。ビルトイン定義はカスタム定義が存在しない場合のデフォルトとして機能する（親仕様 FR-003）

- **FR-AD-004**: システムはプロジェクト固有のカスタムエージェント定義を `.hachimoku/agents/` ディレクトリから読み込み、ビルトインエージェントと同等に扱えなければならない。カスタム定義がビルトイン定義と同名の場合、カスタム定義がビルトインを上書きする（親仕様 FR-011）

- **FR-AD-005**: システムは以下の6つのビルトインエージェントを TOML 定義ファイルとして標準提供しなければならない（親仕様 FR-014）:
  - **code-reviewer**: コード品質・バグ・ベストプラクティスのレビュー。出力スキーマ: `scored_issues`
  - **silent-failure-hunter**: サイレント障害・エラーハンドリング不備の検出。出力スキーマ: `severity_classified`
  - **pr-test-analyzer**: テストカバレッジの欠落・テスト品質の分析。出力スキーマ: `test_gap_assessment`
  - **type-design-analyzer**: 型アノテーション・型安全性の実用分析。出力スキーマ: `multi_dimensional_analysis`
  - **comment-analyzer**: コードコメントの正確性・品質の分析。出力スキーマ: `category_classification`
  - **code-simplifier**: コードの簡潔化・改善提案。出力スキーマ: `improvement_suggestions`

- **~~FR-AD-006~~**: ~~セレクター機能~~ → 005-review-engine の SelectorAgent に移管（Issue #64）。親仕様 FR-005 の実現は 005-review-engine が担当する

- **FR-AD-007**: システムはエージェント定義ファイルのバリデーションにおいて以下を検証しなければならない:
  - 必須フィールドの存在
  - `output_schema` が SCHEMA_REGISTRY に登録されたスキーマ名であること
  - `content_patterns` の各要素が有効な正規表現であること
  - `phase` が "early", "main", "final" のいずれかであること
  - `name` がアルファベット小文字・数字・ハイフンのみで構成されていること

- **FR-AD-008**: ローダーはカスタムエージェント定義のバリデーションエラーを部分失敗として扱い、エラーの発生したエージェントのみスキップし、他のエージェントは正常に読み込まなければならない。スキップされたエージェント情報（ファイル名・エラー内容）はエラーレポートとして返却する。これは親仕様 FR-006（個別エージェントの失敗許容・部分レポート生成）の原則を定義読み込みフェーズに適用したものである

- **FR-AD-009**: `output_schema` フィールドの値は、002-domain-models の SCHEMA_REGISTRY に登録されたスキーマ名と一致しなければならない。ローダーは読み込み時に SCHEMA_REGISTRY への参照解決を行い、スキーマ名から対応する型情報を AgentDefinition に保持する

### Key Entities

- **AgentDefinition（エージェント定義）**: レビューエージェントの全構成情報を包含するモデル。TOML 定義ファイルから構築される。名前（一意識別子）、説明、使用モデル、許可ツールリスト、出力スキーマ参照（SCHEMA_REGISTRY のスキーマ名 + 解決済み型情報）、システムプロンプト、適用ルール（ApplicabilityRule）、実行フェーズを持つ
- **ApplicabilityRule（適用ルール）**: 005-review-engine の SelectorAgent がエージェントの適用可否を判断する際のガイダンス情報。常時適用フラグ（always）、ファイルパターンリスト（file_patterns、fnmatch 互換グロブ記法）、コンテンツパターンリスト（content_patterns、Python re 互換正規表現記法）から構成される。本仕様ではデータ構造の定義とバリデーション（正規表現の構文チェック等）を担当し、実際の評価ロジックは 005-review-engine の SelectorAgent が担当する
- **Phase（実行フェーズ）**: エージェントの実行順序を制御する列挙型。early（前処理的な分析）、main（メインの詳細レビュー）、final（最終的な総合分析）の3値。実行順序の決定は 005-review-engine の SelectorAgent が担当する
- **AgentLoader（エージェントローダー）**: ビルトインとカスタムの TOML 定義ファイルを読み込み、バリデーションし、AgentDefinition モデルのリストを構築する処理。カスタム定義によるビルトイン上書きと部分失敗（不正な定義のスキップ）をサポートする
- **LoadResult（読み込み結果）**: ローダーの処理結果を表現するモデル。正常に読み込まれた AgentDefinition のリストと、スキップされたエージェントのエラー情報リストを持つ。呼び出し元がエラー情報の表示方法を決定できる

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-AD-001**: 6つのビルトインエージェント定義ファイルがすべて正常に読み込まれ、AgentDefinition モデルとして構築される
- **SC-AD-002**: エージェント定義ファイルを `.hachimoku/agents/` に配置するだけで、コード変更なしにカスタムエージェントがレビューに参加できる（親仕様 SC-003 の実現基盤）
- **SC-AD-003**: ビルトインと同名のカスタム定義が存在する場合、カスタム定義がビルトインを100%上書きする
- **SC-AD-004**: 不正な TOML ファイルや必須フィールド欠損の定義ファイルが存在しても、正常な定義ファイルはすべて読み込まれる（部分失敗許容）
- **~~SC-AD-005~~**: ~~セレクターによるエージェント選択~~ → 005-review-engine の SelectorAgent の Success Criteria に移管（Issue #64）
- **~~SC-AD-006~~**: ~~セレクター結果のフェーズ順ソート~~ → 005-review-engine の SelectorAgent の Success Criteria に移管（Issue #64）
- **SC-AD-007**: `output_schema` フィールドの値が SCHEMA_REGISTRY に存在しない場合、定義読み込み時に明確なエラーが報告される

## Assumptions

- エージェント定義ファイルの TOML パースには Python 標準ライブラリ `tomllib`（Python 3.11+）を使用する。外部ライブラリの追加は不要
- ビルトイン6エージェントのシステムプロンプトの具体的な内容は、実装フェーズで各エージェントの専門領域に基づいて策定する。本仕様ではプロンプトの構造と配置方法を定義する
- ビルトインエージェント定義ファイルのパッケージ内配置には `importlib.resources` を使用する（Python 標準ライブラリ）
- `file_patterns` の記法は fnmatch 互換グロブパターンとする。実際のマッチング方法（basename 対象 / フルパス対象 / ディレクトリパターン等）は 005-review-engine の SelectorAgent の判断に委ねられる
- エージェント定義の `model` フィールドの値は文字列として保持し、実際のモデル解決は 005-review-engine が担当する。本仕様ではモデル名のバリデーション（存在確認等）は行わない
- `allowed_tools` フィールドの値は文字列リストとして保持し、実際のツール解決は 005-review-engine が担当する
