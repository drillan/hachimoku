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
| type-design-analyzer | 型設計の分析 | multi_dimensional_analysis | main | file_patterns + content_patterns |
| comment-analyzer | コメントの正確性分析 | category_classification | final | content_patterns |
| code-simplifier | コード簡潔化の提案 | improvement_suggestions | final | 常時適用 |

出力スキーマの詳細は [出力スキーマ](output-schemas) を参照してください。

## TOML 定義ファイル形式

エージェント定義は以下の形式の TOML ファイルで記述します。

```{code-block} toml
name = "code-reviewer"
description = "コード品質・バグ・ベストプラクティスの総合レビュー"
model = "claude-sonnet-4-5-20250929"
output_schema = "scored_issues"
phase = "main"
system_prompt = """
You are an expert code reviewer. Analyze the provided code changes and identify:
- Bugs and logical errors
- Code quality issues
- Violations of best practices and coding standards
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
model = "claude-sonnet-4-5-20250929"
output_schema = "scored_issues"
system_prompt = """
You are a security specialist. Analyze the code for vulnerabilities.
"""

[applicability]
always = true
```

`output_schema` には [SCHEMA_REGISTRY](schema-registry) に登録されたスキーマ名を指定します。
ビルトインと同名のファイルを配置すると、ビルトインの定義を上書きできます。
