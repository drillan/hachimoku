# CLI リファレンス

`hachimoku` CLI（エイリアス `8moku`）は、レビューのインターフェースではなく、**補助的な開発者ユーティリティ**です。レビューは `/hachimoku:setup` と `/hachimoku:review` のスキルを通じて Claude Code 内で実行します。詳細は [インストール](installation.md) を参照してください。

この CLI は決定的で LLM 非依存のサブコマンドのみを提供します。プラグインのスキルが `uvx` でエフェメラル実行するため、通常は手動で実行することはありません。本ページは開発者向け、およびプラグインが内部で何をしているかを理解するために記載しています。

```{contents}
:depth: 2
:local:
```

## 概要

```bash
hachimoku [OPTIONS] COMMAND [ARGS]...
```

| コマンド | 説明 |
|---------|------|
| `init` | `.hachimoku/` ディレクトリをデフォルトの設定とエージェント定義で初期化 |
| `agents` | エージェント定義の一覧・詳細表示 |
| `build` | TOML エージェント定義から Claude Code サブエージェントと `manifest.json` をビルド |
| `select` | 対象のレビューエージェントを選択し、ディスパッチプラン（JSON）を出力 |
| `aggregate` | サブエージェントの指摘をレビューレポートに集約 |

グローバルオプション:

| オプション | 説明 |
|-----------|------|
| `--version` | バージョン番号を表示して終了 |
| `--help` | ヘルプを表示 |

`select` と `aggregate` は `/hachimoku:review` スキルが内部的に呼び出します。`select` はディスパッチプランを計算し、`aggregate` は最終レポートを生成します。通常はユーザーが直接実行することはありません。

## init

`.hachimoku/` ディレクトリにデフォルトの設定ファイルとエージェント定義を作成します。Git リポジトリの内外を問わず実行できます。Git リポジトリ内では `.gitignore` への自動追加も行います。

```bash
hachimoku init [OPTIONS]
```

| オプション | 説明 |
|-----------|------|
| `--force` | 既存ファイルをデフォルト値で上書き |
| `--upgrade` | ビルトインエージェント定義をハッシュ比較で更新 |
| `--help` | ヘルプを表示 |

```bash
# 初回セットアップ
hachimoku init

# 全ファイルをデフォルト値にリセット（config.toml 含む）
hachimoku init --force

# バージョンアップ後にエージェント定義を更新（カスタマイズ済みはスキップ）
hachimoku init --upgrade

# カスタマイズ済みエージェント定義も含めて強制更新（config.toml は保持）
hachimoku init --upgrade --force
```

### フラグ別の動作範囲

| 対象 | `init` | `--force` | `--upgrade` | `--upgrade --force` |
|------|--------|-----------|-------------|---------------------|
| `config.toml` | 新規作成 | 上書き | 対象外 | 対象外 |
| `agents/*.toml` | 新規作成 | 上書き | ハッシュ比較で更新 | 強制上書き |
| `reviews/` | 作成 | 作成 | 対象外 | 対象外 |
| `.gitignore` | 追加 | 追加 | 対象外 | 対象外 |

### upgrade のハッシュ比較

`--upgrade` はローカルファイルとビルトイン定義の SHA-256 ハッシュを比較し、以下のように判定します:

- **ファイルが存在しない**: 新規追加（`Added`）
- **ハッシュ一致**: 更新不要（`Skipped (up to date)`）
- **ハッシュ不一致**: カスタマイズ済みとしてスキップ（`Skipped (customized)`）
- **ハッシュ不一致 + `--force`**: 強制上書き（`Updated`）

作成されるファイル（`init` / `--force`）:

- `.hachimoku/config.toml` — 設定ファイル（全オプションがコメントアウトされたテンプレート）
- `.hachimoku/agents/*.toml` — ビルトインエージェント定義のコピー
- `.hachimoku/reviews/` — レビュー結果の JSONL 蓄積ディレクトリ
- `.gitignore` への `/.hachimoku/` エントリ自動追加（Git リポジトリ内のみ。未登録の場合のみ）

## agents

エージェント定義の一覧表示または詳細表示を行います。

```bash
hachimoku agents [NAME]
```

| 引数 | 説明 |
|------|------|
| `NAME` | 詳細表示するエージェント名（省略時は一覧表示） |

```bash
# 一覧表示
hachimoku agents

# 詳細表示
hachimoku agents code-reviewer
```

一覧表示では NAME, MODEL, PHASE, SCHEMA の各列が表示されます。プロジェクト固有のカスタムエージェントには `[custom]` マーカーが付きます。

## build

TOML エージェント定義から Claude Code のレビューサブエージェントと `manifest.json` をビルドします。各 `*.toml` エージェント定義は、サブエージェント `.md` ファイル（フロントマター、ツール権限、読み取り専用 git ガード hook、Output Contract を含む）と、`manifest.json` の 1 エントリに変換されます。

```bash
hachimoku build [OPTIONS]
```

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--output PATH` | `.hachimoku/build` | 生成されるサブエージェントの出力ディレクトリ |
| `--hook-script TEXT` | `${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh` | 読み取り専用 git ガード hook スクリプトの絶対パス |
| `--help` | — | ヘルプを表示 |

`/hachimoku:setup` スキルは `build` を `--output .claude` で実行し、生成されるサブエージェントが `.claude/agents/` 配下に、`manifest.json` が `.claude/` 配下に配置されるようにします。

```bash
# デフォルトディレクトリにビルド
hachimoku build

# .claude にビルド（setup スキルと同じ）
hachimoku build --output .claude --hook-script /abs/path/to/block-git-mutations.sh
```

## select

変更セットをエージェント manifest と照合し、ディスパッチプランを JSON として出力します。`/hachimoku:review` が内部的に呼び出します。

```bash
hachimoku select [OPTIONS] [ARGS]...
```

| 引数 | 説明 |
|------|------|
| `ARGS` | PR 番号またはファイルパス（省略時は diff モード） |

| オプション | 説明 |
|-----------|------|
| `--manifest PATH` | manifest JSON ファイルのパス（**必須**） |
| `--commit TEXT` | commit モードのコミット参照またはレンジ（`SHA` または `SHA1..SHA2`） |
| `--base-branch TEXT` | diff モードのベースブランチ（デフォルト: `main`） |
| `--help` | ヘルプを表示 |

対象は引数により決定されます。引数なしは diff モード、整数 1 つは PR モード、ファイルパスは file モードを選択します。JSON 出力には `run_dir`（`aggregate` が消費する一時ディレクトリ）と `phases`（`early` / `main` / `final`、それぞれエージェント名のリスト）が含まれます。

## aggregate

run ディレクトリからサブエージェントの指摘 JSON ファイルを読み込み、検証・重複排除し、重要度を分類して、Markdown のレビューレポートを出力します。`.hachimoku/reviews/` 配下の JSONL レビュー履歴にもレコードを追記します。`/hachimoku:review` が内部的に呼び出します。

```bash
hachimoku aggregate [OPTIONS] [ARGS]...
```

| 引数 | 説明 |
|------|------|
| `ARGS` | PR 番号またはファイルパス（省略時は diff モード） |

| オプション | 説明 |
|-----------|------|
| `--run-dir PATH` | `select` が作成した run ディレクトリ（**必須**） |
| `--manifest PATH` | manifest JSON ファイルのパス（**必須**） |
| `--commit TEXT` | commit モードのコミット参照またはレンジ（`SHA` または `SHA1..SHA2`） |
| `--base-branch TEXT` | diff モードのベースブランチ（デフォルト: `main`） |
| `--help` | ヘルプを表示 |

`aggregate` は Markdown レポートを stdout に出力し、重要度に応じた終了コードで終了します（[終了コード](#exit-codes) を参照）。一部のサブエージェントが失敗した場合でも run 全体を失敗とはせず、レポートに失敗エージェントの節を出し、成功した指摘で集約を継続します。

## 出力ストリーム

CLI はレポート出力と進捗情報を分離します:

stdout
: レビューレポート（`aggregate`）またはディスパッチプラン JSON（`select`）。パイプやリダイレクトに対応します。

stderr
: 進捗情報、ログ、エラーメッセージ。

```bash
# select のディスパッチプランを jq にパイプ
hachimoku select --manifest .claude/manifest.json | jq '.phases'
```

(exit-codes)=

## 終了コード

| コード | 名前 | 意味 |
|-------|------|------|
| 0 | SUCCESS | 正常終了 |
| 1 | CRITICAL | Critical レベルの問題を検出 |
| 2 | IMPORTANT | Important レベルの問題を検出（Critical なし） |
| 3 | EXECUTION_ERROR | 実行時エラー（設定解析、Git 操作など） |
| 4 | INPUT_ERROR | 入力エラー（不正な引数、Git 要件未満、ファイル不在、設定ファイル不備） |

コード 1（CRITICAL）と 2（IMPORTANT）は、集約された指摘の重要度に基づき `aggregate` のみが生成します。決定的なサブコマンド `init`、`agents`、`build`、`select` は、成功時 0、実行時エラー時 3、入力エラー時 4 のみを返します。
