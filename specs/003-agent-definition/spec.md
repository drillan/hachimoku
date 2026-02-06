# Feature Specification: エージェント定義・ローダー・セレクター

**Feature Branch**: `003-agent-definition`
**Created**: 2026-02-06
**Status**: Draft
**Input**: User description: "specs/001-architecture-spec/spec.md を親仕様とし、specs/README.mdの003-agent-definitionの仕様を策定してください"
**Parent Spec**: [001-architecture-spec](../001-architecture-spec/spec.md)
**Priority**: P1（基本レビュー実行に必須）
**Depends On**: [002-domain-models](../002-domain-models/spec.md)

## Clarifications

### Session 2026-02-06

- 親仕様 FR-003, FR-005, FR-011, FR-014 および US3 を本仕様で実現する
- README.md のスキーマ所属境界に基づき、出力スキーマの定義は 002-domain-models に含まれる。本仕様ではエージェント定義の `output_schema` フィールドから SCHEMA_REGISTRY を参照してスキーマを解決する
- エージェント定義ファイルのフォーマットは TOML に統一（親仕様 Clarification Session の決定事項）
- ビルトイン6エージェントの定義ファイルは Python パッケージ内にバンドルし、`8moku init` 時にプロジェクトへコピーする（親仕様 US8）
- エージェントのローダーはビルトイン定義とカスタム定義の両方を読み込み、同名の場合はカスタム定義がビルトインを上書きする（親仕様 US3 Acceptance Scenario 2）

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

### User Story 2 - 変更内容に基づくエージェント自動選択 (Priority: P1)

システムがレビュー対象（変更ファイルのパターン・差分内容）に基づいて、適用すべきエージェントを自動選択する。適用ルール（ApplicabilityRule）の条件評価により、関連するエージェントのみがレビューに参加する。

**Why this priority**: エージェント選択は基本レビュー実行（US1）の中核ロジック。変更内容に無関係なエージェントを除外することで、レビューの精度と効率を保証する。

**Independent Test**: テスト用のファイルパスリストと差分内容をセレクターに渡し、適用ルールに基づいて正しいエージェントのみが選択されることで検証可能。

**Acceptance Scenarios**:

1. **Given** `always = true` の適用ルールを持つエージェントが定義されている, **When** 任意のレビュー対象に対してセレクターが実行される, **Then** そのエージェントは常に選択される
2. **Given** `file_patterns = ["*.py"]` の適用ルールを持つエージェントが定義されている, **When** Python ファイルが変更ファイルに含まれる, **Then** そのエージェントが選択される
3. **Given** `file_patterns = ["*.py"]` の適用ルールを持つエージェントが定義されている, **When** Python ファイルが変更ファイルに含まれない, **Then** そのエージェントは選択されない
4. **Given** `content_patterns = ["try:\\s*\\.+\\s*except"]` の適用ルールを持つエージェントが定義されている, **When** diff/PR モードで差分内容に try-except パターンが含まれる, **Then** そのエージェントが選択される
5. **Given** `content_patterns` の適用ルールを持つエージェントが定義されている, **When** file モードでファイル全体の内容が content_patterns に一致する, **Then** そのエージェントが選択される
6. **Given** `file_patterns` と `content_patterns` の両方を持つ適用ルールが定義されている, **When** いずれか一方の条件に一致する, **Then** そのエージェントが選択される（OR 条件）
7. **Given** `file_patterns` と `content_patterns` がともに空で `always = false` のエージェントが定義されている, **When** セレクターが実行される, **Then** そのエージェントは選択されない
8. **Given** 実行フェーズ（phase）が指定されたエージェントが複数存在する, **When** セレクターが実行される, **Then** 結果は phase 順（early → main → final）にソートされて返される

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
- エージェント定義の `file_patterns` や `content_patterns` が空リストの場合、そのルールは常に不一致として扱われる（`always = true` でない限りスキップ）（親仕様 Edge Cases）
- `content_patterns` に無効な正規表現が含まれる場合、定義読み込み時にバリデーションエラーが発生し、具体的なエラーメッセージが表示される
- `.hachimoku/agents/` に `.toml` 以外のファイルが存在する場合、それらは無視される
- ビルトインとカスタムの両方にエージェント定義が存在し、カスタム側がバリデーションエラーの場合、ビルトイン定義がそのまま使用される（上書きは成功したカスタム定義にのみ適用）
- `file_patterns` のパターンマッチングは fnmatch 互換のグロブパターンを使用する（`*`, `?`, `[seq]`, `[!seq]`）
- `content_patterns` のパターンマッチングは正規表現を使用する（Python `re` モジュール互換）
- `phase` フィールドが省略された場合、デフォルト値 `main` が適用される
- エージェント名に使用できる文字はアルファベット小文字・数字・ハイフンのみとする。これ以外の文字を含む名前はバリデーションエラーとなる
- `allowed_tools` フィールドが空リストの場合、エージェントはツールなしで実行される（有効な状態）
- 同じフェーズ内の複数エージェントの実行順序は名前の辞書順とする（決定的な順序を保証）

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

- **FR-AD-002**: システムは適用ルール（ApplicabilityRule）を評価し、レビュー対象に基づいてエージェントの適用可否を判定できなければならない。ApplicabilityRule は以下のフィールドを持つ:
  - `always`: 常時適用フラグ（デフォルト: false）。true の場合、他の条件に関わらず常に適用する
  - `file_patterns`: ファイル名パターンのリスト（fnmatch 互換グロブパターン）。マッチング対象はファイルパスのファイル名部分（basename）とする。変更ファイル（diff/PR モード）または指定ファイル（file モード）のファイル名に対してマッチングする
  - `content_patterns`: 差分内容パターンのリスト（Python `re` 互換正規表現）。差分内容（diff/PR モード）またはファイル全体の内容（file モード）に対してマッチングする

  条件評価ロジック: `always = true` → 常に適用。それ以外の場合、`file_patterns` と `content_patterns` のいずれか1つ以上にマッチすれば適用（OR 条件）。両方が空リストかつ `always = false` の場合は不適用

- **FR-AD-003**: システムはビルトインエージェント定義ファイルを Python パッケージ内にバンドルし、ローダーが常にアクセスできなければならない。ビルトイン定義はカスタム定義が存在しない場合のデフォルトとして機能する（親仕様 FR-003）

- **FR-AD-004**: システムはプロジェクト固有のカスタムエージェント定義を `.hachimoku/agents/` ディレクトリから読み込み、ビルトインエージェントと同等に扱えなければならない。カスタム定義がビルトイン定義と同名の場合、カスタム定義がビルトインを上書きする（親仕様 FR-011）

- **FR-AD-005**: システムは以下の6つのビルトインエージェントを TOML 定義ファイルとして標準提供しなければならない（親仕様 FR-014）:
  - **code-reviewer**: コード品質・バグ・ベストプラクティスのレビュー。出力スキーマ: `scored_issues`
  - **silent-failure-hunter**: サイレント障害・エラーハンドリング不備の検出。出力スキーマ: `severity_classified`
  - **pr-test-analyzer**: テストカバレッジの欠落・テスト品質の分析。出力スキーマ: `test_gap_assessment`
  - **type-design-analyzer**: 型設計・インターフェース設計の分析。出力スキーマ: `multi_dimensional_analysis`
  - **comment-analyzer**: コードコメントの正確性・品質の分析。出力スキーマ: `category_classification`
  - **code-simplifier**: コードの簡潔化・改善提案。出力スキーマ: `improvement_suggestions`

- **FR-AD-006**: システムはレビュー対象のファイルパスリストと差分/ファイル内容を受け取り、適用ルールに基づいて実行すべきエージェントを選択し、実行フェーズ順（early → main → final）でソートされたリストを返すセレクターを提供しなければならない（親仕様 FR-005）

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
- **ApplicabilityRule（適用ルール）**: エージェントをいつ適用するかを決定する条件セット。常時適用フラグ（always）、ファイルパターンリスト（file_patterns、fnmatch 互換グロブ）、コンテンツパターンリスト（content_patterns、Python re 互換正規表現）から構成される。条件は OR 評価（いずれか1つ以上にマッチで適用）
- **Phase（実行フェーズ）**: エージェントの実行順序を制御する列挙型。early（前処理的な分析）、main（メインの詳細レビュー）、final（最終的な総合分析）の3値。同フェーズ内のエージェントは名前の辞書順で実行される
- **AgentLoader（エージェントローダー）**: ビルトインとカスタムの TOML 定義ファイルを読み込み、バリデーションし、AgentDefinition モデルのリストを構築する処理。カスタム定義によるビルトイン上書きと部分失敗（不正な定義のスキップ）をサポートする
- **AgentSelector（エージェントセレクター）**: レビュー対象（ファイルパスリスト・差分/ファイル内容）を受け取り、各エージェントの ApplicabilityRule を評価して、適用すべきエージェントを Phase 順にソートして返す処理
- **LoadResult（読み込み結果）**: ローダーの処理結果を表現するモデル。正常に読み込まれた AgentDefinition のリストと、スキップされたエージェントのエラー情報リストを持つ。呼び出し元がエラー情報の表示方法を決定できる

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-AD-001**: 6つのビルトインエージェント定義ファイルがすべて正常に読み込まれ、AgentDefinition モデルとして構築される
- **SC-AD-002**: エージェント定義ファイルを `.hachimoku/agents/` に配置するだけで、コード変更なしにカスタムエージェントがレビューに参加できる（親仕様 SC-003 の実現基盤）
- **SC-AD-003**: ビルトインと同名のカスタム定義が存在する場合、カスタム定義がビルトインを100%上書きする
- **SC-AD-004**: 不正な TOML ファイルや必須フィールド欠損の定義ファイルが存在しても、正常な定義ファイルはすべて読み込まれる（部分失敗許容）
- **SC-AD-005**: セレクターが ApplicabilityRule に基づいてエージェントを正しく選択し、`always = true` のエージェントは常に選択される
- **SC-AD-006**: セレクターの結果がフェーズ順（early → main → final）でソートされ、同フェーズ内は名前の辞書順で返される
- **SC-AD-007**: `output_schema` フィールドの値が SCHEMA_REGISTRY に存在しない場合、定義読み込み時に明確なエラーが報告される

## Assumptions

- エージェント定義ファイルの TOML パースには Python 標準ライブラリ `tomllib`（Python 3.11+）を使用する。外部ライブラリの追加は不要
- ビルトイン6エージェントのシステムプロンプトの具体的な内容は、実装フェーズで各エージェントの専門領域に基づいて策定する。本仕様ではプロンプトの構造と配置方法を定義する
- ビルトインエージェント定義ファイルのパッケージ内配置には `importlib.resources` を使用する（Python 標準ライブラリ）
- `file_patterns` のマッチングは完全パスではなくファイル名部分に対して行う。ディレクトリパターン（例: `src/**/*.py`）のサポートは将来の拡張として検討する
- エージェント定義の `model` フィールドの値は文字列として保持し、実際のモデル解決は 005-review-engine が担当する。本仕様ではモデル名のバリデーション（存在確認等）は行わない
- `allowed_tools` フィールドの値は文字列リストとして保持し、実際のツール解決は 005-review-engine が担当する
