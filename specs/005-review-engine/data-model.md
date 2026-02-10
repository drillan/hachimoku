# Data Model: レビュー実行エンジン

**Feature**: 005-review-engine | **Date**: 2026-02-07

## 既存モデルへの変更

### ReviewReport（変更: load_errors フィールド追加）

**ファイル**: `src/hachimoku/models/report.py`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| results | `list[AgentResult]` | — | エージェント実行結果リスト |
| summary | `ReviewSummary` | — | レビューサマリー |
| **load_errors** | `tuple[LoadError, ...]` | `()` | エージェント読み込みエラー（FR-RE-014） |
| **aggregated** | `AggregatedReport \| None` | `None` | LLM ベース集約の結果（FR-RE-008, Issue #152） |
| **aggregation_error** | `str \| None` | `None` | 集約エージェント失敗時のエラー情報（FR-RE-021, Issue #152） |

**変更理由**: FR-RE-014 により、LoadResult のスキップ情報を ReviewReport にも記録する。Issue #152 により、LLM ベース集約結果とエラー情報のフィールドを追加。

## 新規モデル

### ReviewMode（入力モード列挙型）

**ファイル**: `src/hachimoku/engine/_target.py`

```python
class ReviewMode(StrEnum):
    DIFF = "diff"
    PR = "pr"
    FILE = "file"
```

### ReviewTarget（レビュー対象）

**ファイル**: `src/hachimoku/engine/_target.py`

入力モードと付随パラメータを保持する判別共用体。

| Variant | Fields | Description |
|---------|--------|-------------|
| DiffTarget | `mode: Literal["diff"]`, `base_branch: str` | diff モード。マージベースからの差分 |
| PRTarget | `mode: Literal["pr"]`, `pr_number: int` | PR モード。PR 番号を指定 |
| FileTarget | `mode: Literal["file"]`, `paths: tuple[str, ...]` | file モード。ファイルパス/ディレクトリ/glob |

共通フィールド:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| issue_number | `int \| None` | `None` | `--issue` オプションの Issue 番号（FR-RE-011） |

```python
ReviewTarget = Annotated[
    Union[DiffTarget, PRTarget, FileTarget],
    Field(discriminator="mode"),
]
```

### AgentExecutionContext（実行コンテキスト）

**ファイル**: `src/hachimoku/engine/_context.py`

単一エージェントの実行に必要な全情報を統合した immutable モデル。

| Field | Type | Description |
|-------|------|-------------|
| agent_name | `str` | エージェント名 |
| model | `str` | 解決済みモデル名（個別設定 > グローバル > デフォルト） |
| system_prompt | `str` | エージェント定義のシステムプロンプト |
| user_message | `str` | レビュー指示情報 + オプションコンテキスト |
| output_schema | `type[BaseAgentOutput]` | 解決済み出力スキーマクラス |
| tools | `tuple[pydantic_ai.Tool[None], ...]` | 解決済み pydantic-ai ツールリスト（deps 未使用のため `Tool[None]`） |
| timeout_seconds | `int` | タイムアウト秒数 |
| max_turns | `int` | 最大ターン数（UsageLimits.request_limit に変換） |
| phase | `Phase` | 実行フェーズ |

### SelectorDefinition（セレクター定義）

**ファイル**: `src/hachimoku/agents/models.py`

セレクターエージェントの TOML 定義。レビューエージェントの `AgentDefinition` と同様に
TOML ファイルから構築される。ビルトインの `selector.toml` から読み込まれる。

| Field | Type | Description |
|-------|------|-------------|
| name | `str` | セレクター名（`"selector"` 固定） |
| description | `str` | セレクターの説明 |
| model | `str` | 使用する LLM モデル名 |
| system_prompt | `str` | セレクターのシステムプロンプト |
| allowed_tools | `tuple[str, ...]` | 許可するツールカテゴリ（デフォルト: 全3カテゴリ） |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）
- `AgentDefinition` とは異なり、`output_schema`・`phase`・`applicability` を持たない。セレクターの出力は `SelectorOutput` に固定され、フェーズ・適用条件の概念はない

### ReferencedContent（参照先コンテンツ）

**ファイル**: `src/hachimoku/engine/_selector.py`（Issue #159）

diff 内で参照されている外部リソースの取得結果。

| Field | Type | Description |
|-------|------|-------------|
| reference_type | `str` | 参照の種類（"issue", "file", "spec" 等） |
| reference_id | `str` | 参照識別子（例: "#152", "src/foo.py"） |
| content | `str` | 取得した参照先の内容テキスト |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）

### SelectorOutput（セレクター出力）

**ファイル**: `src/hachimoku/engine/_selector.py`

セレクターエージェントの構造化出力。

| Field | Type | Description |
|-------|------|-------------|
| selected_agents | `list[str]` | 実行すべきエージェント名リスト |
| reasoning | `str` | 選択理由（デバッグ用） |
| change_intent | `str` | 変更の意図・目的の要約（default=""）（Issue #148） |
| affected_files | `list[str]` | diff 外で影響を受けるファイルパス（default=[]）（Issue #148） |
| relevant_conventions | `list[str]` | 関連プロジェクト規約（default=[]）（Issue #148） |
| issue_context | `str` | Issue 関連情報の要約（default=""）（Issue #148） |
| referenced_content | `list[ReferencedContent]` | diff 内参照先の取得結果（default=[]）（Issue #159） |

### AggregatorDefinition（集約エージェント定義）

**ファイル**: `src/hachimoku/agents/models.py`

集約エージェントの TOML 定義。SelectorDefinition と同じアーキテクチャパターンに従う。
ビルトインの `aggregator.toml` から読み込まれる。（Issue #152）

| Field | Type | Description |
|-------|------|-------------|
| name | `str` | 集約エージェント名（`"aggregator"` 固定） |
| description | `str` | 集約エージェントの説明 |
| model | `str \| None` | 使用する LLM モデル名（None の場合はグローバル設定を使用） |
| system_prompt | `str` | 集約エージェントのシステムプロンプト |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）
- SelectorDefinition と異なり、`allowed_tools` を持たない（集約エージェントはツール不使用）
- 出力は `AggregatedReport` に固定

### AggregatedReport（集約レポート）

**ファイル**: `src/hachimoku/models/report.py`

集約エージェントの構造化出力。（Issue #152）

| Field | Type | Description |
|-------|------|-------------|
| issues | `list[ReviewIssue]` | 重複排除・統合された指摘リスト |
| strengths | `list[str]` | 良い実装に対するポジティブフィードバック |
| recommended_actions | `list[RecommendedAction]` | 優先度付き対応推奨 |
| agent_failures | `list[str]` | 失敗したエージェント名リスト（不完全性の通知用） |

### RecommendedAction（推奨アクション）

**ファイル**: `src/hachimoku/models/report.py`

集約エージェントが生成する対応推奨。（Issue #152）

| Field | Type | Description |
|-------|------|-------------|
| description | `str` | 推奨アクションの内容 |
| priority | `Priority` | 優先度（high/medium/low）。Priority enum を使用 |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）

### EngineResult（エンジン実行結果）

**ファイル**: `src/hachimoku/engine/_engine.py`

ReviewEngine の実行結果。ReviewReport と終了コードを含む。

| Field | Type | Description |
|-------|------|-------------|
| report | `ReviewReport` | レビューレポート |
| exit_code | `Literal[0, 1, 2, 3]` | 終了コード（0=成功, 1=Critical, 2=Important, 3=実行エラー） |

## エンティティ関係図

```text
ReviewEngine
  │
  ├── HachimokuConfig ─────── (004-configuration から取得)
  │     ├── model, timeout, max_turns, parallel, base_branch
  │     ├── selector: SelectorConfig
  │     └── agents: dict[str, AgentConfig]
  │
  ├── LoadResult ──────────── (003-agent-definition から取得)
  │     ├── agents: tuple[AgentDefinition, ...]
  │     └── errors: tuple[LoadError, ...]
  │
  ├── ReviewTarget ─────────── (CLI 入力から構築)
  │     ├── DiffTarget(base_branch)
  │     ├── PRTarget(pr_number)
  │     └── FileTarget(paths)
  │
  ├── ToolCatalog ──────────── (カテゴリ→ツール解決)
  │     └── resolve(categories) → list[Tool]
  │
  ├── ReviewInstructionBuilder
  │     └── build(target) → str (ユーザーメッセージ)
  │
  ├── SelectorDefinition ──── (TOML 定義から読み込み)
  │     └── name, description, model, system_prompt, allowed_tools
  │
  ├── SelectorAgent ─────────── (エージェント選択)
  │     ├── input: instructions + agent_definitions + SelectorDefinition
  │     └── output: SelectorOutput(selected_agents, reasoning)
  │
  ├── AgentExecutionContext ──── (per agent)
  │     ├── model, system_prompt, user_message
  │     ├── output_schema, tools
  │     └── timeout_seconds, max_turns, phase
  │
  ├── Executor
  │     ├── SequentialExecutor
  │     └── ParallelExecutor
  │
  ├── AgentRunner ────────────── (per agent execution)
  │     ├── input: AgentExecutionContext
  │     └── output: AgentResult
  │
  ├── AggregatorDefinition ──── (TOML 定義から読み込み, Issue #152)
  │     └── name, description, model, system_prompt
  │
  ├── AggregatedReport ─────── (集約エージェント出力, Issue #152)
  │     ├── issues: list[ReviewIssue]
  │     ├── strengths: list[str]
  │     ├── recommended_actions: list[RecommendedAction]
  │     └── agent_failures: list[str]
  │
  └── EngineResult
        ├── report: ReviewReport (aggregated: AggregatedReport | None)
        └── exit_code: int
```

## 設定値の解決フロー

```text
AgentDefinition.model ──┐
AgentConfig.model ──────┤  ← 個別設定が最優先
HachimokuConfig.model ──┤  ← グローバル設定
(default: "claudecode:claude-opus-4-6") ────┘  ← HachimokuConfig のデフォルト値

同様に timeout, max_turns も解決:
  AgentConfig.X > HachimokuConfig.X > HachimokuConfig デフォルト値

セレクターのモデル解決:
  SelectorConfig.model > SelectorDefinition.model > HachimokuConfig.model > default("claudecode:claude-opus-4-6")

セレクターの allowed_tools:
  SelectorDefinition.allowed_tools のみ（SelectorConfig からは削除済み）

セレクターの timeout, max_turns:
  SelectorConfig.X > HachimokuConfig.X > HachimokuConfig デフォルト値

集約エージェントのモデル解決 (Issue #152):
  AggregationConfig.model > AggregatorDefinition.model > HachimokuConfig.model > default("claudecode:claude-opus-4-6")

集約の timeout, max_turns (Issue #152):
  AggregationConfig.X > HachimokuConfig.X > HachimokuConfig デフォルト値

集約の有効/無効 (Issue #152):
  aggregation.enabled (default: true)
```

## 状態遷移

### エージェント実行結果の状態

```text
Agent実行開始
  │
  ├── 正常完了 ──────────────→ AgentSuccess(issues, elapsed_time, cost)
  │
  ├── ターン数上限到達 ──────→ AgentTruncated(issues, elapsed_time, turns_consumed)
  │     (UsageLimitExceeded)
  │
  ├── タイムアウト ──────────→ AgentTimeout(timeout_seconds)
  │     (asyncio.TimeoutError)
  │
  └── 実行エラー ────────────→ AgentError(error_message)
        (その他の例外)
```

### レビューパイプラインの状態

```text
Start
  │
  ├── 設定解決 ──── (resolve_config)
  ├── エージェント読み込み ──── (load_agents)
  ├── 無効エージェント除外 ──── (enabled=false を除外)
  ├── レビュー指示構築 ──── (ReviewInstructionBuilder)
  ├── セレクターエージェント実行
  │     ├── 成功 → selected_agents リスト
  │     ├── 空リスト → 正常終了 (exit_code=0)
  │     └── 失敗 → 異常終了 (exit_code=3)
  ├── 実行コンテキスト構築 ──── (per agent)
  ├── エージェント実行 ──── (Sequential or Parallel)
  │     └── SIGINT/SIGTERM → グレースフルシャットダウン
  ├── 結果集約 ──── (ReviewReport)
  ├── LLM ベース集約 ──── (Step 9.5, Issue #152)
  │     ├── 集約有効 + 有効結果あり → AggregatedReport
  │     ├── 集約有効 + 有効結果0件 → スキップ (aggregated=None)
  │     ├── 集約有効 + 失敗 → aggregated=None, エラー記録
  │     ├── 集約無効 → スキップ (aggregated=None)
  │     └── SIGINT/SIGTERM → キャンセル (aggregated=None)
  └── 終了コード判定
        ├── 全失敗 → exit_code=3
        └── 1つ以上成功 → determine_exit_code(max_severity)
```
