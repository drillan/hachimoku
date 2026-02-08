# hachimoku

hachimoku（8moku）は、複数の専門エージェントを用いてコードレビューを行う CLI ツールです。
エージェントの定義は TOML ファイルで管理され、コード変更なしにレビュー観点を追加・カスタマイズできます。

## 主な特徴

### レビューモード

3つのモードでレビュー対象を指定します。

- diff モード（`8moku`）: 現在ブランチの変更差分をレビュー
- PR モード（`8moku <PR番号>`）: GitHub PR の差分とメタデータをレビュー
- file モード（`8moku <ファイルパス...>`）: 指定ファイルの全体をレビュー。Git リポジトリ外でも動作

### エージェント

6つのビルトインエージェントを標準提供します。

- code-reviewer: コード品質・バグ検出
- silent-failure-hunter: サイレント障害の検出
- pr-test-analyzer: テストカバレッジの評価
- type-design-analyzer: 型設計の分析
- comment-analyzer: コメントの正確性分析
- code-simplifier: コード簡潔化の提案

エージェントは `.hachimoku/agents/` に TOML 形式で定義されており、プロジェクト固有のカスタムエージェントを追加できます。
詳細は [エージェント定義](agents.md) を参照してください。

### 実行と出力

- 逐次実行と並列実行を選択可能
- 出力形式は Markdown（人間向け）と JSON（機械向け）に対応
- レビュー結果は `.hachimoku/reviews/` に JSONL 形式で自動蓄積
- レビューレポートは stdout、進捗情報は stderr に出力され、パイプやリダイレクトに対応

### 設定

TOML ベースの階層的な設定をサポートします。

- CLI オプション > `.hachimoku/config.toml` > `pyproject.toml [tool.hachimoku]` > `~/.config/hachimoku/config.toml` > デフォルト

詳細は [設定](configuration.md) を参照してください。

### ドメインモデル

レビュー結果は型安全なドメインモデルで管理されます。
Severity（4段階重大度）、ReviewIssue（問題の統一表現）、AgentResult（判別共用体による成功/切り詰め/エラー/タイムアウト）、ReviewReport（結果集約レポート）、ToolCategory（ツールカテゴリ）、ReviewHistoryRecord（レビュー履歴レコード）を提供します。
詳細は [ドメインモデル](models.md) を参照してください。

```{toctree}
:maxdepth: 2
:caption: Contents

installation
cli
agents
configuration
models
```
