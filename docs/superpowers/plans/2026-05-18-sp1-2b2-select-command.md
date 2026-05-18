# SP1-2b-2: select コマンド Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `8moku select` コマンドを実装する。4モード（diff / commit / pr / file）の変更内容を計算し、`Manifest` の applicability 評価で起動対象エージェントを決定、run_dir を作成してディスパッチプラン JSON を出力する。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §5。`select` は LLM を用いない決定的コマンド。変更内容計算（`review/changeset.py`、新規）→ `select_agent_names`（SP1-2b-1 で実装済み）→ run_dir 作成 → `DispatchPlan` JSON 出力。`Manifest` は `--manifest` で受け取る（生成側 `build` は SP2。本計画ではテスト用 fixture manifest で検証）。

**Tech Stack:** Python 3.13+ / pydantic v2 / Typer / subprocess（git/gh）/ pytest / ruff / mypy / uv

**前提:** SP1-1・SP1-2a・SP1-2b-1 完了済みのブランチ `worktree-sp1-engine-removal` の上で実行する。`agents/manifest.py`（`Manifest`/`ManifestEntry`）と `agents/applicability.py`（`select_agent_names`）は実装済み。

---

## 設計決定

### `select` の CLI サーフェス

`8moku select` サブコマンド。引数:
- 位置引数 `[ARGS...]` — `resolve_input`（`cli/_input_resolver.py`、既存）で diff / pr / file モードを判定。
- `--commit REF` — commit モード。`SHA` または `SHA1..SHA2`。位置引数との併用は不可。
- `--base-branch B` — diff モードのベースブランチ（既定 `main`）。
- `--manifest PATH` — `Manifest` JSON ファイルのパス（**必須**）。

モード判定は旧 CLI（撤去済み `_app.py` の `review_callback`）と同じ規則を踏襲する。

### 変更内容計算（`ChangeSet`）

`review/changeset.py`（新規）に `ChangeSet`（`changed_basenames: frozenset[str]`、`content: str`）と、`ReviewTarget`（`review/target.py` の判別共用体）からモード別に計算する関数群を置く。

| モード | changed_basenames | content |
|--------|-------------------|---------|
| diff | `git diff --name-only {base}...HEAD` の各行 basename | `git diff {base}...HEAD` |
| commit | `git diff --name-only {from} {to}` の各行 basename | `git diff {from} {to}` |
| pr | `gh pr diff {n} --name-only` の各行 basename | `gh pr diff {n}` |
| file | 解決済みパスの basename（`resolve_files` で glob/dir 展開） | 解決済み各ファイルの内容を連結 |

git/gh 実行失敗・未インストール・タイムアウトは `ChangeSetError` を送出する（フォールバックしない）。

### `DispatchPlan` と run_dir

- `DispatchPlan`（`cli/_select.py` に定義）: `run_dir: str`（絶対パス）、`phases: dict[Phase, list[str]]`。stdout に JSON 出力。
- run_dir: `select` が `tempfile.mkdtemp(prefix="hachimoku-run-")` で作成する一時ディレクトリ。サブエージェントの findings 出力先・`aggregate` の入力。絶対パスを `DispatchPlan.run_dir` に格納。

## File Structure

**新規作成:**
- `src/hachimoku/review/changeset.py` — `ChangeSet`・`ChangeSetError`・`compute_changeset`
- `src/hachimoku/cli/_select.py` — `DispatchPlan`・`run_select`
- `tests/unit/review/test_changeset.py`
- `tests/unit/cli/test_select.py`

**変更:**
- `src/hachimoku/cli/_app.py` — `select` サブコマンドを登録

---

## Task 1: 変更内容計算（`review/changeset.py`）

**Files:**
- Create: `src/hachimoku/review/changeset.py`
- Test: `tests/unit/review/test_changeset.py`

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で `uv run` を用いて実行する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/review/test_changeset.py` を作成:

```python
"""changeset 計算のテスト。"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hachimoku.review.changeset import ChangeSet, ChangeSetError, compute_changeset
from hachimoku.review.target import CommitTarget, DiffTarget, FileTarget


def _init_repo(path: Path) -> None:
    """テスト用 git リポジトリを初期化する。"""
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True, capture_output=True)


def _commit_all(path: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=path, check=True, capture_output=True)
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, check=True, capture_output=True, text=True
    )
    return rev.stdout.strip()


class TestComputeChangesetDiff:
    def test_diff_mode_collects_changed_basenames_and_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "base.py").write_text("x = 1\n")
        _commit_all(tmp_path, "base")
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "feature.py").write_text("y = 2  # NEWLINE\n")
        _commit_all(tmp_path, "feature")
        monkeypatch.chdir(tmp_path)

        result = compute_changeset(DiffTarget(base_branch="main"))

        assert isinstance(result, ChangeSet)
        assert "feature.py" in result.changed_basenames
        assert "NEWLINE" in result.content


class TestComputeChangesetCommit:
    def test_commit_mode_uses_ref_range(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "a.py").write_text("a = 1\n")
        first = _commit_all(tmp_path, "first")
        (tmp_path / "b.py").write_text("b = 2\n")
        second = _commit_all(tmp_path, "second")
        monkeypatch.chdir(tmp_path)

        result = compute_changeset(CommitTarget(from_ref=first, to_ref=second))

        assert "b.py" in result.changed_basenames
        assert "a.py" not in result.changed_basenames


class TestComputeChangesetFile:
    def test_file_mode_reads_file_contents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "target.py").write_text("z = 3  # MARKER\n")
        monkeypatch.chdir(tmp_path)

        result = compute_changeset(FileTarget(paths=("target.py",)))

        assert "target.py" in result.changed_basenames
        assert "MARKER" in result.content


class TestComputeChangesetErrors:
    def test_diff_mode_outside_git_repo_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)  # git リポジトリではない
        with pytest.raises(ChangeSetError):
            compute_changeset(DiffTarget(base_branch="main"))
```

> pr モードは `gh` 認証と実 PR が必要なため単体テストでは検証せず、Task 2 の `select` 統合および手動検証で確認する。本 Task では diff / commit / file の3モードと異常系をテストする。

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/review/test_changeset.py -v`
Expected: FAIL（`ModuleNotFoundError: hachimoku.review.changeset`）

- [ ] **Step 3: `review/changeset.py` を実装する**

`src/hachimoku/review/changeset.py` を作成:

```python
"""変更内容計算 — レビュー対象から変更ファイルと内容を取得する。

select コマンドが applicability 評価の入力（変更ファイル basename 集合と
diff 内容）を得るために使用する。git / gh を subprocess で呼び出す。
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePath
from typing import Final

from pydantic import Field

from hachimoku.cli._file_resolver import FileResolutionError, resolve_files
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.review.target import (
    CommitTarget,
    DiffTarget,
    FileTarget,
    PRTarget,
    ReviewTarget,
)

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120


class ChangeSetError(Exception):
    """変更内容計算のエラー。git/gh 実行失敗・未インストール・タイムアウト等。"""


class ChangeSet(HachimokuBaseModel):
    """レビュー対象の変更内容。

    Attributes:
        changed_basenames: 変更ファイルの basename 集合。
        content: 変更内容テキスト（diff またはファイル内容）。
    """

    changed_basenames: frozenset[str]
    content: str


def _run(cmd: list[str]) -> str:
    """サブプロセスを実行し stdout を返す。失敗時は ChangeSetError。"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise ChangeSetError(
            f"Command not found: {cmd[0]}. Ensure it is installed and in PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ChangeSetError(
            f"{' '.join(cmd)} timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ChangeSetError(
            f"{' '.join(cmd)} failed: {exc.stderr.strip()}"
        ) from exc
    return result.stdout


def _basenames(name_only_output: str) -> frozenset[str]:
    """git/gh の --name-only 出力から basename 集合を作る。"""
    return frozenset(
        PurePath(line).name for line in name_only_output.splitlines() if line
    )


def _changeset_from_git(diff_args: list[str]) -> ChangeSet:
    """git diff の引数（範囲指定）から ChangeSet を構築する。"""
    name_only = _run(["git", "diff", "--name-only", *diff_args])
    content = _run(["git", "diff", *diff_args])
    return ChangeSet(changed_basenames=_basenames(name_only), content=content)


def _changeset_diff(target: DiffTarget) -> ChangeSet:
    return _changeset_from_git([f"{target.base_branch}...HEAD"])


def _changeset_commit(target: CommitTarget) -> ChangeSet:
    return _changeset_from_git([target.from_ref, target.to_ref])


def _changeset_pr(target: PRTarget) -> ChangeSet:
    pr = str(target.pr_number)
    name_only = _run(["gh", "pr", "diff", pr, "--name-only"])
    content = _run(["gh", "pr", "diff", pr])
    return ChangeSet(changed_basenames=_basenames(name_only), content=content)


def _changeset_file(target: FileTarget) -> ChangeSet:
    try:
        resolved, _warnings = resolve_files(target.paths, filter_extensions=())
    except FileResolutionError as exc:
        raise ChangeSetError(str(exc)) from exc
    if resolved is None:
        raise ChangeSetError(
            f"No files found matching: {', '.join(target.paths)}."
        )
    basenames = frozenset(PurePath(p).name for p in resolved.paths)
    parts: list[str] = []
    for path in resolved.paths:
        try:
            parts.append(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            raise ChangeSetError(f"Failed to read {path}: {exc}") from exc
    return ChangeSet(changed_basenames=basenames, content="\n".join(parts))


def compute_changeset(target: ReviewTarget) -> ChangeSet:
    """レビュー対象から ChangeSet を計算する。

    Args:
        target: レビュー対象（diff / commit / pr / file のいずれか）。

    Returns:
        変更ファイル basename 集合と変更内容を保持する ChangeSet。

    Raises:
        ChangeSetError: git/gh 実行失敗、ファイル解決失敗、読み取り失敗時。
    """
    if isinstance(target, DiffTarget):
        return _changeset_diff(target)
    if isinstance(target, CommitTarget):
        return _changeset_commit(target)
    if isinstance(target, PRTarget):
        return _changeset_pr(target)
    return _changeset_file(target)
```

> `Path` はファイル読み取り（I/O）に、`PurePath` は basename 抽出（`.name`、I/O なし）に用いる。

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/review/test_changeset.py -v`
Expected: PASS（4 件）

- [ ] **Step 5: 静的検査とコミット**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy .`
Expected: エラーなし。その後:

```bash
git add src/hachimoku/review/changeset.py tests/unit/review/test_changeset.py
git commit -m "feat: add changeset computation for review targets"
```

---

## Task 2: select コマンド（`cli/_select.py` + `_app.py` 登録）

**Files:**
- Create: `src/hachimoku/cli/_select.py`
- Modify: `src/hachimoku/cli/_app.py`
- Test: `tests/unit/cli/test_select.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/cli/test_select.py` を作成:

```python
"""select コマンドのテスト。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest, ManifestEntry
from hachimoku.agents.models import ApplicabilityRule, Phase
from hachimoku.cli._app import app


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True, capture_output=True)


def _write_manifest(path: Path) -> Path:
    manifest = Manifest(
        version=MANIFEST_VERSION,
        entries=(
            ManifestEntry(
                name="always-agent",
                applicability=ApplicabilityRule(always=True),
                phase=Phase.MAIN,
                output_schema="scored_issues",
            ),
            ManifestEntry(
                name="py-agent",
                applicability=ApplicabilityRule(file_patterns=("*.py",)),
                phase=Phase.EARLY,
                output_schema="scored_issues",
            ),
            ManifestEntry(
                name="rust-agent",
                applicability=ApplicabilityRule(file_patterns=("*.rs",)),
                phase=Phase.MAIN,
                output_schema="scored_issues",
            ),
        ),
    )
    manifest_path = path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json())
    return manifest_path


class TestSelectCommand:
    def test_diff_mode_outputs_dispatch_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        (tmp_path / "base.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "feature.py").write_text("y = 2\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], cwd=tmp_path, check=True, capture_output=True)
        manifest_path = _write_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            app, ["select", "--manifest", str(manifest_path)]
        )

        assert result.exit_code == 0
        plan = json.loads(result.stdout)
        # *.py 変更 → py-agent(EARLY) と always-agent(MAIN) が選ばれ、rust-agent は除外
        assert plan["phases"]["early"] == ["py-agent"]
        assert plan["phases"]["main"] == ["always-agent"]
        assert plan["phases"]["final"] == []
        # run_dir が作成されている
        assert Path(plan["run_dir"]).is_dir()

    def test_missing_manifest_file_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            app, ["select", "--manifest", str(tmp_path / "nonexistent.json")]
        )
        assert result.exit_code != 0
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/cli/test_select.py -v`
Expected: FAIL（`select` サブコマンド未登録）

- [ ] **Step 3: `cli/_select.py` を実装する**

`src/hachimoku/cli/_select.py` を作成:

```python
"""select コマンド — レビュー対象から起動エージェントを決定する。

LLM を用いず、Manifest の applicability ルールで決定的に起動対象を選び、
run_dir を作成してディスパッチプラン JSON を stdout に出力する。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from pydantic import Field, ValidationError

from hachimoku.agents.applicability import select_agent_names
from hachimoku.agents.manifest import Manifest
from hachimoku.agents.models import Phase
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.exit_code import ExitCode
from hachimoku.review.changeset import ChangeSetError, compute_changeset
from hachimoku.review.target import ReviewTarget


class DispatchPlan(HachimokuBaseModel):
    """select コマンドの出力。オーケストレーターが消費する。

    Attributes:
        run_dir: サブエージェント findings の出力先ディレクトリ（絶対パス）。
        phases: フェーズ別の起動エージェント名リスト。
    """

    run_dir: str = Field(min_length=1)
    phases: dict[Phase, list[str]]


class SelectError(Exception):
    """select コマンドのエラー。"""


def load_manifest(manifest_path: Path) -> Manifest:
    """Manifest JSON を読み込む。

    Raises:
        SelectError: ファイルが存在しない・JSON 不正・スキーマ不適合の場合。
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SelectError(
            f"Cannot read manifest: {manifest_path}: {exc}\n"
            "Run '8moku build' to generate the manifest."
        ) from exc
    try:
        return Manifest.model_validate_json(raw)
    except ValidationError as exc:
        raise SelectError(f"Invalid manifest at {manifest_path}: {exc}") from exc


def run_select(target: ReviewTarget, manifest_path: Path) -> DispatchPlan:
    """select の中核処理。ChangeSet 計算 → applicability 評価 → run_dir 作成。

    Raises:
        SelectError: manifest 読み込み失敗時。
        ChangeSetError: 変更内容計算失敗時。
    """
    manifest = load_manifest(manifest_path)
    changeset = compute_changeset(target)
    phases = select_agent_names(
        manifest, changeset.changed_basenames, changeset.content
    )
    run_dir = tempfile.mkdtemp(prefix="hachimoku-run-")
    return DispatchPlan(run_dir=run_dir, phases=phases)


def select_command(target: ReviewTarget, manifest_path: Path) -> None:
    """select サブコマンドのエントリ。DispatchPlan を JSON で stdout 出力する。

    終了コード: 0=成功, 3=実行エラー, 4=入力エラー。
    """
    try:
        plan = run_select(target, manifest_path)
    except SelectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(ExitCode.INPUT_ERROR) from None
    except ChangeSetError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(ExitCode.EXECUTION_ERROR) from None
    print(plan.model_dump_json(indent=2))
```

> `dict[Phase, list[str]]` の JSON 出力: `Phase` は `StrEnum` なので `model_dump_json` でキーが `"early"`/`"main"`/`"final"` の文字列になる。テストの `plan["phases"]["early"]` はこれに依存する。

- [ ] **Step 4: `_app.py` に `select` サブコマンドを登録する**

`src/hachimoku/cli/_app.py` に以下を追加する。

(a) import 追加（既存の import 群の末尾付近）:
```python
from pathlib import Path  # 既存。なければ追加
from typing import Annotated  # 既存

from hachimoku.cli._input_resolver import (
    DiffInput,
    FileInput,
    InputError,
    PRInput,
    resolve_input,
)
from hachimoku.cli._select import select_command
from hachimoku.review.target import (
    CommitTarget,
    DiffTarget,
    FileTarget,
    PRTarget,
    ReviewTarget,
)
```

(b) `select` コマンド関数を `agents` コマンド定義の後に追加:
```python
@app.command()
def select(
    args: Annotated[
        list[str] | None,
        typer.Argument(help="PR number or file paths (omit for diff mode)."),
    ] = None,
    manifest: Annotated[
        Path,
        typer.Option("--manifest", help="Path to the manifest JSON file."),
    ] = ...,  # 必須
    commit: Annotated[
        str | None,
        typer.Option("--commit", help="Commit ref or range (SHA or SHA1..SHA2)."),
    ] = None,
    base_branch: Annotated[
        str, typer.Option("--base-branch", help="Base branch for diff mode.")
    ] = "main",
) -> None:
    """Select review agents for a target and emit a dispatch plan (JSON)."""
    target = _resolve_select_target(args, commit, base_branch)
    select_command(target, manifest)


def _resolve_select_target(
    args: list[str] | None, commit: str | None, base_branch: str
) -> ReviewTarget:
    """select の引数からレビュー対象を構築する。

    commit モードは位置引数と排他。それ以外は resolve_input でモード判定する。
    """
    if commit is not None:
        if args:
            print(
                "Error: --commit cannot be used with positional arguments.",
                file=sys.stderr,
            )
            raise typer.Exit(code=ExitCode.INPUT_ERROR)
        if ".." in commit:
            from_ref, _, to_ref = commit.partition("..")
            if not from_ref or not to_ref:
                print(
                    f"Error: Invalid commit range: '{commit}'. Use SHA1..SHA2.",
                    file=sys.stderr,
                )
                raise typer.Exit(code=ExitCode.INPUT_ERROR)
            return CommitTarget(from_ref=from_ref, to_ref=to_ref)
        return CommitTarget(from_ref=commit, to_ref="HEAD")

    try:
        resolved = resolve_input(args or None)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    if isinstance(resolved, DiffInput):
        return DiffTarget(base_branch=base_branch)
    if isinstance(resolved, PRInput):
        return PRTarget(pr_number=resolved.pr_number)
    if isinstance(resolved, FileInput):
        return FileTarget(paths=resolved.paths)
    msg = f"Unexpected resolved input: {resolved!r}"
    raise AssertionError(msg)
```

> `manifest: Annotated[Path, typer.Option(...)] = ...` の `...`（Ellipsis）は Typer で必須オプションを表す。`select_command` 内の `SystemExit` と `_resolve_select_target` 内の `typer.Exit` はいずれも CliRunner で非ゼロ終了コードになる。`sys` は `_app.py` で import 済み。

- [ ] **Step 5: テストが通ることを確認する**

Run: `uv run pytest tests/unit/cli/test_select.py -v`
Expected: PASS（2 件）

- [ ] **Step 6: 静的検査と全テストを確認する**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全てエラーなし、全テスト PASS・収集エラー0。

- [ ] **Step 7: pr モードの手動検証**

`gh` 認証済み環境で、実在の PR に対し `8moku select <PR番号> --manifest <path>` を実行し、`DispatchPlan` JSON が出力され `run_dir` が作成されることを確認する。検証できない環境ではスキップし、その旨を報告に記す。

- [ ] **Step 8: コミット**

```bash
git add src/hachimoku/cli/_select.py src/hachimoku/cli/_app.py tests/unit/cli/test_select.py
git commit -m "feat: add select command emitting dispatch plan"
```

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 のドキュメント整備項目（既存計画と同方針） |
| `docs/ja`・`docs/en` | 否 | 利用者向け CLI ドキュメントは SP1 完了時に一括改訂 |
| `README.md` | 否 | 同上 |
| `CLAUDE.md` | 否 | 影響なし |

## 仕様トレーサビリティ

本計画は設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §5 を上位仕様とする。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する（既存計画と同方針）。

## 完了状態と後続計画

本計画の完了時点:
- `8moku select` が diff / commit / pr / file の4モードで動作し、`DispatchPlan` JSON（run_dir ＋ フェーズ別起動エージェント）を出力する。
- `review/changeset.py`（変更内容計算）と `cli/_select.py`（select コマンド・`DispatchPlan`）が追加される。
- `Manifest` は `--manifest` で受け取る。生成側 `build` は SP2。

**後続計画:**
- SP1-3: `aggregate` 実装 ＋ JSONL 履歴連携。subagent の findings JSON を run_dir から集約。
- SP2: `build`（TOML → サブエージェント `.md` + `manifest.json`）。本計画の `select` が消費する manifest の生成側。
- SP3: Claude Code プラグイン（オーケストレーター skill が `select` を呼び出す）。
