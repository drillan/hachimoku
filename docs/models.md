# ドメインモデル

hachimoku のドメインモデルは `hachimoku.models` パッケージで定義されています。
全モデルは Pydantic v2 ベースで、型検証と厳格なバリデーション（追加フィールド禁止）を提供します。

```{contents}
:depth: 2
:local:
```

## Severity（重大度）

レビュー問題の深刻度を4段階で表現する列挙型です。

| 値 | 説明 |
|----|------|
| Critical | 重大な問題。修正必須 |
| Important | 重要な問題。修正を推奨 |
| Suggestion | 改善の提案 |
| Nitpick | 些細な指摘 |

順序関係: `Critical > Important > Suggestion > Nitpick`

ReviewIssue の severity フィールドでは、大文字小文字を区別せずに入力を受け付けます（`"critical"`, `"CRITICAL"`, `"Critical"` いずれも有効）。

(tool-category)=
## ToolCategory（ツールカテゴリ）

エージェントに許可されるツールの種類を定義する列挙型（StrEnum）です。
読み取り専用の4カテゴリで構成されます。

| 値 | 文字列値 | 説明 |
|----|---------|------|
| `GIT_READ` | `"git_read"` | Git 読み取り操作（diff, log, show, status 等） |
| `GH_READ` | `"gh_read"` | GitHub CLI 読み取り操作（pr view, issue view 等） |
| `FILE_READ` | `"file_read"` | ファイル読み取り操作（read, ls 等） |
| `WEB_FETCH` | `"web_fetch"` | Web コンテンツ取得操作 |

```{code-block} python
from hachimoku.models import ToolCategory

cat = ToolCategory.GIT_READ
assert cat == "git_read"
```

## FileLocation（ファイル位置）

レビュー問題が検出されたファイル内の位置を表します。

| フィールド | 型 | 制約 |
|-----------|---|------|
| `file_path` | `str` | 空文字列不可 |
| `line_number` | `int` | 1以上 |

```{code-block} python
from hachimoku.models import FileLocation

loc = FileLocation(file_path="src/main.py", line_number=42)
```

## ReviewIssue（レビュー問題）

各エージェントが検出した問題の統一表現です。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `agent_name` | `str` | Yes | 空文字列不可 |
| `severity` | `Severity` | Yes | 大文字小文字非依存 |
| `description` | `str` | Yes | 空文字列不可 |
| `location` | `FileLocation \| None` | No | デフォルト `None` |
| `suggestion` | `str \| None` | No | デフォルト `None` |
| `category` | `str \| None` | No | デフォルト `None` |

```{code-block} python
from hachimoku.models import ReviewIssue, Severity

issue = ReviewIssue(
    agent_name="code-reviewer",
    severity=Severity.IMPORTANT,
    description="Unused variable detected",
    suggestion="Remove the variable or use it",
)
```

## CostInfo（コスト情報）

LLM 実行のトークン消費量とコストを記録します。

| フィールド | 型 | 制約 |
|-----------|---|------|
| `input_tokens` | `int` | 0以上 |
| `output_tokens` | `int` | 0以上 |
| `total_cost` | `float` | 0.0以上 |

## AgentResult（エージェント結果）

単一エージェントの実行結果を表す判別共用体（Discriminated Union）です。
`status` フィールドの値により、以下の4つの型が自動選択されます。

### AgentSuccess

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `status` | `Literal["success"]` | Yes | 固定値 `"success"` |
| `agent_name` | `str` | Yes | 空文字列不可 |
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `elapsed_time` | `float` | Yes | 正の値（0は不可） |
| `cost` | `CostInfo \| None` | No | デフォルト `None` |

### AgentTruncated

最大ターン数に到達した場合の部分的な結果を保持します。
ReviewSummary 計算時には AgentSuccess と同様に有効な結果として扱います。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `status` | `Literal["truncated"]` | Yes | 固定値 `"truncated"` |
| `agent_name` | `str` | Yes | 空文字列不可 |
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `elapsed_time` | `float` | Yes | 正の値（0は不可） |
| `turns_consumed` | `int` | Yes | 正の値（0は不可） |

### AgentError

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `status` | `Literal["error"]` | Yes | 固定値 `"error"` |
| `agent_name` | `str` | Yes | 空文字列不可 |
| `error_message` | `str` | Yes | 空文字列不可 |
| `exit_code` | `int \| None` | No | CLI プロセス終了コード。デフォルト `None` |
| `error_type` | `str \| None` | No | 構造化エラー種別。空文字列不可。デフォルト `None` |
| `stderr` | `str \| None` | No | 標準エラー出力。デフォルト `None` |

### AgentTimeout

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `status` | `Literal["timeout"]` | Yes | 固定値 `"timeout"` |
| `agent_name` | `str` | Yes | 空文字列不可 |
| `timeout_seconds` | `float` | Yes | 正の値（0は不可） |

### デシリアライズ例

```{code-block} python
from pydantic import TypeAdapter
from hachimoku.models import AgentResult, AgentSuccess

adapter = TypeAdapter(AgentResult)

# status フィールドで型が自動選択される
result = adapter.validate_python({
    "status": "success",
    "agent_name": "code-reviewer",
    "issues": [],
    "elapsed_time": 2.5,
})
assert isinstance(result, AgentSuccess)
```

## ReviewSummary（レビューサマリー）

レビュー結果の全体サマリーです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `total_issues` | `int` | Yes | 0以上 |
| `max_severity` | `Severity \| None` | Yes | 問題なしの場合 `None` |
| `total_elapsed_time` | `float` | Yes | 0.0以上 |
| `total_cost` | `CostInfo \| None` | No | デフォルト `None` |

## Priority（推奨アクション優先度）

推奨アクションの優先度を3段階で表現する列挙型です。
Severity（問題重大度）とは別の概念で、RecommendedAction で使用されます。

| 値 | 説明 |
|----|------|
| `HIGH` | 高優先度 |
| `MEDIUM` | 中優先度 |
| `LOW` | 低優先度 |

## RecommendedAction（推奨アクション）

集約エージェントが生成する推奨アクションです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `description` | `str` | Yes | 空文字列不可 |
| `priority` | `Priority` | Yes | - |

## AggregatedReport（集約レポート）

LLM ベース集約エージェントの構造化出力です。
重複排除された指摘、ポジティブフィードバック、推奨アクション、失敗エージェント情報を含みます。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容。重複排除・統合済み |
| `strengths` | `list[str]` | Yes | 空リスト許容 |
| `recommended_actions` | `list[RecommendedAction]` | Yes | 空リスト許容 |
| `agent_failures` | `list[str]` | Yes | 失敗エージェント名。空リスト許容 |

## ReviewReport（レビューレポート）

全エージェントの結果を集約したレポートです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `results` | `list[AgentResult]` | Yes | 空リスト許容 |
| `summary` | `ReviewSummary` | Yes | - |
| `load_errors` | `tuple[`[LoadError](load-error)`, ...]` | No | デフォルト空タプル |
| `aggregated` | `AggregatedReport \| None` | No | デフォルト `None`。集約なし/無効/失敗 |
| `aggregation_error` | `str \| None` | No | デフォルト `None`。集約失敗時のエラー情報 |

`load_errors` はエージェント定義の読み込み時に発生したエラーを保持します。
全エージェントが失敗した場合でも空の `results` でレポートを生成できます。

`aggregated` は LLM ベース集約（Step 9.5）の結果です。集約が無効、または失敗した場合は `None` となり、失敗時は `aggregation_error` にエラー情報が設定されます。

```{code-block} python
from hachimoku.models import ReviewReport, ReviewSummary

report = ReviewReport(
    results=[],
    summary=ReviewSummary(
        total_issues=0,
        max_severity=None,
        total_elapsed_time=0.0,
    ),
)
```

## レビュー履歴レコード

レビュー結果を JSONL 形式で永続化するためのレコードモデルです。
`review_mode` フィールドの値で型が自動選択される判別共用体として定義されています。

### CommitHash

Git コミットハッシュの型エイリアスです。40文字の16進小文字文字列に制約されます。

```{code-block} python
from hachimoku.models import CommitHash
from pydantic import TypeAdapter

adapter = TypeAdapter(CommitHash)
hash_value = adapter.validate_python("a" * 40)  # 有効
```

### DiffReviewRecord

diff モードのレビュー履歴レコードです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `review_mode` | `Literal["diff"]` | Yes | 固定値 `"diff"` |
| `commit_hash` | `CommitHash` | Yes | 40文字の16進小文字 |
| `branch_name` | `str` | Yes | 空文字列不可 |
| `reviewed_at` | `datetime` | Yes | - |
| `results` | `list[AgentResult]` | Yes | - |
| `summary` | `ReviewSummary` | Yes | - |

### PRReviewRecord

PR モードのレビュー履歴レコードです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `review_mode` | `Literal["pr"]` | Yes | 固定値 `"pr"` |
| `commit_hash` | `CommitHash` | Yes | 40文字の16進小文字 |
| `pr_number` | `int` | Yes | 1以上 |
| `branch_name` | `str` | Yes | 空文字列不可 |
| `reviewed_at` | `datetime` | Yes | - |
| `results` | `list[AgentResult]` | Yes | - |
| `summary` | `ReviewSummary` | Yes | - |

### FileReviewRecord

file モードのレビュー履歴レコードです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `review_mode` | `Literal["file"]` | Yes | 固定値 `"file"` |
| `file_paths` | `frozenset[str]` | Yes | 1要素以上、各要素非空 |
| `reviewed_at` | `datetime` | Yes | - |
| `working_directory` | `str` | Yes | 絶対パス |
| `results` | `list[AgentResult]` | Yes | - |
| `summary` | `ReviewSummary` | Yes | - |

### デシリアライズ例

```{code-block} python
from pydantic import TypeAdapter
from hachimoku.models import ReviewHistoryRecord, DiffReviewRecord

adapter = TypeAdapter(ReviewHistoryRecord)

# review_mode フィールドで型が自動選択される
record = adapter.validate_python({
    "review_mode": "diff",
    "commit_hash": "a" * 40,
    "branch_name": "feature/example",
    "reviewed_at": "2026-01-01T00:00:00",
    "results": [],
    "summary": {
        "total_issues": 0,
        "max_severity": None,
        "total_elapsed_time": 0.0,
    },
})
assert isinstance(record, DiffReviewRecord)
```

(output-schemas)=
## 出力スキーマ

エージェントの出力形式を規定するスキーマです。全スキーマは `BaseAgentOutput` を継承し、共通属性として `issues: list[ReviewIssue]` を持ちます。

### BaseAgentOutput（出力ベースモデル）

全出力スキーマの共通ベースモデルです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |

### ScoredIssues（スコア付き問題）

数値スコアとレビュー問題を組み合わせた出力スキーマです。code-reviewer 等が使用します。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `overall_score` | `float` | Yes | 0.0 以上 10.0 以下 |

```{code-block} python
from hachimoku.models import ScoredIssues, ReviewIssue, Severity

scored = ScoredIssues(
    issues=[
        ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.IMPORTANT,
            description="Missing error handling",
        ),
    ],
    overall_score=7.5,
)
```

### SeverityClassified（重大度分類問題）

重大度別に分類された問題リストを持つ出力スキーマです。silent-failure-hunter 等が使用します。

`issues` フィールドは4つの分類リストから自動導出されます。入力時は4つの分類リストのみを指定します。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `critical_issues` | `list[ReviewIssue]` | Yes | - |
| `important_issues` | `list[ReviewIssue]` | Yes | - |
| `suggestion_issues` | `list[ReviewIssue]` | Yes | - |
| `nitpick_issues` | `list[ReviewIssue]` | Yes | - |
| `issues` | `list[ReviewIssue]` | - | 自動導出（読み取り専用） |

```{code-block} python
from hachimoku.models import SeverityClassified, ReviewIssue, Severity

classified = SeverityClassified(
    critical_issues=[
        ReviewIssue(
            agent_name="silent-failure-hunter",
            severity=Severity.CRITICAL,
            description="Silent exception swallowed",
        ),
    ],
    important_issues=[],
    suggestion_issues=[],
    nitpick_issues=[],
)

# issues は4リストの結合から自動導出される
assert len(classified.issues) == 1
```

### TestGapAssessment（テストギャップ評価）

テストカバレッジの欠落を評価する出力スキーマです。pr-test-analyzer が使用します。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `coverage_gaps` | `list[CoverageGap]` | Yes | 空リスト許容 |
| `risk_level` | `Severity` | Yes | - |

CoverageGap は以下のフィールドを持ちます。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `file_path` | `str` | Yes | 空文字列不可 |
| `description` | `str` | Yes | 空文字列不可 |
| `priority` | `Severity` | Yes | - |

### MultiDimensionalAnalysis（多次元分析）

複数の評価軸でスコアリングする出力スキーマです。type-design-analyzer が使用します。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `dimensions` | `list[DimensionScore]` | Yes | 空リスト許容 |

DimensionScore は以下のフィールドを持ちます。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `name` | `str` | Yes | 空文字列不可 |
| `score` | `float` | Yes | 0.0 以上 10.0 以下 |
| `description` | `str` | Yes | 空文字列不可 |

### CategoryClassification（カテゴリ分類）

カテゴリ別に問題を分類する出力スキーマです。comment-analyzer が使用します。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `categories` | `dict[str, list[ReviewIssue]]` | Yes | 空辞書許容 |

### ImprovementSuggestions（改善提案）

具体的な改善提案のリストを提供する出力スキーマです。code-simplifier が使用します。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `suggestions` | `list[ImprovementItem]` | Yes | 空リスト許容 |

ImprovementItem は以下のフィールドを持ちます。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `title` | `str` | Yes | 空文字列不可 |
| `description` | `str` | Yes | 空文字列不可 |
| `priority` | `Severity` | Yes | - |
| `location` | `FileLocation \| None` | No | デフォルト `None` |

(schema-registry)=
## SCHEMA_REGISTRY（スキーマレジストリ）

スキーマ名から対応するスキーマクラスを解決するレジストリです。エージェント定義ファイルの `output_schema` フィールドからスキーマを特定する際に使用します。

登録済みスキーマ:

| 名前 | スキーマクラス |
|------|-------------|
| `scored_issues` | `ScoredIssues` |
| `severity_classified` | `SeverityClassified` |
| `test_gap_assessment` | `TestGapAssessment` |
| `multi_dimensional_analysis` | `MultiDimensionalAnalysis` |
| `category_classification` | `CategoryClassification` |
| `improvement_suggestions` | `ImprovementSuggestions` |

```{code-block} python
from hachimoku.models import get_schema, ScoredIssues

schema_cls = get_schema("scored_issues")
assert schema_cls is ScoredIssues
```

未登録のスキーマ名を指定すると `SchemaNotFoundError` が発生します。`register_schema` で新しいスキーマを追加登録でき、同名のスキーマを重複登録すると `DuplicateSchemaError` が発生します。
