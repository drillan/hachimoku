# インストール

```{contents}
:depth: 2
:local:
```

## 前提条件

- [Claude Code](https://docs.claude.com/en/docs/claude-code) — hachimoku はその中でプラグインとして動作します
- [`uv`](https://docs.astral.sh/uv/) — hachimoku CLI を `uvx` でエフェメラル実行するために使用。`PATH` 上にある必要があります
- [`jq`](https://jqlang.github.io/jq/) — 同梱の読み取り専用 git ガード hook が必要とする。`PATH` 上にある必要があります
- Git（diff モード・PR モードのレビューで必要）

前提条件を確認します:

```bash
uv --version
jq --version
```

## Claude Code プラグインのインストール

プラグインが、hachimoku を利用するための主要かつユーザー向けの方法です。レビューは `/hachimoku:setup` と `/hachimoku:review` のスキルを通じて Claude Code 内で実行されます。

### ローカル / 開発用途

リポジトリをクローンし、同梱のプラグインディレクトリを Claude Code に指定します:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
claude --plugin-dir ./plugin
```

### マーケットプレイス経由

マーケットプレイス配布は今後公開予定です。

## プロジェクトのセットアップ

レビューしたい各プロジェクトで、hachimoku を初期化し、レビューサブエージェントを生成します。

### 1. プロジェクトの初期化

```bash
cd your-project
uvx --from git+https://github.com/drillan/hachimoku@v0.1.0 hachimoku init
```

以下のファイルが `.hachimoku/` ディレクトリに作成されます:

- `config.toml` — 設定ファイル（全オプションがコメントアウトされたテンプレート）
- `agents/*.toml` — ビルトインエージェント定義のコピー
- `reviews/` — レビュー結果の JSONL 蓄積ディレクトリ
- `.gitignore` への `/.hachimoku/` エントリ自動追加（Git リポジトリ内のみ。未登録の場合のみ）

設定の詳細は [設定](configuration.md) を参照してください。

### 2. レビューサブエージェントの生成

Claude Code 内で、セットアップスキルを実行します:

```
/hachimoku:setup
```

これにより、レビューサブエージェントが `.claude/agents/` に、`.claude/manifest.json` とともに生成されます。再実行が必要なのは、プラグインまたは hachimoku 本体をアップグレードした後のみです。

## 任意: CLI のローカルインストール（開発者向け）

レビューの実行に CLI のインストールは**不要**です。プラグインのスキルが `uvx` でエフェメラル実行します。ローカルにインストールするのは、`hachimoku build` / `select` / `aggregate` を手元で実行したい開発者にのみ有用です。

### グローバルインストール（uv tool install）

```bash
uv tool install git+https://github.com/drillan/hachimoku.git
```

これにより `hachimoku` および `8moku` コマンドがグローバルに利用可能になります。アップグレードする場合:

```bash
uv tool install --reinstall git+https://github.com/drillan/hachimoku.git
```

```{note}
`uv tool install` は既にインストール済みの場合、何も行いません。
`--reinstall` フラグは強制的な再インストールを行い、`--refresh`（キャッシュ
無効化）を含意するため、リモートリポジトリから確実に最新のコードを取得します。
```

### ソースからインストール

リポジトリをクローンして依存関係を同期します:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv sync
```

開発用ツール（テスト、リンター、型チェッカー）も含める場合:

```bash
uv sync --group dev
```

## 動作確認

Claude Code でプラグインのスキルを一覧表示し、`/hachimoku:setup` と `/hachimoku:review` が利用可能であることを確認します。プロジェクトで `/hachimoku:setup` を実行した後、`.claude/agents/` に生成されたレビューサブエージェントの `.md` ファイルがあり、`.claude/manifest.json` が存在することを確認します。

CLI をローカルにインストールした場合は、直接確認することもできます:

```bash
hachimoku --help
hachimoku agents
```
