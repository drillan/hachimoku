# Init Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.hachimoku/` が存在しない状態でレビューコマンドを実行した際、レビュー前に init / 続行 / キャンセルの 3 択プロンプトを表示する。

**Architecture:** `review_callback` の入力モード判定後・config 解決前に `find_project_root` チェックを追加。ヘルパー関数 `_prompt_missing_project` でプロンプト表示・選択肢処理を行う。変更対象は `src/hachimoku/cli/_app.py` と `tests/unit/cli/` のみ。

**Tech Stack:** Python 3.13+, Typer, Click (prompt/echo), sys.stdin.isatty()

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/hachimoku/cli/_app.py` | Modify | `_prompt_missing_project` 関数追加 + `review_callback` への組み込み |
| `tests/unit/cli/conftest.py` | Modify | `find_project_root` の autouse モック追加 |
| `tests/unit/cli/test_app.py` | Modify | 新テストクラス追加 + 既存テスト更新 |

---

### Task 1: Prerequisites — conftest autouse fixture

**Files:**
- Modify: `tests/unit/cli/conftest.py`

- [ ] **Step 1: Add autouse fixture for find_project_root**

`review_callback` に `.hachimoku/` チェックを追加すると、CliRunner（非 TTY）では全テストが `INPUT_ERROR` で失敗する。これを防ぐため、デフォルトで有効なプロジェクトルートを返す autouse fixture を追加する。

```python
# tests/unit/cli/conftest.py — 既存 import に追加:
# from collections.abc import Iterator は既存
# from pathlib import Path は既存
# from unittest.mock import patch は既存

# 既存の _prevent_review_history_writes の後に追加:

@pytest.fixture(autouse=True)
def _mock_project_root() -> Iterator[None]:
    """テスト環境に依存しないプロジェクトルートを提供する。

    review_callback の .hachimoku/ 存在チェック（FR-INIT-001）が
    テスト実行環境のファイルシステムに依存しないようにする。
    個別テストで @patch(PATCH_FIND_PROJECT_ROOT, return_value=None) でオーバーライド可能。
    """
    with patch(PATCH_FIND_PROJECT_ROOT, return_value=Path("/mock/root")):
        yield
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py -v --tb=short`
Expected: ALL PASS（既存テスト全件パス）

- [ ] **Step 3: Commit**

```bash
git add tests/unit/cli/conftest.py
git commit -m "test: add autouse fixture for find_project_root mock"
```

---

### Task 2: Non-interactive path (FR-INIT-003)

**Files:**
- Test: `tests/unit/cli/test_app.py`
- Modify: `src/hachimoku/cli/_app.py`

- [ ] **Step 1: Write failing test**

`tests/unit/cli/test_app.py` に新テストクラスを追加する。`TestSaveReviewResult` クラスの直前に配置する。

```python
PATCH_STDIN = "sys.stdin"


class TestInitPrompt:
    """init 未実行時のプロンプト動作を検証する（FR-INIT-001〜005）。"""

    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_non_interactive_exits_with_input_error(
        self, _mock_root: MagicMock, mock_stdin: MagicMock
    ) -> None:
        """非 TTY 環境 + .hachimoku/ なし → INPUT_ERROR で終了。"""
        mock_stdin.isatty.return_value = False
        result = runner.invoke(app)
        assert result.exit_code == ExitCode.INPUT_ERROR

    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_non_interactive_shows_init_hint(
        self, _mock_root: MagicMock, mock_stdin: MagicMock
    ) -> None:
        """非 TTY 環境のエラーメッセージに init コマンドのヒントが含まれる。"""
        mock_stdin.isatty.return_value = False
        result = runner.invoke(app)
        assert "Run '8moku init'" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py::TestInitPrompt -v`
Expected: FAIL（`_prompt_missing_project` が未定義）

- [ ] **Step 3: Implement `_prompt_missing_project` (non-interactive branch) and wire into `review_callback`**

`src/hachimoku/cli/_app.py` に以下を追加する。

関数 `_prompt_missing_project` を `_is_git_repository` 関数の直後（`class _ReviewGroup` の直前）に配置:

```python
def _prompt_missing_project(config_overrides: dict[str, object]) -> None:
    """.hachimoku/ 未検出時にユーザーへ選択肢を提示する。

    FR-INIT-001: レビュー前チェック。
    FR-INIT-002: 3 択プロンプト（init / 続行 / キャンセル）。
    FR-INIT-003: 非インタラクティブ環境ではエラー終了。
    FR-INIT-004: init 失敗時はエラー終了。
    """
    if not sys.stdin.isatty():
        print(
            "Error: .hachimoku/ directory not found. "
            "Run '8moku init' to initialize.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.INPUT_ERROR)
```

`review_callback` 内に呼び出しを追加する。
`config_overrides = _build_config_overrides(...)` の直後、`config = resolve_config(...)` の直前:

```python
    # 2.5. .hachimoku/ 存在チェック（FR-INIT-001）
    if find_project_root(Path.cwd()) is None:
        _prompt_missing_project(config_overrides)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py::TestInitPrompt -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hachimoku/cli/_app.py tests/unit/cli/test_app.py
git commit -m "feat(#334): add non-interactive check for missing .hachimoku/"
```

---

### Task 3: Interactive paths — cancel, continue, invalid input (FR-INIT-002)

**Files:**
- Test: `tests/unit/cli/test_app.py`
- Modify: `src/hachimoku/cli/_app.py`

- [ ] **Step 1: Write failing tests**

`TestInitPrompt` クラスに追加:

```python
    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_choice_3_cancels_with_success(
        self, _mock_root: MagicMock, mock_stdin: MagicMock
    ) -> None:
        """選択肢 3 → ExitCode.SUCCESS で終了、レビュー実行なし。"""
        mock_stdin.isatty.return_value = True
        result = runner.invoke(app, input="3\n")
        assert result.exit_code == ExitCode.SUCCESS

    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_choice_2_continues_without_saving(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_root: MagicMock,
        mock_stdin: MagicMock,
    ) -> None:
        """選択肢 2 → save_reviews=False でレビュー続行。"""
        mock_stdin.isatty.return_value = True
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app, input="2\n")
        assert result.exit_code == 0
        mock_run_review.assert_called_once()

    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_choice_2_sets_save_reviews_false(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_root: MagicMock,
        mock_stdin: MagicMock,
    ) -> None:
        """選択肢 2 → resolve_config に save_reviews=False が渡される。"""
        mock_stdin.isatty.return_value = True
        setup_mocks(mock_config, mock_run_review)
        runner.invoke(app, input="2\n")
        cli_overrides = mock_config.call_args.kwargs["cli_overrides"]
        assert cli_overrides["save_reviews"] is False

    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_invalid_then_cancel(
        self, _mock_root: MagicMock, mock_stdin: MagicMock
    ) -> None:
        """無効入力 → 再プロンプト → 選択肢 3 で終了。"""
        mock_stdin.isatty.return_value = True
        result = runner.invoke(app, input="x\n3\n")
        assert result.exit_code == ExitCode.SUCCESS
        assert "Invalid choice" in result.output

    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_prompt_shows_menu(
        self, _mock_root: MagicMock, mock_stdin: MagicMock
    ) -> None:
        """プロンプトに 3 択メニューが表示される。"""
        mock_stdin.isatty.return_value = True
        result = runner.invoke(app, input="3\n")
        assert "[1]" in result.output
        assert "[2]" in result.output
        assert "[3]" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py::TestInitPrompt -v -k "not non_interactive"`
Expected: FAIL（インタラクティブ分岐が未実装）

- [ ] **Step 3: Implement interactive branch of `_prompt_missing_project`**

`_prompt_missing_project` 関数を完成させる。非インタラクティブ分岐の後に追加:

```python
    print(
        ".hachimoku/ directory not found.\n\n"
        "  [1] Run 8moku init (recommended)\n"
        "  [2] Continue without saving reviews\n"
        "  [3] Cancel\n",
        file=sys.stderr,
    )

    while True:
        try:
            choice = click.prompt("Select [1/2/3]", type=str, err=True)
        except (EOFError, click.Abort):
            raise typer.Exit(code=ExitCode.SUCCESS) from None

        if choice == "1":
            try:
                result = run_init(Path.cwd())
            except InitError as e:
                print(f"Error: Initialization failed: {e}", file=sys.stderr)
                raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None
            for path in result.created:
                print(f"  Created: {path}", file=sys.stderr)
            for path in result.skipped:
                print(f"  Skipped (already exists): {path}", file=sys.stderr)
            return

        if choice == "2":
            config_overrides["save_reviews"] = False
            return

        if choice == "3":
            raise typer.Exit(code=ExitCode.SUCCESS)

        click.echo(
            f"Error: Invalid choice '{choice}'. Please enter 1, 2, or 3.",
            err=True,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py::TestInitPrompt -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/hachimoku/cli/_app.py tests/unit/cli/test_app.py
git commit -m "feat(#334): add interactive 3-choice prompt for missing .hachimoku/"
```

---

### Task 4: Interactive init path + error handling (FR-INIT-002 choice 1, FR-INIT-004)

**Files:**
- Test: `tests/unit/cli/test_app.py`
- (Implementation is already in Task 3 — this task adds tests for choice 1)

- [ ] **Step 1: Write failing tests**

`TestInitPrompt` クラスに追加:

```python
    @patch(PATCH_RUN_INIT)
    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_choice_1_runs_init_and_continues_review(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_root: MagicMock,
        mock_stdin: MagicMock,
        mock_run_init: MagicMock,
    ) -> None:
        """選択肢 1 → run_init 実行後、レビュー続行。"""
        mock_stdin.isatty.return_value = True
        setup_mocks(mock_config, mock_run_review)
        mock_run_init.return_value = InitResult()
        result = runner.invoke(app, input="1\n")
        assert result.exit_code == 0
        mock_run_init.assert_called_once()
        mock_run_review.assert_called_once()

    @patch(PATCH_RUN_INIT)
    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_choice_1_init_error_exits_with_execution_error(
        self,
        _mock_root: MagicMock,
        mock_stdin: MagicMock,
        mock_run_init: MagicMock,
    ) -> None:
        """選択肢 1 で InitError → EXECUTION_ERROR で終了。"""
        mock_stdin.isatty.return_value = True
        mock_run_init.side_effect = InitError("Permission denied")
        result = runner.invoke(app, input="1\n")
        assert result.exit_code == ExitCode.EXECUTION_ERROR

    @patch(PATCH_RUN_INIT)
    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_choice_1_init_error_shows_message(
        self,
        _mock_root: MagicMock,
        mock_stdin: MagicMock,
        mock_run_init: MagicMock,
    ) -> None:
        """InitError のメッセージが出力される。"""
        mock_stdin.isatty.return_value = True
        mock_run_init.side_effect = InitError("Permission denied")
        result = runner.invoke(app, input="1\n")
        assert "Permission denied" in result.output
        assert "Initialization failed" in result.output
```

- [ ] **Step 2: Run tests to verify they pass**

choice 1 の実装は Task 3 で完了済み。テストは Green であるはず。

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py::TestInitPrompt -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/cli/test_app.py
git commit -m "test(#334): add tests for init choice and error handling"
```

---

### Task 5: Update existing affected test + --no-confirm independence (FR-INIT-005)

**Files:**
- Test: `tests/unit/cli/test_app.py`

- [ ] **Step 1: Update existing conflicting test**

`TestSaveReviewResult.test_no_project_root_warns_and_exits_normally` は、`find_project_root=None` でレビュー完了後に警告が出ることを検証していた。新しい早期チェックにより、この状況ではレビュー前に `INPUT_ERROR` で終了する。テストを新しい動作に更新する。

既存テスト（削除対象）:
```python
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    @patch(PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(PATCH_RESOLVE_CONFIG)
    def test_no_project_root_warns_and_exits_normally(
        self,
        mock_config: MagicMock,
        mock_run_review: AsyncMock,
        _mock_root: MagicMock,
    ) -> None:
        """find_project_root=None → 警告出力、終了コード不変。"""
        setup_mocks(mock_config, mock_run_review)
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert ".hachimoku/ directory not found" in result.output
```

このテストを削除する。同等の動作は `TestInitPrompt.test_non_interactive_exits_with_input_error` でカバー済み。

- [ ] **Step 2: Add --no-confirm independence test**

`TestInitPrompt` クラスに追加:

```python
    @patch(PATCH_STDIN)
    @patch(PATCH_FIND_PROJECT_ROOT, return_value=None)
    def test_no_confirm_does_not_skip_prompt(
        self, _mock_root: MagicMock, mock_stdin: MagicMock
    ) -> None:
        """--no-confirm は init プロンプトに影響しない（FR-INIT-005）。"""
        mock_stdin.isatty.return_value = True
        result = runner.invoke(app, ["--no-confirm"], input="3\n")
        assert result.exit_code == ExitCode.SUCCESS
        assert "[1]" in result.output
```

- [ ] **Step 3: Run full test suite**

Run: `uv --directory /home/driller/repo/hachimoku run pytest tests/unit/cli/test_app.py -v --tb=short`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/unit/cli/test_app.py
git commit -m "test(#334): update existing tests for early .hachimoku/ check"
```

---

### Task 6: Quality check

- [ ] **Step 1: Run linter + formatter + type checker**

```bash
cd /home/driller/repo/hachimoku && uv run ruff check --fix . && uv run ruff format . && uv run mypy .
```

Expected: エラーなし

- [ ] **Step 2: Run full test suite**

```bash
uv --directory /home/driller/repo/hachimoku run pytest -v --tb=short
```

Expected: ALL PASS

- [ ] **Step 3: Fix any issues found**

品質チェックで問題があれば修正する。

- [ ] **Step 4: Final commit (if fixes needed)**

```bash
git add -u
git commit -m "fix(#334): address quality check findings"
```
