# hachimoku Development Guidelines

マルチエージェントコードレビュー CLI ツール。
憲法全文: `.specify/memory/constitution.md` (v1.0.0)

## Tech Stack

- Python 3.13+ / pydantic v2 / typer
- エージェント定義: TOML（`.hachimoku/agents/*.toml`）
- 設定: `.hachimoku/config.toml`

## Project Structure

```text
src/hachimoku/    # メインパッケージ
tests/            # テスト（1機能=1ファイル: test_X.py ← X.py）
specs/            # 仕様書（SpecKit: 001-name, 002-name...）
```

## Commands

```bash
uv --directory $PROJECT_ROOT run pytest          # テスト
uv --directory $PROJECT_ROOT run ruff check .    # リント
uv --directory $PROJECT_ROOT run ruff format .   # フォーマット
uv --directory $PROJECT_ROOT run mypy .          # 型チェック
# コミット前必須: ruff check --fix . && ruff format . && mypy .
```

## プロジェクト固有ルール

以下はグローバル CLAUDE.md に**ない**、hachimoku 固有のルール。

### CLI 設計（憲法 Art.3）

- stdout: レビューレポートのみ / stderr: 進捗・ログ・エラー
- 終了コード: 0=成功, 1=Critical, 2=Important, 3=実行エラー, 4=入力エラー
- 全コマンドに `--help` 必須、エラーメッセージに解決方法を含める

### データ駆動型アーキテクチャ（憲法 Art.3）

- エージェントは TOML 定義ファイルで外部化（コード変更なしで拡張可能）
- 設定は `.hachimoku/config.toml` で一元管理

### シンプルさ（憲法 Art.4）

- 最大3プロジェクト構造。追加には文書化された正当な理由が必要
- フレームワーク機能を直接使用。不必要なラッパー禁止

### Docstring（憲法 Art.10, SHOULD）

- public モジュール・クラス・関数に Google-style docstring 推奨
- 複雑な private 関数（10行以上）にも推奨

### 命名規則（憲法 Art.11）

- Git ブランチ・コミット: `.claude/git-conventions.md` に従う
- SpecKit ディレクトリ: `<3桁issue番号>-<name>`（例: `002-domain-models`）

<!-- MANUAL ADDITIONS START -->

## ドキュメント

- ビルド: `make -C docs html`
- ルール: `.claude/docs.md`

<!-- MANUAL ADDITIONS END -->

## Active Technologies
- Python 3.13+ + pydantic ≥2.12.5（バリデーション）, tomllib（Python 標準ライブラリ、TOML パース）, importlib.resources（ビルトイン定義のパッケージ内配置）, fnmatch（ファイルパターンマッチング）, re（コンテンツパターンマッチング） (003-agent-definition)
- ファイルシステム（TOML 定義ファイル） (003-agent-definition)
- Python 3.13+ + pydantic ≥2.12.5（バリデーション）, tomllib（Python 標準ライブラリ、TOML パース）, pathlib（ファイルシステム操作） (004-configuration)
- ファイルシステム（TOML 設定ファイル） (004-configuration)

## Recent Changes
- 003-agent-definition: Added Python 3.13+ + pydantic ≥2.12.5（バリデーション）, tomllib（Python 標準ライブラリ、TOML パース）, importlib.resources（ビルトイン定義のパッケージ内配置）, fnmatch（ファイルパターンマッチング）, re（コンテンツパターンマッチング）
