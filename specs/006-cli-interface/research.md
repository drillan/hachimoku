# Research: CLI インターフェース・初期化

**Feature**: 006-cli-interface | **Date**: 2026-02-07

## R-001: Typer サブコマンドと callback の共存パターン

**Decision**: `callback(invoke_without_command=True)` を使い、サブコマンド未指定時にデフォルト動作（レビュー実行）を実行する。`init` / `agents` は `@app.command()` で登録する。

**Rationale**: Typer の標準機構を直接使用（憲法 Art.4）。`invoke_without_command=True` により、引数なし実行時に callback が呼ばれ diff モードとして動作する。サブコマンド指定時は callback がスキップされ、対応する command 関数が呼ばれる。

**Alternatives considered**:
- Click グループ + 手動サブコマンド登録: Typer の上位互換を手動で再実装することになり、不要な複雑さ
- 単一コマンド + 引数パターンマッチ: サブコマンドの `--help` 自動生成が使えない

**実装詳細**:
```python
app = typer.Typer()

@app.callback(invoke_without_command=True)
def review_callback(ctx: typer.Context, ...):
    if ctx.invoked_subcommand is None:
        # レビュー実行（diff/PR/file モード）
        ...

@app.command()
def init(...): ...

@app.command()
def agents(...): ...
```

## R-002: デュアルコマンド名（`8moku` / `hachimoku`）の実現方式

**Decision**: `pyproject.toml` の `[project.scripts]` に2エントリを登録し、同一の `main()` 関数を参照する。

**Rationale**: Python パッケージングの標準的な方法。追加コードなしで2つのコマンド名を提供できる。

**Alternatives considered**:
- シェルエイリアス: ユーザー環境依存、ポータブルでない
- シンボリックリンク: インストール時の追加処理が必要

**実装**:
```toml
[project.scripts]
8moku = "hachimoku.cli:main"
hachimoku = "hachimoku.cli:main"
```

## R-003: 位置引数の入力モード判定ロジック

**Decision**: Typer の `Argument(default=None)` で可変長位置引数を受け取り、`_input_resolver.py` で FR-CLI-002 の優先順ルールを適用する。

**Rationale**: 判定ロジックを純粋関数として分離し、テスト容易性を確保。Typer のサブコマンド判定はフレームワークに任せ、callback 内では位置引数のみを処理する。

**判定アルゴリズム**:
1. サブコマンド文字列 → Typer が自動処理（callback に到達しない）
2. 引数なし → DiffTarget（base_branch は config から取得）
3. 全引数が正の整数、かつ引数が1つ → PRTarget
4. パスライク文字（`/`, `\`, `*`, `?`, `.` を含む）or ファイルシステム存在 → FileTarget
5. 整数とパスライクが混在 → エラー（終了コード 4）
6. いずれにも該当しない → エラー（終了コード 4）

**Alternatives considered**:
- argparse: Typer が内部で Click を使用しており、argparse は不要
- 正規表現ベースのパース: Typer の型アノテーションシステムで十分

## R-004: file モードの glob 展開・ディレクトリ再帰探索

**Decision**: Python 標準ライブラリ（`pathlib.Path.rglob()`, `glob.glob()`）を使用する。外部ライブラリの追加は不要。

**Rationale**: 仕様の Assumptions に明記。標準ライブラリで十分な機能が提供される。

**シンボリックリンク循環参照検出**:
- `Path.resolve()` で実体パスを取得
- 探索済みディレクトリの `set[Path]` で重複を検出
- 循環参照検出時は警告を stderr に出力してスキップ

**Alternatives considered**:
- `os.walk()` + `followlinks=True`: シンボリックリンクの循環参照が無限ループになるリスク
- `pathspec` ライブラリ: 外部依存の追加は不要（`.gitignore` パターンのサポートは 006 のスコープ外）

## R-005: Typer での boolean フラグペア

**Decision**: `typer.Option("--parallel/--no-parallel", default=None)` で三値（True/False/None）を表現する。None は「未指定」で、config_overrides 辞書に含めない。

**Rationale**: Typer の標準的なフラグペア機構。`filter_cli_overrides()` が None を除外するため、未指定時は設定ファイルのデフォルト値が使用される。

**Alternatives considered**:
- `bool | None` を手動パース: Typer の組み込み機能で十分
- 常に True/False を渡す: 設定ファイルの値を上書きしてしまう

## R-006: 終了コード管理

**Decision**: `ExitCode` を `IntEnum` として定義し、005 の `EngineResult.exit_code`（0-3）と CLI 層の入力エラー（4）を統合する。

**Rationale**: 憲法 Art.6 に従い、マジックナンバーを回避して名前付き定数を使用する。

**実装**:
```python
class ExitCode(IntEnum):
    SUCCESS = 0
    CRITICAL = 1
    IMPORTANT = 2
    EXECUTION_ERROR = 3
    INPUT_ERROR = 4
```

## R-007: init コマンドのテンプレート生成

**Decision**: config.toml テンプレートは Python 文字列定数として定義する。ビルトインエージェント定義は `importlib.resources` で 003 パッケージからコピーする。

**Rationale**: config.toml はコメント付きテンプレート（全設定項目をコメントアウトして記載）であり、TOML パーサーの機能だけでは生成できない。ビルトインエージェント定義は 003 が既にパッケージ内にバンドルしている。

**テンプレート内容**: HachimokuConfig のデフォルト値を反映した全設定項目をコメントとして記載。ユーザーはコメントを解除して設定をカスタマイズする。

## R-008: 確認プロンプトの実装

**Decision**: `typer.confirm()` を使用する。stderr に警告メッセージを出力後、stdin からの入力を受け付ける。

**Rationale**: Typer の組み込み機能を直接使用（憲法 Art.4）。`--no-confirm` 指定時はプロンプトをスキップする。CI/CD 環境では `--no-confirm` の使用を推奨。

**Alternatives considered**:
- `input()` 直接使用: Typer の confirm が abort 処理やエラーハンドリングを提供
- Rich prompt: Typer が Rich を内部使用しており、追加依存不要

## R-009: `config` 予約サブコマンド

**Decision**: `@app.command()` で登録し、実行時に未実装メッセージを stderr に出力後 `typer.Exit(code=4)` で終了する。

**Rationale**: 親仕様 FR-021 との整合性を保ちつつ、v0.1 では未実装とする仕様の明示的な要求。Typer コマンド内では `typer.Exit` で終了する（R-010 参照）。

## R-010: Typer の `raise SystemExit` vs `sys.exit()`

**Decision**: Typer callback/command 内で `raise typer.Exit(code=N)` を使用する。

**Rationale**: Typer の標準的な終了方法。`sys.exit()` は pytest での捕捉が困難だが、`typer.Exit` は Typer の CliRunner が適切に処理する。

**テスト**: `typer.testing.CliRunner` を使用し、`result.exit_code` で終了コードを検証する。
