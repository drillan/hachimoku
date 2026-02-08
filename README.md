# hachimoku

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

hachimoku（8moku）は、複数の専門エージェントを用いてコードレビューを行う CLI ツールです。
エージェントの定義は TOML ファイルで管理され、コード変更なしにレビュー観点を追加・カスタマイズできます。

## 主な特徴

- 3つのレビューモード: diff（ブランチ差分）、PR（GitHub PR）、file（指定ファイル）
- ビルトインエージェント: コード品質、サイレント障害、テストカバレッジ、型設計、コメント、簡潔化
- TOML ベースのエージェント定義でカスタムエージェントを追加可能
- 逐次実行・並列実行を選択可能
- JSON 出力対応（Markdown は今後対応予定）

## インストール

現在 PyPI には未公開です。ソースからインストールしてください。

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv sync
```

## クイックスタート

### 1. プロジェクトの初期化

```bash
8moku init
```

`.hachimoku/` ディレクトリにデフォルトの設定ファイルとエージェント定義が作成されます。

### 2. コードレビューの実行

```bash
# diff モード: 現在ブランチの変更差分をレビュー
8moku

# PR モード: GitHub PR をレビュー
8moku 42

# file モード: 指定ファイルをレビュー
8moku src/main.py tests/test_main.py
```

### 3. エージェントの確認

```bash
# エージェント一覧
8moku agents

# エージェント詳細
8moku agents code-reviewer
```

## CLI コマンド

| コマンド | 説明 |
|---------|------|
| `8moku [OPTIONS] [ARGS]` | コードレビューを実行（デフォルト） |
| `8moku init [--force]` | `.hachimoku/` ディレクトリを初期化 |
| `8moku agents [NAME]` | エージェント定義の一覧・詳細表示 |

主なレビューオプション:

| オプション | 説明 |
|-----------|------|
| `--model TEXT` | LLM モデル名 |
| `--timeout INTEGER` | タイムアウト秒数 |
| `--parallel / --no-parallel` | 並列実行の有効/無効 |
| `--format json` | 出力形式 |
| `--base-branch TEXT` | diff モードのベースブランチ |
| `--issue INTEGER` | コンテキスト用 GitHub Issue 番号 |
| `--no-confirm` | 確認プロンプトをスキップ |

## 設定

TOML ベースの階層的な設定をサポートします（優先度順）:

1. CLI オプション
2. `.hachimoku/config.toml`
3. `pyproject.toml [tool.hachimoku]`
4. `~/.config/hachimoku/config.toml`
5. デフォルト値

## ドキュメント

詳細なドキュメントは [docs/](docs/) を参照してください。

- [エージェント定義](docs/agents.md)
- [設定](docs/configuration.md)
- [ドメインモデル](docs/models.md)

## ライセンス

[MIT License](LICENSE)
