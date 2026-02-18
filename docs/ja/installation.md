# インストール

```{contents}
:depth: 2
:local:
```

## 要件

- Python 3.13 以上
- Git（diff モード・PR モードで必要）

## グローバルインストール（uv tool install）

`uv tool install` を使うと、仮想環境を明示的にアクティベートせずに `8moku` / `hachimoku` コマンドをグローバルに利用できます。

### Git URL からインストール

リポジトリを直接指定してインストールします:

```bash
uv tool install git+https://github.com/drillan/hachimoku.git
```

### ローカルクローンからインストール

リポジトリをクローンしてからインストールします:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv tool install .
```

### uv sync との使い分け

| 方法 | 対象 | 用途 |
|------|------|------|
| `uv tool install` | 利用者 | グローバルにコマンドをインストールしてレビューツールとして使用 |
| `uv sync` | 開発者 | プロジェクトディレクトリ内で開発・テスト・デバッグ |

- **利用者**: `uv tool install` でインストールすれば、任意のディレクトリから `8moku` コマンドを実行できます
- **開発者**: `uv sync` でプロジェクトの仮想環境に依存関係を同期し、`uv run` 経由でコマンドを実行します

## アップグレード

### Git URL からインストールした場合

```bash
uv tool install --reinstall git+https://github.com/drillan/hachimoku.git
```

### ローカルクローンからインストールした場合

```bash
cd hachimoku
git pull
uv tool install --reinstall .
```

```{note}
`uv tool install` は既にインストール済みの場合、何も行いません。
`--reinstall` フラグにより、全パッケージを強制的に再インストールします。
このフラグは `--refresh`（キャッシュ無効化）を含意するため、
リモートリポジトリから確実に最新のコードを取得します。
```

## ソースからインストール（開発用）

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

## セットアップ

インストール後、プロジェクトディレクトリで初期化を行います:

```bash
cd your-project
8moku init
```

以下のファイルが `.hachimoku/` ディレクトリに作成されます:

- `config.toml` - 設定ファイル（全オプションがコメントアウトされたテンプレート）
- `agents/*.toml` - ビルトインエージェント定義のコピー

設定の詳細は [設定](configuration.md) を参照してください。

## 動作確認

```bash
# ヘルプの表示
8moku --help

# エージェント一覧の確認
8moku agents
```

`hachimoku` コマンドも同じ機能を提供します:

```bash
hachimoku --help
```
