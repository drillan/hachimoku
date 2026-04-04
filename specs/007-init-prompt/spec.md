# 007: init 未実行時のプロンプト表示

## 概要

`8moku` コマンドをレビューモードで実行した際、`.hachimoku/` ディレクトリが存在しない場合にレビュー実行前にユーザーへ選択肢を提示する。

## 背景

現状、`.hachimoku/` がなくてもレビュー自体は完了するが、完了後に `Warning: Cannot save review history: .hachimoku/ directory not found.` と表示される。レビューの API コール・時間を消費した後に警告が出るのは UX として望ましくない。

## 要件

### FR-INIT-001: レビュー前の .hachimoku/ 存在チェック

- `review_callback` 内の入力モード判定（`resolve_input`）直後、config 解決（`resolve_config`）前に `find_project_root(Path.cwd())` で `.hachimoku/` の存在を確認する
- `.hachimoku/` が存在しない場合、ユーザーにプロンプトを表示する
- 全モード（diff / PR / file）共通で適用する

### FR-INIT-002: 3択プロンプト

stderr に以下の形式で表示する:

```
.hachimoku/ directory not found.

  [1] Run 8moku init (recommended)
  [2] Continue without saving reviews
  [3] Cancel

Select [1/2/3]:
```

各選択肢の動作:

| 選択 | 動作 |
|------|------|
| 1 | `run_init(Path.cwd())` を実行し、init 結果を stderr に表示後、レビューを続行する |
| 2 | `config_overrides["save_reviews"] = False` を設定し、レビューを続行する（保存スキップ） |
| 3 | `ExitCode.SUCCESS` で終了する |
| 無効入力 | 再プロンプトする |

### FR-INIT-003: 非インタラクティブ環境

stdin が TTY でない場合はプロンプトを表示できないため、エラーメッセージを出力して `ExitCode.INPUT_ERROR` で終了する。

```
Error: .hachimoku/ directory not found. Run '8moku init' to initialize.
```

### FR-INIT-004: init 失敗時のエラーハンドリング

選択肢 1 で `run_init` が `InitError` を送出した場合、エラーメッセージを stderr に表示し `ExitCode.EXECUTION_ERROR` で終了する（レビューには進まない）。

### FR-INIT-005: --no-confirm との関係

`--no-confirm` フラグはこのプロンプトに影響しない。init プロンプトは常に表示する。

## 実装方針

### 変更ファイル

`src/hachimoku/cli/_app.py` のみ。

### ヘルパー関数

`_prompt_missing_project(config_overrides: dict[str, object]) -> None` を追加する。

- `find_project_root` が `None` の場合に呼び出される
- 選択肢 1: `run_init()` 実行 → init 結果を stderr に表示 → return（レビュー続行）
- 選択肢 2: `config_overrides["save_reviews"] = False` を設定 → return（レビュー続行）
- 選択肢 3: `typer.Exit(code=ExitCode.SUCCESS)` で終了
- 非 TTY: エラーメッセージ出力 → `typer.Exit(code=ExitCode.INPUT_ERROR)` で終了

### review_callback 内の挿入位置

```python
# 1. 入力モード判定
resolved = resolve_input(raw_args or None)

# 2. config_overrides 構築
config_overrides = _build_config_overrides(...)

# ★ NEW: .hachimoku/ 存在チェック
project_root = find_project_root(Path.cwd())
if project_root is None:
    _prompt_missing_project(config_overrides)

# 3. config 解決
config = resolve_config(cli_overrides=config_overrides)
```

### 既存コードへの影響

- `_save_review_result` 内の `find_project_root` チェック（634-640行目）は安全ネットとしてそのまま残す
- init 成功時は `resolve_config` が `config.toml` を正しく読み込む

## 対象外

- `--no-confirm` による init プロンプトスキップ
- `init` サブコマンド自体の変更
- `agents` / `config` サブコマンドへの影響
