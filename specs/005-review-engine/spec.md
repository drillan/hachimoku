# Feature Specification: レビュー実行エンジン

**Feature Branch**: `005-review-engine`
**Created**: 2026-02-07
**Status**: Draft
**Input**: User description: "specs/README.md をもとに、specs/001-architecture-spec/spec.mdを親仕様とした 005-review-engine を策定してください"
**Parent Spec**: [001-architecture-spec](../001-architecture-spec/spec.md)
**Priority**: P1（基本レビュー実行に必須）
**Depends On**: [002-domain-models](../002-domain-models/spec.md), [003-agent-definition](../003-agent-definition/spec.md), [004-configuration](../004-configuration/spec.md)

## Clarifications

### Session 2026-02-10 (Issue #152)

- Q: 集約エージェント失敗時の挙動は？（フォールバック禁止原則との整合） → A: 集約失敗時は `ReviewReport.aggregated = None` のまま返し、エラー情報を ReviewReport に明示的に記録する。これはフォールバック（デフォルト値での処理続行）ではなく、オプショナルな enrichment ステップの結果が利用不可であることの明示的表現。エラーは隠蔽しない
- Q: AggregatedReport の統合 issues の型は？ → A: 既存の `ReviewIssue` を再利用する。集約エージェントは重複排除後の issues を同じ型で返す。新規型は導入しない
- Q: strengths（良い実装へのフィードバック）のデータ構造は？ → A: `list[str]` のシンプルな文字列リスト。各要素が1つのポジティブフィードバック。構造化モデルは導入しない
- Q: recommended_actions のデータ構造は？ → A: `RecommendedAction(description: str, priority: Priority)` のリスト。Priority enum（high/medium/low）を使用し、優先度順でソート表示可能にする
- Q: 集約エージェントへの入力範囲は？ → A: AgentSuccess と AgentTruncated の結果のみを渡す。AggregatedReport に `agent_failures: list[str]` を追加し、失敗エージェント名を記録する。集約結果のみを参照する消費者にもレビューの不完全性が伝わるようにする

### Session 2026-02-10 (Issue #159)

- SelectorOutput に `referenced_content: list[ReferencedContent]`（default=[]）を追加。diff 内で参照されている外部リソース（Issue body、ファイル内容、仕様書等）の取得結果を保持する
- `ReferencedContent` モデルを `_selector.py` に定義: `reference_type`（str）、`reference_id`（str）、`content`（str）
- `build_selector_context_section()` に `referenced_content` パラメータを追加。循環インポート回避のため `TYPE_CHECKING` ガードで `ReferencedContent` を型チェック時のみ import する
- 非空時に `### Referenced Content` サブセクションをレンダリング。各参照は `#### [type] id` + コードブロックで構造化
- セレクターの system_prompt に `### referenced_content` セクションを追加し、diff 内の参照検出・取得を指示する

### Session 2026-02-10 (Issue #148)

- SelectorOutput に 4 つのメタデータフィールドを追加する: `change_intent`（str, default=""）、`affected_files`（list[str], default=[]）、`relevant_conventions`（list[str], default=[]）、`issue_context`（str, default=""）。全フィールドにデフォルト値を設定し後方互換性を確保する
- FR-RE-002 に Step 5.5（セレクターメタデータ伝播）を追加: セレクターの分析結果をレビューエージェントの user_message にマークダウンセクションとして追記する。メタデータが全て空の場合は user_message を変更しない
- FR-RE-007 のユーザーメッセージにセレクターメタデータを含むことを明記
- `_instruction.py` に `build_selector_context_section()` を追加。`_selector.py` → `_instruction.py` の循環インポートを回避するため、SelectorOutput を受け取らず keyword-only パラメータで個別フィールドを受け取る
- セレクターの system_prompt を更新し、メタデータフィールド（変更意図・影響ファイル・関連規約・Issue コンテキスト）の出力を指示する

### Session 2026-02-07

- 親仕様 FR-001, FR-002, FR-004, FR-005, FR-006, FR-007, FR-013, FR-018, FR-022, FR-024 および US1, US2, US9 を本仕様で実現する
- README.md の依存関係に基づき、002（ドメインモデル）、003（エージェント定義）、004（設定）の3仕様に依存する
- エージェントの実行基盤として pydantic-ai を採用し、`output_type` による構造化出力制御を利用する（002-domain-models Clarification で確定）
- エージェント定義の `model` フィールドの値解決は本仕様の責務（003-agent-definition Assumptions で明記）
- エージェント定義の `allowed_tools` フィールドの値解決は本仕様の責務（003-agent-definition Assumptions で明記）
- 設定モデル（HachimokuConfig）からのエージェント個別設定（enabled/model/timeout/max_turns）の適用は本仕様の責務
- FR-004（出力スキーマによる型検証）のうち、スキーマ定義は 002-domain-models が担当し、pydantic-ai の `output_type` を通じた実行時バリデーションは本仕様が担当する（README.md スキーマ所属境界）
- レビュー対象の取得（git diff、PR 差分、ファイル読み込み）は本仕様のスコープに含む。ただし PR メタデータ取得の GitHub API 呼び出しは 008-github-integration との協調で実現する
- 終了コード 3（実行エラー: 全エージェント失敗）の判定は本仕様が担当する。終了コード 0/1/2 は 002-domain-models の Severity マッピングに基づく
- SIGINT/SIGTERM シグナルハンドリングは本仕様のスコープに含む
- `parallel` 設定のデフォルト値を `true`（並列実行）に変更する。LLM 呼び出しは I/O バウンドでありエージェント間の副作用もないため、並列実行がデフォルトとして適切。逐次実行が必要な場合は `--no-parallel` で切り替える。この変更は 004-configuration の FR-CF-002 のデフォルト値にも波及する
- Q: レビュー実行中の stderr 進捗表示の粒度は？ → A: エージェント単位の進捗表示とする。各エージェントの実行開始（エージェント名）・完了/失敗ステータス・全体完了サマリーを stderr に出力する。ターン数や経過時間のリアルタイム表示は行わない
- Q: diff モードの比較対象は具体的に何か？ → A: マージベースからの差分（`git merge-base base_branch HEAD` を起点とした diff）を使用する。これにより base_branch 上の他者のコミットが混入せず、PR の差分と同等の結果が得られる
- Q: エージェント読み込みエラー（LoadResult のスキップ情報）の伝達方法は？ → A: stderr に警告表示し、かつ ReviewReport にも記録する（併用）。ユーザーは実行中に定義エラーに気づけ、レポート内でも確認できる
- Q: 最大ターン数到達時の結果ステータスは？ → A: 新たな状態 AgentTruncated を追加する。成功でもタイムアウトでもない「切り詰め」状態として区別する。AgentTruncated はその時点までの部分的な結果（検出済み問題リスト）を保持する。ReviewSummary 計算時、AgentTruncated の問題は有効な結果として含める（AgentSuccess と同様に扱う）。この変更は 002-domain-models の AgentResult 判別共用体（3型 → 4型）に波及する
- Q: git/gh コマンドの実行方法は？ → A: 全ての git/gh コマンドは LLM エージェントが `allowed_tools` 経由で自律的に実行する。hachimoku 本体が subprocess でメカニカルに実行することはしない。LLM の判断で diff コマンドのオプションを変更する等の柔軟性を確保する。これにより DiffProvider はレビュー対象の「指示情報」（base_branch、モード等）を構築する役割に変わり、実際のコマンド実行はエージェントが行う
- Q: エージェント選択（AgentSelector）をツール自律実行とどう整合させるか？ → A: AgentSelector 自体を pydantic-ai エージェントとして実行する。セレクターエージェントは入力情報（PR番号 / base_branch / ファイルパス）と利用可能なエージェント定義一覧をプロンプトで受け取り、git/gh ツールでレビュー対象を調査した上で、実行すべきエージェントリストを構造化出力で返す。003-agent-definition の `file_patterns` / `content_patterns` はセレクターエージェントの判断ガイダンスとして機能する（メカニカルなパターンマッチングではなくなる）。この変更は 003-agent-definition の AgentSelector 設計に波及する
- Q: セレクターエージェントの allowed_tools の範囲は？ → A: 最小限とする。git/gh の読み取り系コマンドとファイル読み込みのみ。コード変更等の副作用を持つツールは除外する
- Q: diff/file が空の場合の検出タイミングは？ → A: セレクターエージェントの責務とする。セレクターがレビュー対象を調査した結果、差分が空やファイルが0件の場合は空のエージェントリストを返し、エンジンは空リストを受けて正常終了する（終了コード 0）
- Q: エージェントが使用できるツールのカタログと権限ポリシーは？ → A: カテゴリベースのツールカタログを定義する。利用可能なカテゴリは `git_read`（git 読み取り系コマンド）、`gh_read`（gh 読み取り系コマンド）、`file_read`（ファイル読み込み・ディレクトリ探索）の3種で、全て読み取り専用。書き込み系ツール（git commit/push、ファイル書き込み、gh pr comment 等）はカタログに含めない。エンジンがホワイトリストとしてガードレールを設け、TOML の `allowed_tools` で未登録のカテゴリ名を指定した場合はバリデーションエラーとする

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 逐次実行によるマルチエージェントレビュー (Priority: P1)

システムが設定とエージェント定義に基づいてレビュー対象を取得し、適用可能なエージェントを逐次実行して結果を ReviewReport に集約する。各エージェントは pydantic-ai を通じて LLM に問い合わせを行い、出力スキーマによる型検証を経て構造化された結果を返す。

**Why this priority**: これがレビューエンジンの根幹機能であり、エンジンとしての最小限の価値を提供する。逐次実行は並列実行の基盤でもあり、ここが動作しなければ何も始まらない。

**Independent Test**: テスト用のエージェント定義と差分データをエンジンに渡し、各エージェントがフェーズ順に逐次実行され、ReviewReport が生成されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 適用可能なエージェントが3つ存在し逐次実行モードが設定されている状態, **When** レビューを実行する, **Then** 3つのエージェントがフェーズ順（early → main → final）・同フェーズ内は名前辞書順で1つずつ実行され、全結果が ReviewReport に集約される
2. **Given** エージェント定義に `output_schema` が指定されている状態, **When** エージェントが実行される, **Then** pydantic-ai の `output_type` に対応するスキーマモデルが設定され、エージェントの出力が型検証される
3. **Given** エージェント定義に `allowed_tools` が指定されている状態, **When** エージェントが実行される, **Then** 指定されたツールのみがエージェントに許可される
4. **Given** 設定で `agents.code-reviewer.model = "haiku"` が指定されている状態, **When** code-reviewer エージェントが実行される, **Then** エージェント個別設定のモデル（haiku）が使用される
5. **Given** 設定で `agents.code-reviewer.enabled = false` が指定されている状態, **When** エージェント選択が行われる, **Then** code-reviewer は選択対象から除外される
6. **Given** エージェント個別設定にモデルが未指定の状態, **When** エージェントが実行される, **Then** グローバル設定の `model` 値が使用される

---

### User Story 2 - 個別エージェントの失敗許容と部分レポート生成 (Priority: P1)

個別エージェントがタイムアウト・実行エラー・出力スキーマ違反で失敗した場合でも、成功したエージェントの結果のみでレビューレポートを生成する。失敗情報は AgentError または AgentTimeout として記録され、レポートに含まれる。

**Why this priority**: 部分失敗許容はレビューエンジンの信頼性を担保する基盤機能であり、US1 と同等の優先度。外部 LLM に依存するエージェント実行では失敗が不可避であり、1つの失敗で全結果が失われることは許容できない。

**Independent Test**: 意図的にタイムアウトやエラーを発生させるテスト用エージェントを含めてレビューを実行し、成功したエージェントのみの結果でレポートが生成されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 3つのエージェントのうち1つがタイムアウトする状態, **When** レビューを実行する, **Then** タイムアウトしたエージェントは AgentTimeout として記録され、残り2つの成功結果で ReviewReport が生成される
2. **Given** 3つのエージェントのうち1つが実行エラーを返す状態, **When** レビューを実行する, **Then** エラーのエージェントは AgentError として記録され、残り2つの成功結果で ReviewReport が生成される
3. **Given** エージェントの出力がスキーマに準拠しない状態, **When** 出力の型検証が失敗する, **Then** 当該エージェントは AgentError として記録され（エラー情報にスキーマ違反の詳細を含む）、他のエージェント結果は正常に処理される
4. **Given** 全エージェントが失敗した状態, **When** レビューを実行する, **Then** 全失敗情報を含む ReviewReport が生成され、終了コード 3（実行エラー）として返される
5. **Given** エージェントごとのタイムアウト（秒数）と最大ターン数が設定されている状態, **When** エージェントがタイムアウト秒数を超過する, **Then** エージェントの実行が中断され AgentTimeout として記録される
6. **Given** エージェントごとの最大ターン数が設定されている状態, **When** エージェントのターン数が上限に達する, **Then** エージェントの実行がその時点の部分的な結果で終了し、AgentTruncated として記録される（検出済み問題は ReviewReport に含まれる）

---

### User Story 3 - 並列実行によるレビュー高速化 (Priority: P2)

開発者が並列実行オプション（`parallel = true`）を有効にした場合、同一フェーズ内のエージェントが同時に実行される。フェーズ間は依然として順序を保持する（early → main → final）。

**Why this priority**: 逐次実行（P1）が動作した後の自然な改善。CI/CD パイプラインでの実用性に直結する。

**Independent Test**: 並列オプション付きでレビューを実行し、同一フェーズ内のエージェントが並行して実行され、全体の所要時間が逐次実行より短いことで検証可能。

**Acceptance Scenarios**:

1. **Given** `parallel = true` が設定され、main フェーズに3つのエージェントが存在する状態, **When** レビューを実行する, **Then** 3つのエージェントが同時に実行され、フェーズ全体の所要時間が最も遅いエージェントの実行時間に近い値となる
2. **Given** `parallel = true` が設定され、early・main・final の3フェーズにエージェントが分散している状態, **When** レビューを実行する, **Then** early フェーズ完了後に main フェーズ、main フェーズ完了後に final フェーズが実行される（フェーズ間は順序保持）
3. **Given** 並列実行中に1つのエージェントが失敗する状態, **When** エラーが発生する, **Then** 他のエージェントは影響を受けず完了し、失敗したエージェントの情報が ReviewReport に含まれる
4. **Given** `parallel = false` が明示的に設定されている状態, **When** レビューを実行する, **Then** エージェントは逐次実行される

---

### User Story 4 - SIGINT/SIGTERM によるグレースフルシャットダウン (Priority: P2)

ユーザーが Ctrl+C（SIGINT）またはシステムが SIGTERM を送信した場合、実行中のエージェントを安全に停止し、それまでに完了したエージェントの結果を部分レポートとして出力する。

**Why this priority**: シグナルハンドリングはプロセスの安定性に直結するが、基本的なレビュー実行と部分失敗許容（P1）が動作してから取り組む。

**Independent Test**: レビュー実行中に SIGINT を送信し、完了済みエージェントの結果が部分レポートとして出力されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 逐次実行中に2番目のエージェントが実行中の状態, **When** SIGINT を受信する, **Then** 実行中のエージェントが停止され、1番目のエージェントの結果が部分レポートとして出力される
2. **Given** 並列実行中に複数のエージェントが実行中の状態, **When** SIGINT を受信する, **Then** 全実行中エージェントが停止され、停止前に完了していたエージェントの結果が部分レポートとして出力される
3. **Given** SIGINT を受信した状態, **When** シャットダウン処理が開始される, **Then** 3秒以内に全プロセスが終了する（親仕様 SC-007）
4. **Given** SIGTERM を受信した状態, **When** シャットダウン処理が開始される, **Then** SIGINT と同様のグレースフルシャットダウンが実行される

---

### User Story 5 - レビュー対象の取得と入力モード判別 (Priority: P1)

レビューエンジンが入力モード（diff / PR / file）に応じてレビュー指示情報を構築し、エージェントのプロンプトコンテキストとして提供する。エージェントは `allowed_tools`（git, gh, ファイル読み込み等）を使って、差分取得・ファイル読み込み・PR 情報取得を自律的に行う。

**Why this priority**: レビュー指示の構築はエージェント実行の前提であり、US1 と同等の優先度。指示がなければレビューは実行できない。

**Independent Test**: 各入力モード（diff / file / PR）でレビュー指示が正しく構築され、エージェントのプロンプトコンテキストに含まれることで検証可能。

**Acceptance Scenarios**:

1. **Given** Git リポジトリ内で diff モードが選択されている状態, **When** レビュー指示を構築する, **Then** `base_branch` 名とレビュー方針（マージベースからの差分レビュー）がプロンプトコンテキストに含まれ、エージェントが git ツールで差分を自律的に取得する
2. **Given** file モードでファイルパスが指定されている状態, **When** レビュー指示を構築する, **Then** ファイルパスリストがプロンプトコンテキストに含まれ、エージェントがファイル読み込みツールで内容を自律的に取得する
3. **Given** file モードでディレクトリが指定されている状態, **When** レビュー指示を構築する, **Then** ディレクトリパスがプロンプトコンテキストに含まれ、エージェントがツールで再帰的に探索する
4. **Given** file モードで glob パターンが指定されている状態, **When** レビュー指示を構築する, **Then** glob パターンがプロンプトコンテキストに含まれ、エージェントがツールでマッチするファイルを取得する
5. **Given** PR モードが選択されている状態, **When** レビュー指示を構築する, **Then** PR 番号がプロンプトコンテキストに含まれ、エージェントが gh/git ツールで PR 差分とメタデータを自律的に取得する

---

### User Story 6 - エージェント実行コンテキストの構築 (Priority: P1)

レビューエンジンがエージェント定義・設定・レビュー対象・オプションの情報を統合し、各エージェントの実行コンテキスト（システムプロンプト・ユーザーメッセージ・ツール設定・モデル設定）を構築する。`--issue` オプション指定時は Issue 番号がプロンプトコンテキストに含まれる。

**Why this priority**: 実行コンテキストの構築はエージェント実行（US1）の前処理であり、同等の優先度。

**Independent Test**: エージェント定義と設定から実行コンテキストを構築し、システムプロンプト・モデル・ツール・出力スキーマが正しく設定されることで検証可能。

**Acceptance Scenarios**:

1. **Given** エージェント定義のシステムプロンプトとレビュー対象がある状態, **When** 実行コンテキストを構築する, **Then** システムプロンプトとレビュー対象（差分/ファイル内容）を含むコンテキストが構築される
2. **Given** `--issue 122` オプションが指定されている状態, **When** 実行コンテキストを構築する, **Then** Issue 番号（122）がプロンプトコンテキストに含まれる
3. **Given** PR モードで PR メタデータが取得されている状態, **When** 実行コンテキストを構築する, **Then** PR のタイトル・ラベル・リンク Issue がエージェントのコンテキストに含まれる
4. **Given** エージェント個別設定でタイムアウトが上書きされている状態, **When** 実行コンテキストを構築する, **Then** エージェント固有のタイムアウト値が適用される
5. **Given** エージェント個別設定で最大ターン数が上書きされている状態, **When** 実行コンテキストを構築する, **Then** エージェント固有の最大ターン数が適用される

---

### User Story 7 - LLM ベースの結果集約 (Priority: P2, Issue #152)

レビューエンジンが全エージェントの実行結果を LLM ベースの集約エージェントに入力し、重複排除・統合された AggregatedReport を生成する。AggregatedReport には統合 issues、strengths（良い実装へのフィードバック）、recommended_actions（優先度付き対応推奨）が含まれる。

**Why this priority**: 基本的なレビュー実行（P1）が動作した後の品質向上機能。レビュー結果の実用性を大幅に向上させるが、集約なしでもレビュー自体は成立する。

**Independent Test**: 複数エージェントの結果（重複する指摘を含む）を集約エージェントに渡し、AggregatedReport が生成されることで検証可能。

**Acceptance Scenarios**:

1. **Given** 3つのエージェントが同一の問題を異なる表現で報告している状態, **When** 集約を実行する, **Then** 重複が排除され統合された issues リスト（`ReviewIssue`）が AggregatedReport に含まれる
2. **Given** レビュー対象に良い実装が含まれている状態, **When** 集約を実行する, **Then** strengths（`list[str]`）にポジティブフィードバックが含まれる
3. **Given** 複数の指摘が存在する状態, **When** 集約を実行する, **Then** recommended_actions に優先度付き（`Priority`）の対応推奨が含まれる
4. **Given** 一部のエージェントが失敗した状態, **When** 集約を実行する, **Then** AggregatedReport の `agent_failures` に失敗エージェント名が記録される
5. **Given** 集約エージェントがタイムアウトまたはエラーで失敗した状態, **When** 集約に失敗する, **Then** `ReviewReport.aggregated = None` のまま、エラー情報が ReviewReport に記録され、Step 9 までの通常レポートが返される
6. **Given** 設定で集約が無効化されている状態（`aggregation.enabled = false`）, **When** レビューを実行する, **Then** Step 9.5 がスキップされ `ReviewReport.aggregated = None` となる
7. **Given** 全エージェントが失敗し有効な結果が0件の状態, **When** 結果集約を行う, **Then** 集約ステップをスキップし `ReviewReport.aggregated = None` となる

---

### Edge Cases

- diff モードで Git リポジトリ外から実行した場合、明確なエラーメッセージとともに終了コード 4（入力エラー）で終了する
- 全エージェントが設定で無効化されている場合、セレクターエージェントに渡すエージェント定義一覧が空となるため、セレクターは空リストを返し正常終了する（終了コード 0）
- エージェント実行中に pydantic-ai が予期しない例外を送出した場合、当該エージェントは AgentError として記録され、他のエージェントの実行は継続する
- 並列実行中に複数のエージェントが同時にタイムアウトした場合、各エージェントが個別に AgentTimeout として記録される
- file モードでシンボリックリンクによる循環参照が検出された場合、当該リンクをスキップし警告メッセージを stderr に表示する（親仕様 Edge Cases）
- file モードで指定されたファイル数が `max_files_per_review` を超過した場合の確認処理は 006-cli-interface の責務とする。本仕様では受け取ったファイルリストをそのまま処理する
- タイムアウト設定が非常に短い値（例: 1秒）の場合でも、エージェント起動前のバリデーションは行わない。タイムアウトは設定モデルのバリデーション（004-configuration）で正の整数として検証済みである
- 同一フェーズ内の並列実行中に SIGINT を受信した場合、全並列エージェントにキャンセルが伝播される
- ReviewReport の ReviewSummary 計算時、AgentError・AgentTimeout のエージェントは問題数にカウントされない。最大重大度は AgentSuccess および AgentTruncated の結果のみから決定される
- diff モードで base_branch が存在しないブランチを指定している場合、明確なエラーメッセージとともに終了コード 4（入力エラー）で終了する
- エージェントの出力が空（問題なし）の場合、AgentSuccess として記録される（空の問題リストは有効な成功結果）
- セレクターエージェントが失敗した場合（タイムアウト・実行エラー・不正な出力）、レビュー実行は中断され、エラー情報とともに終了コード 3（実行エラー）が返される
- セレクターエージェントが空のエージェントリストを返した場合、適用可能なエージェントが0件の場合と同様に扱う（空の ReviewReport で正常終了、終了コード 0）
- エージェント定義（TOML）の `allowed_tools` にツールカタログに存在しないカテゴリ名が指定されている場合、FR-RE-016 のガードレールによりバリデーションエラーとなり、当該エージェントはレビュー実行から除外される
- SelectorDefinition の `allowed_tools` にツールカタログに存在しないカテゴリ名が指定されている場合、FR-RE-016 のガードレールにより例外が送出され、レビュー実行は中断される（終了コード 3）
- 集約エージェントが失敗した場合（タイムアウト・実行エラー・出力スキーマ違反）、`ReviewReport.aggregated = None` のまま、エラー情報を ReviewReport に記録する。終了コードには影響しない（Issue #152）
- 全エージェントが失敗し集約への入力（AgentSuccess / AgentTruncated）が0件の場合、集約ステップをスキップする。`ReviewReport.aggregated = None`（Issue #152）
- 設定で集約が無効化されている場合（`aggregation.enabled = false`）、Step 9.5 をスキップし `ReviewReport.aggregated = None`（Issue #152）
- SIGINT/SIGTERM 受信時に集約ステップが実行中の場合、集約をキャンセルし Step 9 までの結果で部分レポートを生成する（`aggregated = None`）（Issue #152）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-RE-001**: システムは入力モード（diff / PR / file）に応じてレビュー対象コンテンツを事前解決し、レビュー指示情報とともにエージェントのプロンプトコンテキストに埋め込まなければならない（親仕様 FR-001, Issue #129）。コンテンツの事前解決はエージェント実行前にエンジンが1回だけ行い、全エージェント（セレクター・レビュー）で共有する:
  - **diff モード**: エンジンが `git merge-base` + `git diff` で差分を取得し、`base_branch` 名とともにプロンプトコンテキストに埋め込む
  - **PR モード**: エンジンが `gh pr diff` で PR 差分を取得し、PR 番号とともにプロンプトコンテキストに埋め込む。PR メタデータ（タイトル・ラベル・リンク Issue）の取得はエージェントが `gh pr view` で自律的に行う
  - **file モード**: エンジンが `pathlib.Path.read_text()` でファイル内容を読み込み、ファイルパスリストとともにプロンプトコンテキストに埋め込む
  - コンテンツ解決に失敗した場合（git/gh エラー、ファイル不存在等）は `ContentResolveError` を送出し、終了コード 3（実行エラー）で終了する

- **FR-RE-002**: システムは以下の手順でエージェント実行パイプラインを構成しなければならない（親仕様 FR-002）:
  1. **設定解決**: 004-configuration の ConfigResolver から HachimokuConfig を取得する
  2. **エージェント読み込み**: 003-agent-definition の AgentLoader からエージェント定義リスト（LoadResult）を取得する。LoadResult にスキップされたエージェントのエラー情報が含まれる場合、stderr に警告を表示し、エラー情報を ReviewReport にも記録する
  3. **無効エージェント除外**: HachimokuConfig の `agents.<name>.enabled = false` のエージェントを除外する
  3.5. **コンテンツ事前解決**: 入力モード（diff / PR / file）に応じてレビュー対象コンテンツを事前解決する（Issue #129）。失敗時は `ContentResolveError` を送出し終了コード 3 で終了する
  4. **レビュー指示構築**: 事前解決されたコンテンツを含むレビュー指示情報を構築する
  5. **セレクター定義読み込み**: ビルトインの `selector.toml` から SelectorDefinition を読み込む。カスタムの `selector.toml`（`.hachimoku/agents/selector.toml`）が存在する場合はビルトインを上書きする
  6. **エージェント選択（セレクターエージェント）**: SelectorDefinition と SelectorConfig に基づいてセレクターエージェント（pydantic-ai エージェント）を構築・実行し、レビュー指示情報と利用可能なエージェント定義一覧を渡す。セレクターエージェントは SelectorDefinition.allowed_tools で許可されたツールでレビュー対象を調査し、実行すべきエージェントリストを構造化出力で返す。エージェント定義の `file_patterns` / `content_patterns` / `phase` はセレクターの判断ガイダンスとして提供される
  6.5. **セレクターメタデータ伝播**: セレクターエージェントの分析結果（変更意図・影響ファイル・関連規約・Issue コンテキスト・参照先コンテンツ）をレビューエージェント向けのユーザーメッセージに追記する。SelectorOutput の `change_intent`・`affected_files`・`relevant_conventions`・`issue_context`・`referenced_content` フィールドをマークダウンセクション化し、レビュー指示情報に結合する。`referenced_content` は diff 内で参照されている外部リソース（Issue body、ファイル内容等）の取得結果で、参照元と参照先の横断整合性チェックを可能にする（Issue #148, #159）。メタデータが全て空の場合はユーザーメッセージを変更しない
  7. **実行コンテキスト構築**: 選択された各エージェントに対して実行コンテキスト（モデル・ツール・プロンプト・タイムアウト・最大ターン数）を構築する
  8. **エージェント実行**: 逐次または並列でエージェントを実行する
  9. **結果集約**: 各エージェントの結果（AgentResult）を ReviewReport に集約する
  9.5. **LLM ベース集約（オプショナル）**: 設定で集約が有効（デフォルト: 有効）の場合、AggregatorDefinition（TOML 定義）に基づいて集約エージェント（pydantic-ai エージェント）を構築・実行する。AgentSuccess と AgentTruncated の結果のみを入力とし、重複排除・統合した AggregatedReport を生成する。集約エージェント失敗時は `ReviewReport.aggregated = None` のまま、エラー情報を ReviewReport に記録する（Issue #152）

- **FR-RE-003**: システムは個別エージェントの失敗（タイムアウト・実行エラー・出力スキーマ違反）を許容し、成功したエージェントの結果のみで ReviewReport を生成できなければならない（親仕様 FR-006）。失敗したエージェントは AgentError または AgentTimeout として ReviewReport に記録される。AgentTruncated（最大ターン数到達）は失敗ではなく、部分的な結果を持つ有効な状態として扱う

- **FR-RE-004**: システムはエージェントごとに以下の二段階のプロセス制御を提供しなければならない（親仕様 FR-007）:
  - **タイムアウト（秒数）**: エージェントの実行時間が設定値を超過した場合、実行を中断し AgentTimeout を記録する
  - **最大ターン数**: エージェントのターン数（LLM への問い合わせ回数）が設定値に達した場合、その時点までの部分的な結果で実行を終了し AgentTruncated を記録する。AgentTruncated は検出済み問題リストを保持し、ReviewSummary 計算時には有効な結果として含まれる（AgentSuccess と同様に扱う）。この状態は 002-domain-models の AgentResult 判別共用体に新たなバリアント（status="truncated"）として追加される

  タイムアウトと最大ターン数はそれぞれ以下の優先順で解決する（004-configuration FR-CF-002 のデフォルト値定義に準拠）:
  1. エージェント個別設定（`agents.<name>.timeout` / `agents.<name>.max_turns`）
  2. グローバル設定（`timeout` / `max_turns`）
  3. デフォルト値（`timeout: 300` / `max_turns: 10`、004-configuration で定義）

- **FR-RE-005**: システムは SIGINT/SIGTERM シグナルを受信した場合、以下のグレースフルシャットダウンを実行しなければならない（親仕様 FR-013）:
  1. 実行中のエージェントにキャンセルを通知する
  2. 完了済みエージェントの結果を収集する
  3. 完了済みの結果のみで ReviewReport（部分レポート）を生成する
  4. シャットダウン開始から3秒以内に全プロセスを終了する（親仕様 SC-007）

- **FR-RE-006**: システムはデフォルトで同一フェーズ内のエージェントを並列に実行しなければならない（`parallel = true` がデフォルト）。フェーズ間は順序を保持する（early → main → final）。`parallel = false` が明示的に設定された場合はフェーズ順かつ名前辞書順で逐次実行する

- **FR-RE-007**: システムは各エージェントの実行コンテキストを以下の情報から構築しなければならない:
  - **モデル**: エージェント個別設定 > グローバル設定 > デフォルト値の優先順で解決
  - **プロバイダー**: モデル名のプレフィックス（`claudecode:` / `anthropic:`）で決定する。Agent 構築直前に `resolve_model()` で pydantic-ai の `Model` オブジェクトに変換する。`claudecode:` プレフィックスは `ClaudeCodeModel`、`anthropic:` プレフィックスはモデル名文字列をそのまま使用する（Issue #125 で `provider` フィールド廃止、プレフィックスベースに統一）
  - **ツール**: エージェント定義の `allowed_tools` のカテゴリ名を ToolCatalog 経由で pydantic-ai ツールに解決（FR-RE-016）
  - **出力スキーマ**: エージェント定義の `output_schema` から SCHEMA_REGISTRY 経由で解決（002-domain-models）。pydantic-ai の `output_type` に設定する
  - **システムプロンプト**: エージェント定義の `system_prompt`
  - **ユーザーメッセージ**: レビュー指示情報（入力モード・base_branch/PR番号/ファイルパス等）+ オプションコンテキスト（`--issue` 番号）+ セレクターメタデータ（FR-RE-002 Step 5.5、Issue #148）。差分・ファイル内容・PR メタデータの実際の取得はエージェントが `allowed_tools` で自律的に行う
  - **タイムアウト**: FR-RE-004 の優先順で解決
  - **最大ターン数**: FR-RE-004 の優先順で解決

- **FR-RE-008**: システムは全エージェントの実行結果を ReviewReport に集約しなければならない。ReviewReport には以下を含む:
  - AgentResult のリスト（AgentSuccess / AgentTruncated / AgentError / AgentTimeout）
  - ReviewSummary（総問題数・最大重大度・総実行時間・総コスト情報）
  - 最大重大度は AgentSuccess および AgentTruncated の結果から決定する（AgentError・AgentTimeout は除外）
  - `aggregated: AggregatedReport | None`（LLM ベース集約の結果。集約が無効、スキップ、または失敗の場合は `None`）（Issue #152）

- **FR-RE-009**: システムは全エージェントが失敗した場合（ReviewReport 内に AgentSuccess と AgentTruncated がともに0件）、終了コード 3（実行エラー）を返さなければならない。1つ以上のエージェントが成功または切り詰め完了した場合は、002-domain-models の Severity マッピングに基づいて終了コード（0/1/2）を返す

- **FR-RE-010**: セレクターエージェントが空のエージェントリストを返した場合（レビュー対象が空、または適用可能なエージェントなし）、システムはレビューエージェント実行をスキップし、その旨を通知して正常終了しなければならない（終了コード 0）

- **FR-RE-011**: システムは `--issue <番号>` オプションが指定された場合、Issue 番号をエージェントのプロンプトコンテキストに含めなければならない（親仕様 FR-024）。エージェントが `gh` コマンド等で Issue 情報を自律的に取得することを期待する

- **FR-RE-012**: システムは PR モードにおいて、PR のタイトル・ラベル・リンク Issue をエージェントの追加コンテキストとして注入しなければならない（親仕様 FR-022）。PR の説明文（body）は注入しない

- **FR-RE-013**: システムは pydantic-ai の `output_type` にエージェント定義の `output_schema` に対応するスキーマモデルを設定し、エージェント出力の実行時バリデーションを行わなければならない（親仕様 FR-004 の実行時検証部分）。バリデーション失敗時は当該エージェントを AgentError として記録する

- **FR-RE-014**: システムはエージェント読み込み時のエラー情報（LoadResult のスキップ情報）を stderr に警告として表示し、かつ ReviewReport のメタデータにも記録しなければならない。これによりユーザーは実行中にカスタムエージェント定義のミスに気づけ、レポート内でも確認できる

- **FR-RE-015**: システムはレビュー実行中の進捗情報を stderr に出力しなければならない（親仕様 FR-018）。出力内容は以下の通り:
  - 各エージェントの実行開始時: エージェント名を表示
  - 各エージェントの完了時: 成功/失敗ステータスを表示
  - 全体完了時: 実行されたエージェント数・成功/失敗の内訳サマリーを表示

- **FR-RE-016**: システムは以下のツールカタログを定義し、全エージェント（セレクターエージェント・レビューエージェント）が使用できるツールをカテゴリベースで管理しなければならない:
  - **`git_read`**: git の読み取り系コマンド（diff, log, show, status, merge-base 等）。リポジトリの状態を変更するコマンドは含まない
  - **`gh_read`**: gh CLI の読み取り系コマンド（pr view, issue view, api での読み取りクエリ等）。PR コメント投稿等の副作用を持つコマンドは含まない
  - **`file_read`**: ファイル内容の読み込み、ディレクトリ一覧、glob パターンによるファイル検索。ファイルの書き込み・削除は含まない

  全カテゴリは読み取り専用であり、書き込み系ツール（git commit/push、ファイル書き込み、gh pr comment 等）はカタログに存在しない。

  エンジンは以下のガードレールを強制する:
  - エージェント定義（TOML）の `allowed_tools` および SelectorDefinition の `allowed_tools` に含まれるツール名をカタログに対してバリデーションする
  - カタログに存在しないツール名が指定された場合、レビューエージェント定義はバリデーションエラーとし LoadResult のエラー情報に記録する（FR-RE-014 と同様の伝達方法）。SelectorDefinition の場合は例外を送出する
  - カテゴリ名からそのカテゴリに属する個別の pydantic-ai ツールへのマッピングはエンジンが担当する

- **FR-RE-017**: システムは AggregatorDefinition モデルを提供しなければならない（Issue #152）。AggregatorDefinition は SelectorDefinition と同じアーキテクチャパターン（TOML 定義 → pydantic-ai エージェント構築 → 構造化出力）に従う:
  - `name: str`（`"aggregator"` 固定）
  - `description: str`（集約エージェントの説明）
  - `model: str | None`（使用する LLM モデル名。None の場合はグローバル設定を使用）
  - `system_prompt: str`（集約エージェントのシステムプロンプト）
  - ビルトインの `aggregator.toml` から読み込まれ、カスタムの `aggregator.toml`（`.hachimoku/agents/aggregator.toml`）で上書き可能
  - AggregatorDefinition は `allowed_tools` を持たない（集約エージェントはツールを使用せず、入力データのみから統合結果を生成する）

- **FR-RE-018**: システムは AggregatedReport モデルを提供しなければならない（Issue #152）。AggregatedReport は集約エージェントの構造化出力であり、以下のフィールドを持つ:
  - `issues: list[ReviewIssue]`（重複排除・統合された指摘リスト。既存の ReviewIssue を再利用）
  - `strengths: list[str]`（良い実装に対するポジティブフィードバック。各要素が1つのフィードバック）
  - `recommended_actions: list[RecommendedAction]`（優先度付き対応推奨。RecommendedAction は `description: str` と `priority: Priority` を持つ。Priority enum を使用）
  - `agent_failures: list[str]`（失敗したエージェント名のリスト。集約結果のみを参照する消費者にレビューの不完全性を通知する）

- **FR-RE-019**: システムは設定で LLM ベース集約の有効/無効を切替可能にしなければならない（Issue #152）。デフォルトは有効（`aggregation.enabled = true`）。無効の場合、FR-RE-002 Step 9.5 をスキップし `ReviewReport.aggregated = None` となる

- **FR-RE-020**: システムはビルトインの `aggregator.toml` を同梱しなければならない（Issue #152）。`aggregator.toml` は重複排除・strengths 抽出・recommended_actions 生成を指示するシステムプロンプトを含む。セレクターと同様にカスタム TOML で上書き可能

- **FR-RE-021**: 集約エージェント失敗時（タイムアウト・実行エラー・出力スキーマ違反）、システムは `ReviewReport.aggregated = None` のまま、エラー情報を ReviewReport に明示的に記録しなければならない（Issue #152）。レビューパイプライン全体はエラー終了せず、Step 9 までの通常の ReviewReport を返す。これはフォールバック（デフォルト値での処理続行）ではなく、オプショナルな enrichment ステップの結果が利用不可であることの明示的表現である

### Key Entities

- **ReviewEngine（レビューエンジン）**: レビュー実行パイプライン全体を統括する処理。設定解決・エージェント読み込み・選択・実行・結果集約の全工程を調整する。入力モード・設定・エージェント定義を受け取り、ReviewReport を返す
- **ReviewTarget（レビュー対象）**: レビュー対象の入力情報を抽象化したエンティティ。入力モード（diff / PR / file）と付随するパラメータ（base_branch / PR番号 / ファイルパス等）を保持する。ReviewInstructionBuilder がこのエンティティからエージェント向けのプロンプトコンテキスト（レビュー指示情報）を構築する。セレクターエージェントとレビューエージェントの両方に提供される
- **AgentRunner（エージェントランナー）**: 単一エージェントの実行を担当する処理。実行コンテキストを受け取り、pydantic-ai を通じてエージェントを実行し、AgentResult（AgentSuccess / AgentTruncated / AgentError / AgentTimeout）を返す。タイムアウトと最大ターン数の二段階制御を適用する
- **AgentExecutionContext（実行コンテキスト）**: 単一エージェントの実行に必要な全情報を統合したエンティティ。モデル名・許可ツール・出力スキーマ・システムプロンプト・ユーザーメッセージ・タイムアウト・最大ターン数を保持する。エージェント定義・設定・レビュー対象から構築される
- **SequentialExecutor（逐次エグゼキューター）**: エージェントをフェーズ順・名前辞書順で1つずつ実行する処理。SIGINT/SIGTERM 受信時は現在のエージェント実行後に停止する
- **ParallelExecutor（並列エグゼキューター）**: 同一フェーズ内のエージェントを並列に実行する処理。フェーズ間は順序を保持する。SIGINT/SIGTERM 受信時は全並列エージェントにキャンセルを伝播する
- **ReviewInstructionBuilder（レビュー指示構築）**: 入力モード（diff / PR / file）に応じてエージェントに渡すレビュー指示情報を構築する処理。diff モードでは base_branch 名とレビュー方針、PR モードでは PR 番号、file モードではファイルパスリストを含む指示を生成する。実際の差分取得・ファイル読み込み・PR 情報取得はエージェントが `allowed_tools` で自律的に行う
- **SelectorDefinition（セレクター定義）**: セレクターエージェントの TOML 定義情報。名前（`"selector"` 固定）、説明、モデル名、システムプロンプト、許可ツールカテゴリリストを保持する。ビルトインの `selector.toml` から読み込まれ、カスタムの `selector.toml` で上書き可能。AgentDefinition と同様のデータ駆動型アーキテクチャに従い、コード変更なしでセレクターのプロンプトやツール設定を変更可能（Issue #118）
- **SelectorAgent（セレクターエージェント）**: pydantic-ai エージェントとして実行されるエージェント選択処理。SelectorDefinition（TOML 定義）からシステムプロンプト・モデル・許可ツールを取得し、SelectorConfig（設定）によるオーバーライド（モデル・タイムアウト・ターン数）を適用する。レビュー指示情報と利用可能なエージェント定義一覧（名前・説明・適用ルール・フェーズ）をプロンプトで受け取り、SelectorDefinition.allowed_tools で許可されたツールでレビュー対象を調査した上で、実行すべきエージェント名のリストをフェーズ順で構造化出力として返す。003-agent-definition の `file_patterns` / `content_patterns` は判断ガイダンスとして機能する
- **ToolCatalog（ツールカタログ）**: エージェントに許可されるツールのカテゴリ定義と、カテゴリ名から pydantic-ai ツールオブジェクトへのマッピングを管理する処理。読み取り専用の3カテゴリ（`git_read`, `gh_read`, `file_read`）のみを登録する。エージェント定義の `allowed_tools` バリデーション（ガードレール）と、実行時のツール解決を担当する
- **AggregatorDefinition（集約エージェント定義）**: 集約エージェントの TOML 定義情報。SelectorDefinition と同じアーキテクチャパターンに従う。名前（`"aggregator"` 固定）、説明、モデル名、システムプロンプトを保持する。ビルトインの `aggregator.toml` から読み込まれ、カスタムの `aggregator.toml` で上書き可能。`allowed_tools` は持たない（Issue #152）
- **AggregatedReport（集約レポート）**: 集約エージェントの構造化出力。重複排除された `issues`（`ReviewIssue`）、`strengths`（`list[str]`）、優先度付き `recommended_actions`（`list[RecommendedAction]`）、`agent_failures`（`list[str]`）を含む（Issue #152）
- **RecommendedAction（推奨アクション）**: 集約エージェントが生成する対応推奨。`description: str`（推奨内容）と `priority: Priority`（high/medium/low）を持つ（Issue #152）

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-RE-001**: レビューコマンドの実行開始から結果出力完了まで、設定されたタイムアウト時間＋10秒以内に確実にプロセスが終了する（親仕様 SC-001）
- **SC-RE-002**: 6つのビルトインエージェントのうち少なくとも1つが正常完了すれば、ユーザーに有意味な ReviewReport が出力される（親仕様 SC-002）
- **SC-RE-003**: 並列実行モードでの全体所要時間が、最も遅いエージェントの実行時間＋オーバーヘッド10%以内に収まる（親仕様 SC-004）
- **SC-RE-004**: 個別エージェントの失敗率が50%を超えても、成功したエージェントの結果のみで ReviewReport が正常に生成される（親仕様 SC-006）
- **SC-RE-005**: SIGINT 受信後3秒以内に全プロセスが終了し、それまでの結果が部分レポートとして出力される（親仕様 SC-007）
- **SC-RE-006**: 全エージェントが失敗した場合に終了コード 3 が返され、少なくとも1つ成功した場合は Severity マッピングに基づく正しい終了コード（0/1/2）が返される
- **SC-RE-007**: エージェント個別設定（model / timeout / max_turns / enabled）が正しく適用され、グローバル設定より優先される
- **SC-RE-008**: pydantic-ai の `output_type` による出力バリデーションが全エージェントで正しく動作し、スキーマ違反は AgentError として検出される

## Assumptions

- エージェント実行基盤として pydantic-ai を採用する。`Agent` クラスの `run()` メソッドで LLM を呼び出し、`output_type` パラメータで構造化出力を制御する
- pydantic-ai はタイムアウト制御と最大ターン数の制御機能を提供する想定。pydantic-ai が直接サポートしない場合は、asyncio のタイムアウト機構で補完する
- 並列実行には Python の asyncio を使用する。各エージェント実行は非同期タスクとして実行され、`asyncio.gather()` 等で同時実行される
- レビュー対象コンテンツ（diff / PR 差分 / ファイル内容）はエンジンが subprocess（`asyncio.create_subprocess_exec`）で事前解決し、エージェントのプロンプトに埋め込む（Issue #129）。PR メタデータ取得等の補助的な情報取得は引き続きエージェントが `allowed_tools` 経由で自律的に実行する。`git` および `gh` コマンドがエンジン実行環境で利用可能であることを前提とする
- `allowed_tools` はカテゴリベース（`git_read`, `gh_read`, `file_read`）で定義される。各カテゴリに属する個別の pydantic-ai ツール（関数）の登録は実装の責務とする。カテゴリ内のツール構成は pydantic-ai のツール登録機構に依存する
- file モードでのファイル読み込み・ディレクトリ探索・循環参照検出もエージェントが `file_read` カテゴリのツールを通じて自律的に行う
- エージェントのコスト情報は pydantic-ai の実行結果から取得可能な場合に記録する（オプショナル）
