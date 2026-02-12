# エージェント定義

hachimoku のレビューエージェントは TOML ファイルで定義されます。
コード変更なしにエージェントの追加・カスタマイズが可能なデータ駆動型アーキテクチャを採用しています。
6つのビルトインエージェントを標準提供し、プロジェクト固有のカスタムエージェントも追加できます。

```{contents}
:depth: 2
:local:
```

## ビルトインエージェント

以下の6つのエージェントがパッケージに同梱されています。

| エージェント名 | 説明 | 出力スキーマ | フェーズ | 適用条件 |
|---------------|------|-------------|---------|---------|
| code-reviewer | コード品質・バグ検出 | scored_issues | main | 常時適用 |
| silent-failure-hunter | サイレント障害の検出 | severity_classified | main | content_patterns |
| pr-test-analyzer | テストカバレッジの評価 | test_gap_assessment | main | file_patterns |
| type-design-analyzer | 型アノテーション・型安全性の実用分析 | multi_dimensional_analysis | main | file_patterns + content_patterns |
| comment-analyzer | コメントの正確性分析 | category_classification | final | content_patterns |
| code-simplifier | コード簡潔化の提案 | improvement_suggestions | final | 常時適用 |

出力スキーマの詳細は [出力スキーマ](output-schemas) を参照してください。

(selector-definition)=
## セレクターエージェント

セレクターエージェントは、レビュー対象を分析して実行すべきレビューエージェントを選択する専用エージェントです。
レビューエージェントと同様に TOML 定義ファイルで構成情報を管理します。

### SelectorDefinition

| フィールド | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `name` | `str` | Yes | セレクター名（`"selector"` 固定） |
| `description` | `str` | Yes | セレクターの説明 |
| `model` | `str` | Yes | 使用する LLM モデル名 |
| `system_prompt` | `str` | Yes | セレクターのシステムプロンプト |
| `allowed_tools` | `list[str]` | No | 許可するツールカテゴリ。デフォルト: 全3カテゴリ |

レビューエージェントの `AgentDefinition` とは異なり、`output_schema`・`phase`・`applicability` フィールドはありません。
セレクターの出力は常に `SelectorOutput`（選択されたエージェント名リストと理由）に固定されます。

### モデル解決の優先順位

セレクターエージェントのモデルは以下の優先順位で解決されます:

1. `[selector]` 設定の `model`（[設定](configuration.md) 参照）
2. セレクター定義の `model`
3. グローバル設定の `model`（デフォルト: `"claudecode:claude-opus-4-6"`）

### ビルトインセレクター定義

パッケージにはビルトインの `selector.toml` が同梱されています。
カスタムの `selector.toml` を `.hachimoku/agents/selector.toml` に配置すると、ビルトインを上書きできます。

```{code-block} toml
:caption: selector.toml（ビルトイン）

name = "selector"
description = "レビュー対象を分析し、実行すべきレビューエージェントを選択する"
model = "claudecode:claude-haiku-4-5"
allowed_tools = ["git_read", "gh_read", "file_read"]
system_prompt = """
You are an agent selector for code review.
Your task is to analyze the review target and select the most applicable
review agents from the available list.

## Workflow

1. Identify changed files and their types using the provided tools:
   - For diff mode: run git commands to list changed files
   - For PR mode: use gh commands to get PR metadata and changed files
   - For file mode: read the specified file paths

2. Analyze the changes:
   - Determine file types and languages involved
   - Check for patterns in the diff (error handling, type definitions, tests, etc.)
   - Consider the scope and nature of the changes

3. Select agents based on applicability:
   - Always include agents with `always=true` applicability
   - Include agents whose `file_patterns` match any changed file (basename match)
   - Include agents whose `content_patterns` match any content in the diff
   - Consider the agent's `phase` for execution ordering

4. Return selected agent names ordered by phase (early → main → final),
   and provide reasoning for your selection.

## Selection Guidelines

- Prefer including an agent over excluding it when uncertain
- An empty selection is valid when no agents are applicable
  (e.g., no meaningful changes to review)
- Use file_patterns and content_patterns as guidance, not strict rules;
  the LLM's judgment can override mechanical pattern matching
"""
```

### load_selector()

ビルトインのセレクター定義を読み込みます。カスタム定義が存在する場合はそちらを使用します。

```{code-block} python
from hachimoku.agents import load_selector

definition = load_selector()
print(definition.name)  # "selector"
```

## TOML 定義ファイル形式

エージェント定義は以下の形式の TOML ファイルで記述します。

```{code-block} toml
name = "code-reviewer"
description = "コード品質・バグ・ベストプラクティスの総合レビュー"
model = "anthropic:claude-opus-4-6"
output_schema = "scored_issues"
phase = "main"
allowed_tools = ["git_read", "gh_read", "file_read"]
system_prompt = """
You are code-reviewer, an expert code quality analyst. Analyze code changes
for bugs, security issues, and best practice violations.

## Review Methodology
1. Use run_git(["diff", "--name-only"]) to list changed files.
2. Use read_file(path) to read surrounding context.
3. Check for bugs, security vulnerabilities, and performance concerns.
...
"""

[applicability]
always = true
```

### フィールド一覧

| フィールド | 型 | 必須 | 説明 |
|-----------|---|------|------|
| `name` | `str` | Yes | エージェント名。アルファベット小文字・数字・ハイフンのみ（`^[a-z0-9-]+$`） |
| `description` | `str` | Yes | エージェントの説明 |
| `model` | `str` | Yes | 使用する LLM モデル名 |
| `output_schema` | `str` | Yes | [SCHEMA_REGISTRY](schema-registry) に登録されたスキーマ名 |
| `system_prompt` | `str` | Yes | エージェントのシステムプロンプト |
| `allowed_tools` | `list[str]` | No | 許可するツールカテゴリのリスト。デフォルト: 空 |
| `phase` | `str` | No | 実行フェーズ。デフォルト: `"main"` |

`[applicability]` テーブル:

| フィールド | 型 | デフォルト | 説明 |
|-----------|---|----------|------|
| `always` | `bool` | `false` | 常時適用フラグ |
| `file_patterns` | `list[str]` | `[]` | fnmatch パターンのリスト |
| `content_patterns` | `list[str]` | `[]` | 正規表現パターンのリスト |

`[applicability]` テーブルを省略した場合、`always = true` がデフォルトとして適用されます。

## Phase（実行フェーズ）

エージェントの実行順序を制御するフェーズです。
エージェントはフェーズ順に実行され、同フェーズ内では名前の辞書順で実行されます。

| 値 | 実行順序 | 説明 |
|----|---------|------|
| `early` | 0 | 前処理フェーズ |
| `main` | 1 | メインレビューフェーズ |
| `final` | 2 | 後処理フェーズ |

```{code-block} python
from hachimoku.agents import Phase, PHASE_ORDER

assert PHASE_ORDER[Phase.EARLY] < PHASE_ORDER[Phase.MAIN] < PHASE_ORDER[Phase.FINAL]
```

## ApplicabilityRule（適用条件）

エージェントがレビュー対象に適用されるかどうかを判定する条件です。

条件評価ロジック:

1. `always = true` の場合、常に適用
2. `file_patterns` のいずれかにファイル名（basename）がマッチすれば適用
3. `content_patterns` のいずれかにコンテンツがマッチすれば適用
4. 上記いずれも該当しなければ不適用

`file_patterns` と `content_patterns` は OR 関係です。

### ビルトインエージェントの適用条件

| エージェント | 条件 | パターン |
|------------|------|---------|
| code-reviewer | `always = true` | - |
| silent-failure-hunter | content_patterns | `try\s*:`, `except\s`, `catch\s*\(`, `\.catch\s*\(` |
| pr-test-analyzer | file_patterns | `test_*.py`, `*_test.py`, `*.test.ts`, `*.test.js`, `*.spec.ts`, `*.spec.js` |
| type-design-analyzer | file_patterns + content_patterns | ファイル: `*.py`, `*.ts`, `*.tsx` / コンテンツ: `class\s+\w+`, `interface\s+\w+`, `type\s+\w+\s*=` |
| comment-analyzer | content_patterns | `"""`, `'''`, `/\*\*`, `//\s*TODO`, `#\s*TODO` |
| code-simplifier | `always = true` | - |

(load-error)=
## LoadError（読み込みエラー）

エージェント定義ファイルの読み込み時に発生したエラー情報を保持します。
読み込みに失敗した個別のエージェント定義はスキップされ、他のエージェントの読み込みは継続します。

| フィールド | 型 | 制約 |
|-----------|---|------|
| `source` | `str` | 空文字列不可。エラー発生元（ファイルパス等） |
| `message` | `str` | 空文字列不可。エラーメッセージ |

## LoadResult（読み込み結果）

エージェント定義の読み込み結果です。
正常に読み込まれた定義とスキップされたエラー情報を分離して保持します。

| フィールド | 型 | 制約 |
|-----------|---|------|
| `agents` | `tuple[AgentDefinition, ...]` | 読み込み成功したエージェント定義 |
| `errors` | `tuple[LoadError, ...]` | デフォルト空タプル。読み込みエラー情報 |

## エージェントの読み込み

### load_builtin_agents()

パッケージに同梱された6つのビルトインエージェント定義を読み込みます。

```{code-block} python
from hachimoku.agents import load_builtin_agents

result = load_builtin_agents()
print(len(result.agents))  # 6
```

### load_custom_agents(custom_dir)

指定ディレクトリ内の `*.toml` ファイルをカスタムエージェント定義として読み込みます。
ディレクトリが存在しない場合は空の LoadResult を返します。

```{code-block} python
from pathlib import Path
from hachimoku.agents import load_custom_agents

result = load_custom_agents(Path(".hachimoku/agents"))
```

### load_agents(custom_dir=None)

ビルトインとカスタムのエージェント定義を統合して読み込みます。
カスタム定義がビルトインと同名の場合、カスタムがビルトインを上書きします。

```{code-block} python
from pathlib import Path
from hachimoku.agents import load_agents

# ビルトインのみ
result = load_agents()

# カスタムと統合
result = load_agents(custom_dir=Path(".hachimoku/agents"))

for agent in result.agents:
    print(f"{agent.name}: {agent.description}")

# 読み込みエラーの確認
for error in result.errors:
    print(f"Skipped {error.source}: {error.message}")
```

## カスタムエージェントの作成

プロジェクト固有のカスタムエージェントを追加する手順:

1. `.hachimoku/agents/` ディレクトリを作成
2. TOML 形式でエージェント定義ファイルを配置

```{code-block} toml
:caption: .hachimoku/agents/security-checker.toml

name = "security-checker"
description = "セキュリティ脆弱性の検出"
model = "anthropic:claude-opus-4-6"
output_schema = "scored_issues"
allowed_tools = ["git_read", "gh_read", "file_read"]
system_prompt = """
You are security-checker, a security vulnerability specialist.
Analyze the code for injection, authentication, and data exposure issues.
"""

[applicability]
always = true
```

`output_schema` には [SCHEMA_REGISTRY](schema-registry) に登録されたスキーマ名を指定します。
ビルトインと同名のファイルを配置すると、ビルトインの定義を上書きできます。
