# インストール

```{contents}
:depth: 2
:local:
```

## 要件

- Python 3.13 以上
- Git（diff モード・PR モードで必要）

## ソースからインストール

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
