# Quickstart: CLI インターフェース・初期化

**Feature**: 006-cli-interface | **Date**: 2026-02-07

## 前提条件

- 002-005 が実装済み
- `typer>=0.21.1` が `pyproject.toml` に登録済み

## 実装順序

### Phase 1: P1 — 基本 CLI・レビュー実行

1. **ExitCode** (`_exit_code.py`): IntEnum 定義（最小単位、依存なし）
2. **InputResolver** (`_input_resolver.py`): 位置引数 → ResolvedInput 判定
3. **CliApp** (`_app.py`): Typer app + callback + review 実行フロー
4. **pyproject.toml**: デュアルコマンド名エントリ追加
5. **`__init__.py`**: main() → cli.main() への委譲

### Phase 2: P2 — init・file モード

6. **InitHandler** (`_init_handler.py`): .hachimoku/ 初期化ロジック
7. **FileResolver** (`_file_resolver.py`): glob/ディレクトリ展開・確認プロンプト
8. **CliApp 拡張**: init サブコマンド + file モード完全対応

### Phase 3: P3 — agents 管理

9. **CliApp 拡張**: agents サブコマンド（一覧・詳細表示）
10. **config 予約サブコマンド**: 未実装エラー返却

## TDD ワークフロー（各ステップ共通）

```
1. テスト作成 → ユーザー承認
2. Red 確認（pytest 実行、テスト失敗を確認）
3. 実装（Green）
4. 品質チェック: ruff check --fix . && ruff format . && mypy .
5. 全テスト通過確認
```

## キーとなる API 連携

### CLI → Engine

```python
from hachimoku.engine import run_review, EngineResult
from hachimoku.engine._target import DiffTarget, PRTarget, FileTarget

# 使用例（diff モード）
target = DiffTarget(base_branch="main", issue_number=None)
config_overrides = {"model": "opus", "timeout": 600}  # None 除外済み
result: EngineResult = await run_review(target, config_overrides=config_overrides)
# result.exit_code: 0, 1, 2, or 3
# result.report: ReviewReport
```

### CLI → ConfigResolver

```python
from hachimoku.config import resolve_config

# CLI オプションを辞書化（None は除外）
overrides = {"model": "opus", "parallel": False}
config = resolve_config(cli_overrides=overrides)
```

### CLI → AgentLoader

```python
from hachimoku.agents import load_agents, load_builtin_agents

# agents サブコマンド用
result = load_agents(custom_dir=Path(".hachimoku/agents"))
for agent in result.agents:
    print(f"{agent.name}: {agent.model} ({agent.phase})")
```

### init → ビルトインエージェントコピー

```python
from importlib.resources import as_file, files

builtin_package = files("hachimoku.agents._builtin")
for resource in builtin_package.iterdir():
    if resource.name.endswith(".toml"):
        with as_file(resource) as src_path:
            # src_path → .hachimoku/agents/ にコピー
            ...
```

## テスト戦略

| テストファイル | 対象モジュール | 主なテスト手法 |
|--------------|--------------|--------------|
| `test_exit_code.py` | `_exit_code.py` | 値の検証、IntEnum 性質 |
| `test_input_resolver.py` | `_input_resolver.py` | 各パターンの判定結果検証 |
| `test_file_resolver.py` | `_file_resolver.py` | tmp_path による FS モック |
| `test_init_handler.py` | `_init_handler.py` | tmp_path による FS モック |
| `test_app.py` | `_app.py` | typer.testing.CliRunner |

### CliRunner テストの典型パターン

```python
from typer.testing import CliRunner
from hachimoku.cli._app import app

runner = CliRunner()

def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Multi-agent code review" in result.output

def test_unknown_arg():
    result = runner.invoke(app, ["unknown_string_that_does_not_exist"])
    assert result.exit_code == 4
```
