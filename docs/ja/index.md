# hachimoku

hachimoku は、マルチエージェントによるコードレビューを行う Claude Code プラグインです。
レビューは対話中の Claude Code セッション内で実行され、専門のレビューサブエージェントを並列にディスパッチし、その指摘を 1 つのレポートに集約します。

レビューは既存の Claude Code セッション内で実行されるため、`claude -p` が 2026-06-15 以降に発生させる従量課金枠ではなく、対話サブスクリプションの枠でまかなわれます。

## アーキテクチャ

hachimoku は 2 つの部分から構成されます:

- **Claude Code プラグイン**（ユーザー向け） — `/hachimoku:setup` と `/hachimoku:review` の 2 つのスキル。これがレビューのインターフェースです。適用対象のサブエージェントを選択し、フェーズ順に並列ディスパッチし、指摘を集約して、レポートを提示することでレビューをオーケストレーションします。
- **薄い CLI**（`hachimoku`、エイリアス `8moku`） — 決定的で LLM 非依存のサブコマンド（`init`、`agents`、`build`、`select`、`aggregate`）を持つ補助的な開発者ユーティリティ。プラグインのスキルはこれを `uvx` でエフェメラル実行します。レビューの実行にインストールは不要です。

導入方法は [インストール](installation.md)、開発者向け CLI は [CLI リファレンス](cli.md) を参照してください。

## 主な特徴

### プラグインのワークフロー

レビューは 2 つのスキルにより、Claude Code 内から完結して実行されます。

- `/hachimoku:setup` — プロジェクトごとに 1 回実行します。レビューサブエージェントを `.claude/agents/` に、`.claude/manifest.json` を生成します。
- `/hachimoku:review` — レビューをオーケストレーションします。PR 番号、ファイルパス、または引数なし（現在ブランチの差分）を受け付けます。

### エージェント

複数のビルトインレビューサブエージェントを標準提供します。コード品質、セキュリティ、依存関係監査、型設計、テストカバレッジ、コメントの正確性、コード簡潔化といった観点をカバーします。

エージェントは `.hachimoku/agents/` に TOML 形式で定義されており、プロジェクト固有のカスタムエージェントを追加できます。
詳細は [エージェント定義](agents.md) を参照してください。

### 決定的な選択と集約

エージェント選択（`hachimoku select`）とレポート集約（`hachimoku aggregate`）は、LLM 枠を消費しない決定的な CLI ステップとして実行されます。モデルを使用するのは、Claude Code セッション内で動作するレビューサブエージェント自体のみです。

### セキュリティ

レビューサブエージェントは `PreToolUse` hook（`block-git-mutations.sh`）付きで生成されます。この hook は `git`/`gh` の読み取り専用アクセスに制限するため、レビューがリポジトリの状態を変更することはできません。

### 出力と履歴

- レビューレポートは Markdown として生成され、Claude Code セッション内で提示されます
- レビュー結果は `.hachimoku/reviews/` 配下に JSONL 形式で自動蓄積されます
- 薄い CLI はレポート出力（stdout）と進捗・ログ（stderr）を分離します

### 設定

TOML ベースの階層的な設定をサポートします。

- `.hachimoku/config.toml` > `pyproject.toml [tool.hachimoku]` > `~/.config/hachimoku/config.toml` > デフォルト

詳細は [設定](configuration.md) を参照してください。

### ドメインモデル

レビュー結果は型安全なドメインモデルで管理されます。
Severity（4段階重大度）、ReviewIssue（問題の統一表現）、AgentResult（成功/エラーの判別共用体）、ReviewReport（結果集約レポート）、ToolCategory（ツールカテゴリ）、ReviewHistoryRecord（レビュー履歴レコード）を提供します。
詳細は [ドメインモデル](models.md) を参照してください。

```{toctree}
:maxdepth: 2
:caption: Contents

installation
cli
agents
configuration
models
review-context
```
