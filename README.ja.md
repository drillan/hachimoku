# hachimoku

[English](README.md) | **日本語**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)

hachimoku は、マルチエージェントによるコードレビューを行う Claude Code プラグインです。
レビューは**対話中の Claude Code セッション内**で実行され、専門のレビューサブエージェントを並列にディスパッチし、その指摘を 1 つのレポートに集約します。

レビューは既存の Claude Code セッション内で実行されるため、`claude -p` が 2026-06-15 以降に発生させる従量課金枠ではなく、対話サブスクリプションの枠でまかなわれます。

## 主な特徴

- Claude Code プラグインとして動作 — 別途レビューツールをインストール・実行する必要がない
- ビルトインのレビューサブエージェントを標準提供（コード品質、セキュリティ、依存関係、型設計、テストカバレッジ、コメント、簡潔化 など）
- TOML エージェント定義でプロジェクト固有のレビュー観点を追加可能 — コード変更は不要
- フェーズ順（early → main → final）での並列ディスパッチ
- 決定的な選択と集約: エージェント選択とレポート集約は LLM 枠を消費しない通常の CLI ステップとして実行される
- レビューサブエージェントは同梱のガード hook により `git`/`gh` の読み取り専用アクセスに制限される
- レビュー結果は `.hachimoku/reviews/` 配下に JSONL 形式で蓄積され、レビュー履歴の分析に利用できる

## 前提条件

以下の 2 つが `PATH` 上にインストールされている必要があります:

- [`uv`](https://docs.astral.sh/uv/) — hachimoku CLI を `uvx` でエフェメラル実行するために使用
- [`jq`](https://jqlang.github.io/jq/) — 同梱の読み取り専用 git ガード hook が必要とする

## クイックスタート

### 1. プラグインのインストール

ローカル / 開発用途では、同梱のプラグインディレクトリを Claude Code に指定します:

```bash
claude --plugin-dir ./plugin
```

マーケットプレイス配布は今後公開予定です。

### 2. プロジェクトのセットアップ（初回のみ）

プロジェクト内で、Claude Code のセットアップスキルを実行します:

```
/hachimoku:setup
```

これにより、レビューサブエージェントが `.claude/agents/` に、`.claude/manifest.json` とともに生成されます。再実行が必要なのはプラグインをアップグレードした後のみです。

### 3. レビューの実行

```
/hachimoku:review
```

レビュースキルがレビューをオーケストレーションします。適用対象のサブエージェントを選択し、フェーズ順に並列ディスパッチし、指摘を集約して、構造化されたレポートを提示します。引数に PR 番号やファイルパスを渡せます。空のままにすると現在ブランチの差分をレビューします。

## アーキテクチャ

hachimoku は 2 つの部分から構成されます:

- **Claude Code プラグイン**（ユーザー向け） — `/hachimoku:setup` と `/hachimoku:review` の 2 つのスキル。これがレビューのインターフェースです。
- **薄い CLI**（`hachimoku`、エイリアス `8moku`） — 決定的で LLM 非依存のサブコマンド（`init`、`agents`、`build`、`select`、`aggregate`）を持つ補助的な開発者ユーティリティ。プラグインのスキルはこれを `uvx` でエフェメラル実行します。

レビューの実行に CLI のインストールは不要です。`uv tool install` でローカルにインストールするのは任意であり、`build` / `select` / `aggregate` を手元で実行したい開発者にのみ有用です。詳細は [インストール](docs/ja/installation.md) を参照してください。

## エージェント定義

レビューサブエージェントは `.hachimoku/agents/` 配下の TOML エージェント定義から生成されます。各定義はレビュー観点、モデル、適用ルール、出力スキーマを宣言します。プロジェクト固有のカスタムエージェントを追加するには、新しい TOML ファイルをそのディレクトリに置き、`/hachimoku:setup` を再実行します。

詳細は [エージェント定義](docs/ja/agents.md) を参照してください。

## 設定

TOML ベースの階層的な設定をサポートします（優先度順）:

1. `.hachimoku/config.toml`
2. `pyproject.toml [tool.hachimoku]`
3. `~/.config/hachimoku/config.toml`
4. デフォルト値

詳細は [設定](docs/ja/configuration.md) を参照してください。

## ドキュメント

📖 **オンライン**: [日本語](https://drillan.github.io/hachimoku/ja/) | [English](https://drillan.github.io/hachimoku/en/)

ソースファイルは [docs/](docs/) にあります。

- [インストール](docs/ja/installation.md)
- [CLI リファレンス](docs/ja/cli.md)
- [エージェント定義](docs/ja/agents.md)
- [設定](docs/ja/configuration.md)
- [ドメインモデル](docs/ja/models.md)
- [Review Context ガイド](docs/ja/review-context.md)

## ライセンス

[MIT License](LICENSE)
