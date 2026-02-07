# Research: レビュー実行エンジン

**Feature**: 005-review-engine | **Date**: 2026-02-07

## R-001: ターン数制御メカニズム（pydantic-ai + claudecode-model）

**背景**: 仕様では `max_turns`（最大ターン数）でエージェント実行を制御し、到達時は AgentTruncated として記録する。pydantic-ai と claudecode-model の両方で制御メカニズムを調査。

**調査結果**:

1. **pydantic-ai**: `max_turns` パラメータは存在しない。`UsageLimits(request_limit=N)` でモデルリクエスト数を制限。制限超過時は `UsageLimitExceeded` 例外を送出
2. **claudecode-model**: `ClaudeCodeModel` コンストラクタが `max_turns: int | None` パラメータを直接サポート。`model_settings` 辞書経由でも渡せる（`model_settings={"max_turns": N}`）。内部で `claude_agent_sdk.ClaudeAgentOptions.max_turns` に渡される

**Decision**: 二重経路で制御する

**Rationale**:
- **pydantic-ai 層**: `UsageLimits(request_limit=N)` を `agent.run()` に渡す。これにより pydantic-ai フレームワークレベルでターン数が制限される。超過時は `UsageLimitExceeded` 例外 → AgentTruncated に変換
- **モデル層**: `ModelSettings` に `max_turns` を含めて渡す。ClaudeCodeModel 使用時は claude_agent_sdk 側でもターン数が制限される

二重経路にすることで、ClaudeCodeModel 以外のモデル（OpenAI、Anthropic 直接等）でも `UsageLimits` による制御が機能し、ClaudeCodeModel 使用時はさらに SDK レベルの制御も加わる。

**Alternatives considered**:
- pydantic-ai の `UsageLimits` のみ → ClaudeCodeModel 固有の最適化（SDK レベルの早期停止）を活用できない
- claudecode-model の `max_turns` のみ → 他のモデルプロバイダーで動作しない
- pydantic-ai の `agent.iter()` を使ったノード単位の手動制御 → 実装が複雑になり、pydantic-ai の内部構造への依存が増す

## R-002: エージェント全体のタイムアウト制御

**背景**: 仕様では `timeout`（秒数）でエージェント実行全体の時間を制限する。pydantic-ai の `ModelSettings.timeout` は HTTP リクエスト単位のタイムアウトであり、エージェント全体（複数ターンを含む）のタイムアウトではない。

**Decision**: `asyncio.timeout(seconds)` でエージェント全体の実行をラップする

**Rationale**: `ModelSettings.timeout` は個別の LLM API 呼び出しのタイムアウトであり、マルチターンエージェントの全体実行時間を制御するものではない。`asyncio.timeout()` (Python 3.11+) でエージェントの `run()` 呼び出し全体をラップし、`asyncio.TimeoutError` を catch して AgentTimeout に変換する。これは仕様の Assumptions にも「pydantic-ai が直接サポートしない場合は、asyncio のタイムアウト機構で補完する」と明記されている。

**Alternatives considered**:
- `ModelSettings.timeout` のみ → 個別リクエストのタイムアウトであり、全体時間の制御にはならない
- signal.alarm → asyncio と相性が悪く、並列実行時に複数タイマーが干渉する

## R-003: AgentTruncated の部分結果取得方法

**背景**: `UsageLimitExceeded` 例外発生時、それまでのターンで検出された部分的な結果（ReviewIssue リスト）を取得する必要がある。

**Decision**: `UsageLimitExceeded` 例外の属性またはメッセージ履歴から部分結果を復元する

**Rationale**: pydantic-ai の `UsageLimitExceeded` は `AgentRunError` のサブクラスで、例外発生時のメッセージ履歴にアクセスできる可能性がある。ただし、構造化出力（`output_type`）の部分結果は LLM がまだ最終応答を返していないため直接取得できない可能性が高い。実装上は以下の戦略を採用する:

1. **ツール呼び出し履歴からの復元**: エージェントがツールを使って段階的に問題を検出している場合、ツール呼び出しの戻り値から部分情報を抽出できる可能性がある
2. **空の結果での Truncated 記録**: 部分結果の取得が技術的に困難な場合、AgentTruncated は空の issues リストで記録する。仕様上「検出済み問題リストを保持する」とあるが、0件も有効なリストである
3. **pydantic-ai の `agent.iter()` を用いた段階的実行**: ノードごとに実行を進め、各ステップで中間結果を蓄積する方式。request_limit の代替として検討に値するが、実装複雑度が高い

最終的なアプローチは実装フェーズで pydantic-ai の実際の動作を検証して確定する。

**Alternatives considered**:
- 全ターンの出力を独自にバッファリング → pydantic-ai のツール呼び出しフローに介入が必要で複雑
- 部分結果を諦めて AgentError 扱い → 仕様に AgentTruncated が明記されているため不適切

## R-004: pydantic-ai ツール登録と ToolCatalog の設計

**背景**: エージェントの `allowed_tools` はカテゴリベース（git_read, gh_read, file_read）で定義される。カテゴリから pydantic-ai ツール関数群へのマッピングが必要。

**Decision**: `ToolCatalog` クラスがカテゴリ名から `list[Tool]` へのマッピングを管理し、`Agent` コンストラクタの `tools=` 引数にフラットなリストとして渡す

**Rationale**: pydantic-ai のツール登録は `Agent(tools=[...])` でコンストラクタ時に行う。各ツールは `Tool(func, takes_ctx=bool)` でラップするか、関数をそのまま渡せる。ToolCatalog は以下の責務を持つ:

1. **カテゴリ→ツール解決**: `resolve(categories: Sequence[str]) -> list[Tool]`
2. **バリデーション**: `validate(categories: Sequence[str]) -> list[str]`（不正カテゴリ名を返す）
3. **ツール定義**: 各カテゴリに属するツール関数は `_tools/` パッケージで定義

ツール関数は `subprocess` で git/gh/ファイル操作コマンドを実行する。pydantic-ai の `Tool` として登録することで、LLM が自律的にコマンドを選択・実行できる。

**ToolCategory enum との関係（二重バリデーションの明確化）**:
- 003-agent-definition の `AgentDefinition.allowed_tools` は `tuple[str, ...]`（文字列タプル）であり、`ToolCategory` enum で型バリデーションされていない
- 004-configuration の `SelectorConfig.allowed_tools` は `list[ToolCategory]` で ToolCategory enum バリデーション済み
- ToolCatalog のバリデーションは **AgentDefinition（003）側の文字列ツール名** を検証する役割。003 は汎用的な文字列を受け入れ、005 のエンジンがカタログに照合して不正なカテゴリを検出する。これは二重チェックではなく、**レイヤー間の責務分離**（003=構文検証、005=意味検証）

**Alternatives considered**:
- `@agent.tool` デコレータ → エージェントインスタンスごとにデコレータを適用する必要があり、動的なツール構成に不向き
- Toolset（pydantic-ai 組み込み） → カテゴリベースの動的選択には過剰で、シンプルなリストで十分

## R-005: ツール関数の設計（git_read / gh_read / file_read）

**背景**: 各ツールカテゴリに属する具体的なツール関数を設計する。LLM エージェントがこれらのツールを使ってレビュー対象を自律的に調査する。

**Decision**: カテゴリごとに汎用的なコマンド実行ツールを提供する

**Rationale**: 個別コマンドごとにツール（`git_diff`, `git_log`, `git_show` ...）を定義すると、ツール数が膨大になり LLM のツール選択コストが増大する。代わりに、各カテゴリで1-2個の汎用ツールを提供する:

- **git_read**: `run_git(args: list[str]) -> str` — 読み取り系 git コマンドを実行。許可されたサブコマンド（diff, log, show, status, merge-base, rev-parse, branch, ls-files）のホワイトリストで検証
- **gh_read**: `run_gh(args: list[str]) -> str` — 読み取り系 gh コマンドを実行。許可されたサブコマンド（pr view, issue view, api）のホワイトリストで検証
- **file_read**: `read_file(path: str) -> str` + `list_directory(path: str, pattern: str | None) -> str` — ファイル読み込みとディレクトリ一覧

ホワイトリスト検証により、書き込み系コマンド（git commit, gh pr comment 等）の実行を防止する。

**Alternatives considered**:
- コマンドごとに個別ツール → ツール数爆発、LLM のコンテキスト圧迫
- 完全自由なシェル実行 → セキュリティリスク。ホワイトリストによるガードレールが必要

## R-006: セレクターエージェントの出力スキーマ

**背景**: セレクターエージェントは実行すべきエージェント名のリストを構造化出力で返す。出力スキーマの設計が必要。

**Decision**: `SelectorOutput` Pydantic モデルを定義し、`output_type` として使用する

**Rationale**:

```python
class SelectorOutput(BaseModel):
    selected_agents: list[str]  # エージェント名のリスト（フェーズ順）
    reasoning: str              # 選択理由（デバッグ・監査用）
```

セレクターエージェントは:
1. レビュー指示情報（モード・パラメータ）を受け取る
2. 利用可能なエージェント定義一覧（名前・説明・適用ルール・フェーズ）を受け取る
3. git/gh ツールでレビュー対象を調査する
4. 実行すべきエージェント名リストを返す

`selected_agents` の各名前はエンジンが利用可能なエージェント定義と照合し、不明な名前はエラーとして無視する。

**Alternatives considered**:
- エージェント名だけでなくフェーズも返す → フェーズは AgentDefinition に既に含まれているため冗長
- 選択理由なし → デバッグ時に選択根拠が不明になる

## R-007: 並列実行の設計（asyncio.TaskGroup）

**背景**: 同一フェーズ内のエージェントを並列実行し、フェーズ間は順序を保持する。

**Decision**: Python 3.11+ の `asyncio.TaskGroup` を使用する

**Rationale**: `asyncio.TaskGroup` は構造化並行性（Structured Concurrency）を提供し、タスクグループ内の例外が適切に伝播される。`asyncio.gather(return_exceptions=True)` と比較して:

- キャンセル伝播が自動的に行われる（SIGINT 対応に有利）
- コンテキストマネージャで明確なスコープを持つ
- Python 3.13 で安定しており、フレームワーク推奨の方法

ただし、`TaskGroup` はデフォルトで1つのタスクが例外を送出すると他のタスクもキャンセルされる。個別エージェントの失敗許容のために、各タスク内で例外を catch して AgentResult に変換する必要がある。

```python
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(_run_agent_safe(ctx)) for ctx in phase_contexts]
# _run_agent_safe は内部で例外を catch し AgentResult を返す
```

**Alternatives considered**:
- `asyncio.gather(return_exceptions=True)` → 例外が値として返され型安全性が低い。キャンセル伝播も手動
- `concurrent.futures.ThreadPoolExecutor` → asyncio エコシステムとの整合性が低い

## R-008: SIGINT/SIGTERM ハンドリング

**背景**: シグナル受信時に実行中エージェントを安全に停止し、完了済み結果で部分レポートを生成する。3秒以内に全プロセス終了。

**Decision**: `asyncio` のシグナルハンドラと `asyncio.Event` を組み合わせる

**Rationale**:

1. `loop.add_signal_handler(signal.SIGINT, handler)` でシグナルを捕捉
2. `asyncio.Event` (`shutdown_event`) をセットし、実行ループにキャンセルを通知
3. 並列実行中は `TaskGroup` のキャンセルにより全タスクが停止
4. 逐次実行中は次のエージェント実行前に `shutdown_event` をチェック
5. 3秒タイムアウト: `asyncio.wait_for(cleanup(), timeout=3.0)` で強制終了

**Alternatives considered**:
- `signal.signal()` → asyncio イベントループとの統合が難しい
- `KeyboardInterrupt` の catch → SIGTERM をカバーしない

## R-009: ReviewReport への load_errors フィールド追加

**背景**: FR-RE-014 により、エージェント読み込みエラー（LoadResult のスキップ情報）を ReviewReport にも記録する必要がある。

**Decision**: ReviewReport に `load_errors: tuple[LoadError, ...]` フィールドを追加する

**Rationale**: 既存の ReviewReport モデルを直接修正する（Art.8 リファクタリングポリシー準拠）。LoadError は 003-agent-definition で定義済みの型であり、そのまま再利用する。

```python
class ReviewReport(HachimokuBaseModel):
    results: list[AgentResult]
    summary: ReviewSummary
    load_errors: tuple[LoadError, ...] = ()  # 追加
```

**Alternatives considered**:
- メタデータ辞書に格納 → 型安全性が低い
- 新しい ReviewReportV2 モデル → Art.8 でバージョン付きクラス作成禁止

## R-010: モデル名の解決戦略

**背景**: HachimokuConfig の `model` フィールドには "sonnet" のような短縮名が使われる。pydantic-ai は "anthropic:claude-sonnet-4-5" 形式を期待する。Clarifications に「エージェント定義の `model` フィールドの値解決は本仕様の責務」と明記されている。

**Decision**: 本仕様は「値の受け渡し」（設定優先順に基づくモデル名の決定と pydantic-ai への引き渡し）を担当する。エイリアス変換（短縮名→完全修飾名）は本仕様のスコープに含めない

**Rationale**: Clarifications の「値解決」は、エージェント個別設定 > グローバル設定 > デフォルト値の優先順でモデル名を決定し、AgentExecutionContext に設定する責務を指す（FR-RE-004, FR-RE-007 に対応）。一方、文字列レベルの変換（"sonnet" → "anthropic:claude-sonnet-4-5"）はモデル名体系の設計に依存し、pydantic-ai や claudecode-model のモデル名解決機構に委ねる。pydantic-ai は `Agent(model=...)` にモデル名文字列を直接受け付け、不正な名前は実行時エラーとなる。

**本仕様が担当する「値解決」**:
1. エージェント個別設定のモデル名があればそれを使用
2. なければグローバル設定のモデル名を使用
3. 決定されたモデル名をそのまま pydantic-ai Agent に渡す

**本仕様が担当しない部分**:
- エイリアスマッピング（"sonnet" → "anthropic:claude-sonnet-4-5"）
- モデル名のバリデーション（pydantic-ai 側で実行時に行われる）

**Alternatives considered**:
- エイリアスマッピング辞書を実装 → 仕様にマッピング定義がなく、スコープクリープ
- 設定で完全なモデル名を強制 → ユーザビリティ低下

## R-011: コスト情報の取得

**背景**: AgentSuccess には `cost: CostInfo | None` フィールドがある。pydantic-ai からコスト情報を取得する方法の調査。

**Decision**: `result.usage()` からトークン数を取得し、CostInfo に変換する

**Rationale**: pydantic-ai には `result.cost()` メソッドは存在しない。`result.usage()` で `RunUsage` オブジェクトを取得でき、`input_tokens`, `output_tokens`, `requests` 等のフィールドがある。CostInfo（002-domain-models で定義済み）への変換:

```python
CostInfo(
    input_tokens=usage.input_tokens,
    output_tokens=usage.output_tokens,
    total_cost=None,  # 金額計算は別途対応
)
```

金額ベースのコスト計算は仕様で「オプショナル」とされているため、トークン数のみ記録する。

**Alternatives considered**:
- genai-prices ライブラリ → 追加依存。MVP では不要
- Logfire 連携 → 監視インフラ。MVP では不要
