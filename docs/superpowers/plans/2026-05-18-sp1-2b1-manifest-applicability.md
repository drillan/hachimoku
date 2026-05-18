# SP1-2b-1: Manifest 契約と applicability 評価器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `select` / `aggregate` が消費する `Manifest` データ契約と、コード変更に対する `ApplicabilityRule` の決定的評価器（LLM 不要）を実装する。

**Architecture:** 設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §5-6 の基盤部分。`Manifest` は `build`（SP2）が TOML から生成し `select`（SP1-2b-2）/ `aggregate`（SP1-3）が消費する純粋データモデル。applicability 評価器は変更ファイル集合と diff 内容から実行対象エージェントをフェーズ別に決定する純関数。いずれも I/O を持たず単体テスト可能。`select` CLI 本体（4モードの diff 計算）は本計画の成果物を利用する後続計画 SP1-2b-2。

**Tech Stack:** Python 3.13+ / pydantic v2 / fnmatch / re / pytest / ruff / mypy / uv

**前提:** SP1-1（旧エンジン撤去）・SP1-2a（モデル再形成）完了済みのブランチ `worktree-sp1-engine-removal` の上で実行する。

---

## 設計決定

本計画で確定する契約（設計書 §5-6 を具体化）:

### Manifest

- 配置: `src/hachimoku/agents/manifest.py`。`Manifest` は「エージェントのディスパッチメタデータ」であり `agents/` パッケージが正しい所属。`models/` に置くと `models → agents`（`ApplicabilityRule`/`Phase` 参照）の循環依存になるため避ける。
- `ManifestEntry`: 1エージェント分のメタデータ。`name` / `applicability`（`ApplicabilityRule`）/ `phase`（`Phase`）/ `output_schema`（スキーマ名文字列）。`AgentDefinition` から `system_prompt` 等を除いた dispatch 用サブセット。
- `Manifest`: `version`（文字列）＋ `entries`（`ManifestEntry` のタプル）。pydantic の JSON シリアライズで `build` が生成・`select` が読み込む。

### applicability 評価器

- 配置: `src/hachimoku/agents/applicability.py`。`ApplicabilityRule` と `Manifest` を入力に取る純関数群。
- 評価セマンティクス（`ApplicabilityRule` の docstring に既定）:
  1. `always=True` → 適用
  2. `file_patterns` のいずれかが変更ファイルの basename に `fnmatch` でマッチ → 適用
  3. `content_patterns` のいずれかが diff 内容に `re.search` でマッチ → 適用
  4. 上記いずれも該当しなければ不適用（条件 2・3 は OR）
- `change_matches(rule, changed_basenames, content) -> bool`: 単一ルールの評価。
- `select_agent_names(manifest, changed_basenames, content) -> dict[Phase, list[str]]`: マニフェスト全体を評価し、適用対象エージェント名をフェーズ別・名前昇順で返す。3フェーズすべてをキーとして持つ（該当なしは空リスト）。

## File Structure

**新規作成:**
- `src/hachimoku/agents/manifest.py` — `ManifestEntry`・`Manifest` モデル、`MANIFEST_VERSION` 定数
- `src/hachimoku/agents/applicability.py` — `change_matches`・`select_agent_names`
- `tests/unit/agents/test_manifest.py`
- `tests/unit/agents/test_applicability.py`

**変更:** なし（既存モジュールへの影響なし。`select` CLI への組み込みは SP1-2b-2）。

> `tests/unit/agents/` ディレクトリは既存（`agents/` の他テストが配置済み）。`__init__.py` も存在する前提。存在しなければ空ファイルで作成する。

---

## Task 1: Manifest データモデル

**Files:**
- Create: `src/hachimoku/agents/manifest.py`
- Test: `tests/unit/agents/test_manifest.py`

> 全コマンドは worktree（`worktree-sp1-engine-removal`）で `uv run` を用いて実行する。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/agents/test_manifest.py` を作成:

```python
"""Manifest / ManifestEntry モデルのテスト。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest, ManifestEntry
from hachimoku.agents.models import ApplicabilityRule, Phase


def _entry(name: str = "code-reviewer") -> ManifestEntry:
    return ManifestEntry(
        name=name,
        applicability=ApplicabilityRule(always=True),
        phase=Phase.MAIN,
        output_schema="scored_issues",
    )


class TestManifestEntry:
    def test_construct(self) -> None:
        entry = _entry()
        assert entry.name == "code-reviewer"
        assert entry.phase is Phase.MAIN
        assert entry.output_schema == "scored_issues"
        assert entry.applicability.always is True

    def test_name_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            ManifestEntry(
                name="",
                applicability=ApplicabilityRule(always=True),
                phase=Phase.MAIN,
                output_schema="scored_issues",
            )

    def test_output_schema_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            ManifestEntry(
                name="a",
                applicability=ApplicabilityRule(always=True),
                phase=Phase.MAIN,
                output_schema="",
            )


class TestManifest:
    def test_construct(self) -> None:
        manifest = Manifest(version=MANIFEST_VERSION, entries=(_entry(),))
        assert manifest.version == MANIFEST_VERSION
        assert len(manifest.entries) == 1

    def test_json_round_trip(self) -> None:
        original = Manifest(
            version=MANIFEST_VERSION,
            entries=(
                _entry("code-reviewer"),
                ManifestEntry(
                    name="security-analyzer",
                    applicability=ApplicabilityRule(
                        file_patterns=("*.py",), content_patterns=(r"password",)
                    ),
                    phase=Phase.EARLY,
                    output_schema="severity_classified",
                ),
            ),
        )
        restored = Manifest.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_empty_entries_allowed(self) -> None:
        manifest = Manifest(version=MANIFEST_VERSION, entries=())
        assert manifest.entries == ()
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/agents/test_manifest.py -v`
Expected: FAIL（`ModuleNotFoundError: hachimoku.agents.manifest`）

- [ ] **Step 3: `manifest.py` を実装する**

`src/hachimoku/agents/manifest.py` を作成:

```python
"""Manifest — レビューエージェントのディスパッチメタデータ契約。

build（SP2）が TOML 定義から生成し、select（SP1-2b-2）/ aggregate（SP1-3）が
消費する純粋データモデル。AgentDefinition から system_prompt 等を除いた、
ディスパッチ判定に必要なサブセットを保持する。
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from hachimoku.agents.models import ApplicabilityRule, Phase
from hachimoku.models._base import HachimokuBaseModel

MANIFEST_VERSION: Final[str] = "1"
"""Manifest スキーマのバージョン。互換性のない変更時に繰り上げる。"""


class ManifestEntry(HachimokuBaseModel):
    """1エージェント分のディスパッチメタデータ。

    Attributes:
        name: エージェント名（一意識別子）。
        applicability: 適用ルール。
        phase: 実行フェーズ。
        output_schema: 出力スキーマ名（SCHEMA_REGISTRY のキー）。
    """

    name: str = Field(min_length=1)
    applicability: ApplicabilityRule
    phase: Phase
    output_schema: str = Field(min_length=1)


class Manifest(HachimokuBaseModel):
    """全レビューエージェントのディスパッチメタデータ。

    Attributes:
        version: Manifest スキーマのバージョン。
        entries: エージェントごとのエントリ。
    """

    version: str = Field(min_length=1)
    entries: tuple[ManifestEntry, ...]
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/agents/test_manifest.py -v`
Expected: PASS（7 件）

- [ ] **Step 5: 静的検査とコミット**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy .`
Expected: エラーなし。その後:

```bash
git add src/hachimoku/agents/manifest.py tests/unit/agents/test_manifest.py
git commit -m "feat: add Manifest dispatch-metadata contract"
```

---

## Task 2: applicability 評価器

**Files:**
- Create: `src/hachimoku/agents/applicability.py`
- Test: `tests/unit/agents/test_applicability.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/agents/test_applicability.py` を作成:

```python
"""applicability 評価器のテスト。"""

from __future__ import annotations

from hachimoku.agents.applicability import change_matches, select_agent_names
from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest, ManifestEntry
from hachimoku.agents.models import ApplicabilityRule, Phase


class TestChangeMatches:
    def test_always_true_matches_regardless(self) -> None:
        rule = ApplicabilityRule(always=True)
        assert change_matches(rule, frozenset(), "") is True

    def test_file_pattern_matches_basename(self) -> None:
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert change_matches(rule, frozenset({"main.py"}), "") is True

    def test_file_pattern_no_match(self) -> None:
        rule = ApplicabilityRule(file_patterns=("*.rs",))
        assert change_matches(rule, frozenset({"main.py"}), "") is False

    def test_content_pattern_matches(self) -> None:
        rule = ApplicabilityRule(content_patterns=(r"TODO",))
        assert change_matches(rule, frozenset(), "x = 1  # TODO") is True

    def test_content_pattern_no_match(self) -> None:
        rule = ApplicabilityRule(content_patterns=(r"FIXME",))
        assert change_matches(rule, frozenset(), "x = 1  # TODO") is False

    def test_file_or_content_is_or(self) -> None:
        # file_patterns 不一致でも content_patterns 一致なら適用
        rule = ApplicabilityRule(
            file_patterns=("*.rs",), content_patterns=(r"password",)
        )
        assert change_matches(rule, frozenset({"main.py"}), "password = 1") is True

    def test_no_conditions_matches_nothing(self) -> None:
        rule = ApplicabilityRule()
        assert change_matches(rule, frozenset({"main.py"}), "anything") is False


class TestSelectAgentNames:
    def test_groups_by_phase_sorted(self) -> None:
        manifest = Manifest(
            version=MANIFEST_VERSION,
            entries=(
                ManifestEntry(
                    name="zzz-early",
                    applicability=ApplicabilityRule(always=True),
                    phase=Phase.EARLY,
                    output_schema="scored_issues",
                ),
                ManifestEntry(
                    name="aaa-early",
                    applicability=ApplicabilityRule(always=True),
                    phase=Phase.EARLY,
                    output_schema="scored_issues",
                ),
                ManifestEntry(
                    name="py-only",
                    applicability=ApplicabilityRule(file_patterns=("*.py",)),
                    phase=Phase.MAIN,
                    output_schema="scored_issues",
                ),
            ),
        )
        result = select_agent_names(
            manifest, frozenset({"main.py"}), "diff content"
        )
        assert result == {
            Phase.EARLY: ["aaa-early", "zzz-early"],
            Phase.MAIN: ["py-only"],
            Phase.FINAL: [],
        }

    def test_excludes_non_matching(self) -> None:
        manifest = Manifest(
            version=MANIFEST_VERSION,
            entries=(
                ManifestEntry(
                    name="rust-only",
                    applicability=ApplicabilityRule(file_patterns=("*.rs",)),
                    phase=Phase.MAIN,
                    output_schema="scored_issues",
                ),
            ),
        )
        result = select_agent_names(manifest, frozenset({"main.py"}), "")
        assert result == {Phase.EARLY: [], Phase.MAIN: [], Phase.FINAL: []}

    def test_empty_manifest(self) -> None:
        manifest = Manifest(version=MANIFEST_VERSION, entries=())
        result = select_agent_names(manifest, frozenset({"main.py"}), "")
        assert result == {Phase.EARLY: [], Phase.MAIN: [], Phase.FINAL: []}
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/agents/test_applicability.py -v`
Expected: FAIL（`ModuleNotFoundError: hachimoku.agents.applicability`）

- [ ] **Step 3: `applicability.py` を実装する**

`src/hachimoku/agents/applicability.py` を作成:

```python
"""applicability 評価器 — コード変更に対する ApplicabilityRule の決定的評価。

select（SP1-2b-2）が、変更ファイル集合と diff 内容から実行対象エージェントを
フェーズ別に決定するために使用する。LLM を用いない純関数群。
"""

from __future__ import annotations

import re
from fnmatch import fnmatch

from hachimoku.agents.manifest import Manifest
from hachimoku.agents.models import ApplicabilityRule, Phase


def change_matches(
    rule: ApplicabilityRule,
    changed_basenames: frozenset[str],
    content: str,
) -> bool:
    """単一の ApplicabilityRule をコード変更に対して評価する。

    評価セマンティクス（ApplicabilityRule の定義に準拠）:
        1. always=True なら常に適用。
        2. file_patterns のいずれかが changed_basenames の要素に
           fnmatch でマッチすれば適用。
        3. content_patterns のいずれかが content に re.search でマッチすれば適用。
        4. いずれも該当しなければ不適用。条件 2・3 は OR。

    Args:
        rule: 評価対象の適用ルール。
        changed_basenames: 変更ファイルの basename 集合。
        content: 変更内容（diff テキスト）。

    Returns:
        適用すべきなら True。
    """
    if rule.always:
        return True
    for pattern in rule.file_patterns:
        if any(fnmatch(basename, pattern) for basename in changed_basenames):
            return True
    for pattern in rule.content_patterns:
        if re.search(pattern, content):
            return True
    return False


def select_agent_names(
    manifest: Manifest,
    changed_basenames: frozenset[str],
    content: str,
) -> dict[Phase, list[str]]:
    """Manifest 全体を評価し、適用対象エージェント名をフェーズ別に返す。

    Args:
        manifest: 評価対象の Manifest。
        changed_basenames: 変更ファイルの basename 集合。
        content: 変更内容（diff テキスト）。

    Returns:
        フェーズをキー、適用対象エージェント名の昇順リストを値とする辞書。
        全 3 フェーズ（EARLY / MAIN / FINAL）を必ずキーに含む（該当なしは空リスト）。
    """
    result: dict[Phase, list[str]] = {phase: [] for phase in Phase}
    for entry in manifest.entries:
        if change_matches(entry.applicability, changed_basenames, content):
            result[entry.phase].append(entry.name)
    for phase in result:
        result[phase].sort()
    return result
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/agents/test_applicability.py -v`
Expected: PASS（10 件）

- [ ] **Step 5: 静的検査とコミット**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest`
Expected: 全てエラーなし、全テスト PASS。その後:

```bash
git add src/hachimoku/agents/applicability.py tests/unit/agents/test_applicability.py
git commit -m "feat: add deterministic applicability evaluator"
```

---

## Documentation Impact

| 対象 | 更新要否 | 内容 |
|------|---------|------|
| `specs/008+/spec.md` | 否（後続） | SpecKit spec 形式化は設計書 §15 のドキュメント整備項目（既存計画と同方針） |
| `docs/ja`・`docs/en` | 否 | 利用者向けドキュメントは SP1 完了時に一括改訂。内部モジュール追加のみで本計画では更新しない |
| `README.md` | 否 | 影響なし |
| `CLAUDE.md` | 否 | 影響なし |

## 仕様トレーサビリティ

本計画は設計書 `docs/superpowers/specs/2026-05-18-skill-migration-design.md` §5-6 を上位仕様とする。SpecKit 形式の `specs/NNN-xxx/spec.md` は設計書 §15 の整備項目として別途作成する（既存計画と同方針）。

## 完了状態と後続計画

本計画の完了時点:
- `agents/manifest.py`: `Manifest` / `ManifestEntry` データ契約が確定。JSON シリアライズ可能。
- `agents/applicability.py`: `change_matches` / `select_agent_names` の決定的評価器。
- いずれも純粋（I/O なし）・単体テスト済み。`select` / `aggregate` / `build` から再利用可能。

**後続計画:**
- SP1-2b-2: `hachimoku select` コマンド実装。`--target` の 4 モード（diff / commit / pr / file）の diff 計算、変更ファイル集合・内容の取得、`select_agent_names` 呼び出し、run_dir 作成、ディスパッチプラン JSON 出力。`cli/_input_resolver.py` / `cli/_file_resolver.py`（再利用予定）の調査を要する。
- SP1-3: `aggregate` 実装 ＋ JSONL 履歴連携。
- SP2: `build`（TOML → サブエージェント `.md` + `manifest.json`）。本計画の `Manifest` を生成側として利用。
