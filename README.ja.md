# hachimoku

[English](README.md) | **日本語**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

hachimoku（8moku）は、複数の専門エージェントを用いてコードレビューを行う CLI ツールです。
エージェントの定義は TOML ファイルで管理され、コード変更なしにレビュー観点を追加・カスタマイズできます。

## 主な特徴

- 3つのレビューモード: diff（ブランチ差分）、PR（GitHub PR）、file（指定ファイル）
- ビルトインエージェント: コード品質、サイレント障害、テストカバレッジ、型安全性、コメント、簡潔化
- TOML ベースのエージェント定義でカスタムエージェントを追加可能
- 逐次実行・並列実行を選択可能
- LLM ベース結果集約: 複数エージェントの指摘を重複排除・統合し、推奨アクションを生成
- コスト効率化: セレクター・集約は軽量モデル、レビューは高性能モデルで精度を維持
- 柔軟なモデル設定: config → definition → global の優先順位で解決、いつでも Opus 4.6 に戻せる
- Markdown / JSON 出力対応（デフォルトは Markdown）
- JSONL 形式でレビュー結果を自動蓄積し、レビュー履歴の解析・分析が可能

## インストール

`uv tool install` でグローバルにインストールできます。

```bash
uv tool install git+https://github.com/drillan/hachimoku.git
```

開発者向け（ソースからのセットアップ）:

```bash
git clone https://github.com/drillan/hachimoku.git
cd hachimoku
uv sync
```

詳細は [インストール](docs/ja/installation.md) を参照してください。

## アップグレード

```bash
uv tool install --reinstall git+https://github.com/drillan/hachimoku.git
```

> **Note**: `uv tool install` は既にインストール済みの場合、何も行いません。
> `--reinstall` フラグにより、リモートリポジトリから最新のコードを取得して再インストールします。

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
| `--model TEXT` | LLM モデル名（プレフィックス付き: `claudecode:` or `anthropic:`） |
| `--timeout INTEGER` | タイムアウト秒数 |
| `--parallel / --no-parallel` | 並列実行の有効/無効 |
| `--format FORMAT` | 出力形式（`markdown` / `json`、デフォルト: `markdown`） |
| `--base-branch TEXT` | diff モードのベースブランチ |
| `--issue INTEGER` | コンテキスト用 GitHub Issue 番号 |
| `--no-confirm` | 確認プロンプトをスキップ |

## モデルプレフィックス

hachimoku はモデル名のプレフィックスでプロバイダーを決定します:

| プレフィックス | 説明 | API キー | 例 |
|--------------|------|---------|-----|
| `claudecode:` | Claude Code 内蔵モデル（デフォルト） | 不要 | `claudecode:claude-opus-4-6` |
| `anthropic:` | Anthropic API 直接呼び出し | `ANTHROPIC_API_KEY` 必須 | `anthropic:claude-opus-4-6` |

```bash
# Anthropic API を使用する場合
export ANTHROPIC_API_KEY="your-api-key"
8moku --model "anthropic:claude-opus-4-6"
```

## 設定

TOML ベースの階層的な設定をサポートします（優先度順）:

1. CLI オプション
2. `.hachimoku/config.toml`
3. `pyproject.toml [tool.hachimoku]`
4. `~/.config/hachimoku/config.toml`
5. デフォルト値

## ドキュメント

詳細なドキュメントは [docs/](docs/) を参照してください。[日本語](docs/ja/)・[English](docs/en/) で提供しています。

- [インストール](docs/ja/installation.md)
- [CLI リファレンス](docs/ja/cli.md)
- [エージェント定義](docs/ja/agents.md)
- [設定](docs/ja/configuration.md)
- [ドメインモデル](docs/ja/models.md)
- [Review Context ガイド](docs/ja/review-context.md)

## ライセンス

[MIT License](LICENSE)
