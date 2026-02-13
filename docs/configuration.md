# 設定

hachimoku は TOML ベースの階層的な設定システムを提供します。
5つのソースから設定を読み込み、優先度に基づいて値を解決します。

```{contents}
:depth: 2
:local:
```

## 設定の階層

以下の5層で構成されます。上位のソースが下位を上書きします。

1. CLI オプション（最高優先度）
2. `.hachimoku/config.toml`（プロジェクト設定）
3. `pyproject.toml` の `[tool.hachimoku]` セクション
4. `~/.config/hachimoku/config.toml`（ユーザーグローバル設定）
5. デフォルト値（最低優先度）

プロジェクト設定（`.hachimoku/config.toml`）と `pyproject.toml` は、カレントディレクトリから親方向に探索されます。

### マージルール

- スカラー値: 高優先レイヤーの値が上書き
- `agents` セクション: エージェント名をキーとしてフィールド単位でマージ
- `selector` セクション: フィールド単位でマージ

## 設定ファイル形式

### .hachimoku/config.toml

```{literalinclude} _examples/config.toml
:language: toml
:caption: .hachimoku/config.toml
```

### pyproject.toml

```{code-block} toml
[tool.hachimoku]
model = "anthropic:claude-opus-4-6"
timeout = 300
parallel = false
```

## 設定項目

### HachimokuConfig

全設定項目の一覧です。

| 項目 | 型 | デフォルト | 制約 | 説明 |
|-----|---|----------|------|------|
| `model` | `str` | `"claudecode:claude-opus-4-6"` | 空文字不可、プレフィックス必須 | 使用する LLM モデル名（`claudecode:` or `anthropic:` プレフィックスでプロバイダーを指定） |
| `timeout` | `int` | `600` | 正の値 | エージェントのタイムアウト（秒） |
| `max_turns` | `int` | `20` | 正の値 | エージェントの最大ターン数 |
| `parallel` | `bool` | `true` | - | 並列実行の有効化 |
| `base_branch` | `str` | `"main"` | 空文字不可 | diff モードの基準ブランチ |
| `output_format` | `str` | `"markdown"` | `"markdown"` or `"json"` | 出力形式 |
| `save_reviews` | `bool` | `true` | - | レビュー履歴の JSONL 保存（後述） |
| `show_cost` | `bool` | `false` | - | コスト情報の表示 |
| `max_files_per_review` | `int` | `100` | 正の値 | file モードの最大ファイル数 |
| `selector` | `SelectorConfig` | 後述 | - | セレクターエージェント設定 |
| `aggregation` | `AggregationConfig` | 後述 | - | 集約エージェント設定 |
| `agents` | `dict[str, AgentConfig]` | `{}` | - | エージェント個別設定 |

### SelectorConfig

セレクターエージェントの設定上書きです。
`model`、`timeout`、`max_turns` が `None` の場合はセレクター定義の値を使用し、それも `None` の場合はグローバル設定値を使用します（3 層解決: config → definition → global）。

| 項目 | 型 | デフォルト | 制約 | 説明 |
|-----|---|----------|------|------|
| `model` | `str \| None` | `None` | 空文字不可 | モデル名の上書き（プレフィックスでプロバイダー指定） |
| `timeout` | `int \| None` | `None` | 正の値 | タイムアウト（秒） |
| `max_turns` | `int \| None` | `None` | 正の値 | 最大ターン数 |
| `referenced_content_max_chars` | `int` | `5000` | 正の値 | referenced_content の各コンテンツの最大文字数。超過時は末尾切り詰め + truncation マーカー追加 |

### AggregationConfig

集約エージェントの設定です。SelectorConfig と同パターンに加え、`enabled` で集約の有効/無効を切り替えます。
`model`、`timeout`、`max_turns` が `None` の場合は集約エージェント定義の値を使用し、それも `None` の場合はグローバル設定値を使用します（3 層解決: config → definition → global）。

| 項目 | 型 | デフォルト | 制約 | 説明 |
|-----|---|----------|------|------|
| `enabled` | `bool` | `true` | - | 集約の有効/無効 |
| `model` | `str \| None` | `None` | 空文字不可 | モデル名の上書き（プレフィックスでプロバイダー指定） |
| `timeout` | `int \| None` | `None` | 正の値 | タイムアウト（秒） |
| `max_turns` | `int \| None` | `None` | 正の値 | 最大ターン数 |

```{code-block} toml
[aggregation]
enabled = true
model = "claudecode:claude-opus-4-6"
timeout = 300
max_turns = 10
```

### AgentConfig

エージェントごとの個別設定です。
`model`、`timeout`、`max_turns` が `None` の場合はグローバル設定値を使用します。

| 項目 | 型 | デフォルト | 制約 | 説明 |
|-----|---|----------|------|------|
| `enabled` | `bool` | `true` | - | エージェントの有効/無効 |
| `model` | `str \| None` | `None` | 空文字不可 | モデル名（プレフィックスでプロバイダー指定） |
| `timeout` | `int \| None` | `None` | 正の値 | タイムアウト（秒） |
| `max_turns` | `int \| None` | `None` | 正の値 | 最大ターン数 |

エージェント名は `[agents.<name>]` 形式で指定し、`^[a-z0-9-]+$` パターンに一致する必要があります。

## レビュー履歴の蓄積

`save_reviews = true`（デフォルト）の場合、レビュー完了後に結果を `.hachimoku/reviews/` ディレクトリへ JSONL 形式で自動蓄積します。

### 蓄積先ファイル

レビューモードごとに蓄積先ファイルが分かれます。

| レビューモード | 蓄積先ファイル | 例 |
|--------------|--------------|---|
| diff | `diff.jsonl` | `.hachimoku/reviews/diff.jsonl` |
| PR | `pr-{番号}.jsonl` | `.hachimoku/reviews/pr-123.jsonl` |
| file | `files.jsonl` | `.hachimoku/reviews/files.jsonl` |

各行は独立した JSON オブジェクトです。新しいレビューは既存ファイルに追記されます。

### 無効化

```{code-block} toml
save_reviews = false
```

CLI オプションでも制御できます。

```{code-block} bash
8moku review --no-save-reviews
```

## プロジェクトルート探索

`find_project_root()` は指定ディレクトリから親方向に `.hachimoku/` ディレクトリを探索します。
見つからない場合は `None` を返します。

```{code-block} python
from pathlib import Path
from hachimoku.config import find_project_root

root = find_project_root(Path.cwd())
if root is not None:
    print(f"Project root: {root}")
```

## 設定の解決

`resolve_config()` は5層の設定ソースを統合し、最終的な設定オブジェクトを構築します。
全ファイルが存在しない場合はデフォルト値のみで構築されます。

```{code-block} python
from pathlib import Path
from hachimoku.config import resolve_config

# デフォルト設定（カレントディレクトリから探索）
config = resolve_config()

# 探索開始ディレクトリと CLI オーバーライドを指定
config = resolve_config(
    start_dir=Path("/path/to/project"),
    cli_overrides={"timeout": 600, "parallel": False},
)

print(config.model)      # "claudecode:claude-opus-4-6"
print(config.timeout)    # 600（CLI オーバーライドが適用）
print(config.parallel)   # False（CLI オーバーライドが適用）
```
