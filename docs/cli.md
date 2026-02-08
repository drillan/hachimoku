# CLI リファレンス

hachimoku は `8moku` と `hachimoku` の2つのコマンド名を提供します。どちらも同一の機能を実行します。

```{contents}
:depth: 2
:local:
```

## レビューコマンド（デフォルト）

引数なしまたは引数付きで実行すると、コードレビューを行います。

```bash
8moku [OPTIONS] [ARGS]
```

引数の種類により入力モードが自動判定されます:

引数なし
: diff モード。現在ブランチの変更差分をレビューします。Git リポジトリ内で実行する必要があります。

正の整数1つ
: PR モード。指定された GitHub PR の差分とメタデータをレビューします。Git リポジトリ内で実行する必要があります。

ファイルパス（1つ以上）
: file モード。指定されたファイルの全体をレビューします。glob パターン（`*`, `?`, `[`）やディレクトリ指定にも対応します。Git リポジトリ外でも動作します。

```bash
# diff モード
8moku

# PR モード
8moku 42

# file モード
8moku src/main.py
8moku src/**/*.py
8moku src/
```

### レビューオプション

レビューコマンドのオプションです。設定ファイルの値を上書きします。

| オプション | 型 | 説明 |
|-----------|-----|------|
| `--model TEXT` | str | LLM モデル名 |
| `--timeout INTEGER` | int (min: 1) | タイムアウト秒数 |
| `--max-turns INTEGER` | int (min: 1) | エージェントの最大ターン数 |
| `--parallel / --no-parallel` | bool | 並列実行の有効/無効 |
| `--base-branch TEXT` | str | diff モードのベースブランチ |
| `--format json` | OutputFormat | 出力形式（現在は JSON のみ対応） |
| `--save-reviews / --no-save-reviews` | bool | レビュー結果の保存 |
| `--show-cost / --no-show-cost` | bool | コスト情報の表示 |
| `--max-files INTEGER` | int (min: 1) | レビュー対象の最大ファイル数 |
| `--issue INTEGER` | int (min: 1) | コンテキスト用 GitHub Issue 番号 |
| `--no-confirm` | bool | 確認プロンプトをスキップ |
| `--help` | - | ヘルプを表示 |

設定ファイルでのデフォルト値については [設定](configuration.md) を参照してください。

### ファイルモードの動作

file モードでは以下の処理が行われます:

- glob パターン（`*`, `?`, `[`）の展開
- ディレクトリ指定時の再帰的なファイル収集
- シンボリックリンクの循環検出
- 結果はソート・重複排除された絶対パスのリスト

ファイル数が `max_files_per_review`（デフォルト: 100）を超えた場合、確認プロンプトが表示されます。`--no-confirm` オプションで確認をスキップできます。

## init

`.hachimoku/` ディレクトリにデフォルトの設定ファイルとエージェント定義を作成します。

```bash
8moku init [OPTIONS]
```

| オプション | 説明 |
|-----------|------|
| `--force` | 既存ファイルをデフォルト値で上書き |
| `--help` | ヘルプを表示 |

```bash
# 初回セットアップ
8moku init

# 設定をリセット
8moku init --force
```

作成されるファイル:

- `.hachimoku/config.toml` - 設定ファイル（全オプションがコメントアウトされたテンプレート）
- `.hachimoku/agents/*.toml` - ビルトインエージェント定義のコピー

## agents

エージェント定義の一覧表示または詳細表示を行います。

```bash
8moku agents [NAME]
```

| 引数 | 説明 |
|------|------|
| `NAME` | エージェント名（省略時は一覧表示） |

```bash
# 一覧表示
8moku agents

# 詳細表示
8moku agents code-reviewer
```

一覧表示では NAME, MODEL, PHASE, SCHEMA の各列が表示されます。プロジェクト固有のカスタムエージェントには `[custom]` マーカーが付きます。

## config (Planned)

設定管理サブコマンドは未実装です。`.hachimoku/config.toml` を直接編集してください。

## 出力ストリーム

hachimoku はレビューレポートと進捗情報を分離して出力します:

stdout
: レビューレポートのみ。パイプやリダイレクトに対応します。

stderr
: 進捗情報、ログ、エラーメッセージ、確認プロンプト。

```bash
# レポートをファイルに保存
8moku > review.json

# レポートを別のコマンドにパイプ
8moku | jq '.agents'
```

## 終了コード

| コード | 名前 | 意味 |
|-------|------|------|
| 0 | SUCCESS | 正常終了。問題なし、またはユーザーが操作を確認 |
| 1 | CRITICAL | Critical レベルの問題を検出 |
| 2 | IMPORTANT | Important レベルの問題を検出（Critical なし） |
| 3 | EXECUTION_ERROR | 実行時エラー（ネットワーク、タイムアウト、設定解析など） |
| 4 | INPUT_ERROR | 入力エラー（不正な引数、Git 要件未満、ファイル不在、権限、設定ファイル不備） |

終了コードはスクリプトや CI/CD パイプラインでの条件分岐に使用できます:

```bash
8moku
case $? in
  0) echo "No issues found" ;;
  1) echo "Critical issues found" ;;
  2) echo "Important issues found" ;;
  3) echo "Execution error" ;;
  4) echo "Input error" ;;
esac
```
