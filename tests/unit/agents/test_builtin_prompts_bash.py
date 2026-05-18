"""ビルトインレビューエージェントのプロンプトが Bash 化済みであることの検証。"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_BUILTIN_DIR = Path(__file__).parents[3] / "src" / "hachimoku" / "agents" / "_builtin"
_RETIRED = {"selector.toml", "aggregator.toml"}
# 旧 hachimoku 固有ツール名（呼び出し記法）
_LEGACY_TOOL_RE = re.compile(r"\b(run_git|run_gh|read_file|list_directory)\s*\(")

_REVIEWER_TOMLS = sorted(
    p for p in _BUILTIN_DIR.glob("*.toml") if p.name not in _RETIRED
)


@pytest.mark.parametrize("toml_path", _REVIEWER_TOMLS, ids=lambda p: p.name)
def test_system_prompt_has_no_legacy_tool_calls(toml_path: Path) -> None:
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    prompt = data["system_prompt"]
    matches = _LEGACY_TOOL_RE.findall(prompt)
    assert not matches, (
        f"{toml_path.name} still references legacy tool calls: {matches}"
    )


def test_reviewer_toml_count() -> None:
    # 退役2本（selector/aggregator）を除く全レビューエージェントが対象
    assert len(_REVIEWER_TOMLS) == 12
