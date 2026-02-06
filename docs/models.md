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

Pydantic モデルのフィールドとして使用する場合、大文字小文字を区別せずに入力を受け付けます（`"critical"`, `"CRITICAL"`, `"Critical"` いずれも有効）。

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
`status` フィールドの値により、以下の3つの型が自動選択されます。

### AgentSuccess

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `status` | `Literal["success"]` | Yes | 固定値 `"success"` |
| `agent_name` | `str` | Yes | 空文字列不可 |
| `issues` | `list[ReviewIssue]` | Yes | 空リスト許容 |
| `elapsed_time` | `float` | Yes | 正の値（0は不可） |
| `cost` | `CostInfo \| None` | No | デフォルト `None` |

### AgentError

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `status` | `Literal["error"]` | Yes | 固定値 `"error"` |
| `agent_name` | `str` | Yes | 空文字列不可 |
| `error_message` | `str` | Yes | 空文字列不可 |

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

## ReviewReport（レビューレポート）

全エージェントの結果を集約したレポートです。

| フィールド | 型 | 必須 | 制約 |
|-----------|---|------|------|
| `results` | `list[AgentResult]` | Yes | 空リスト許容 |
| `summary` | `ReviewSummary` | Yes | - |

全エージェントが失敗した場合でも空の `results` でレポートを生成できます。

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
