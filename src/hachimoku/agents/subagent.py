"""TOML エージェント定義 → Claude Code サブエージェント形式への純粋変換関数。

build（SP2）コマンドが使用する I/O なし・単体テスト可能な変換ロジック。
"""

from __future__ import annotations

import json

from hachimoku.agents.manifest import ManifestEntry
from hachimoku.agents.models import AgentDefinition

# =============================================================================
# モジュール定数
# =============================================================================

_CATEGORY_TO_CC_TOOLS: dict[str, tuple[str, ...]] = {
    "git_read": ("Bash",),
    "gh_read": ("Bash",),
    "file_read": ("Read", "Grep", "Glob"),
    "web_fetch": ("WebFetch",),
}
"""ToolCategory 値から Claude Code ツール名へのマッピング。"""

_CC_TOOL_ORDER: tuple[str, ...] = ("Bash", "Read", "Grep", "Glob", "WebFetch")
"""Claude Code ツールの正規出力順。"""


# =============================================================================
# 純粋変換関数
# =============================================================================


def strip_model_prefix(model: str) -> str:
    """モデル名から既知のプレフィックスを除去して返す。

    Args:
        model: プレフィックス付きまたは素のモデル名。
            例: ``"claudecode:claude-opus-4-7"``, ``"anthropic:claude-opus-4-7"``,
            ``"claude-opus-4-7"``

    Returns:
        プレフィックスを取り除いたモデル名。既知のプレフィックスがなければそのまま返す。
    """
    for prefix in ("claudecode:", "anthropic:"):
        if model.startswith(prefix):
            return model[len(prefix) :]
    return model


def tools_frontmatter_value(allowed_tools: tuple[str, ...]) -> str:
    """ToolCategory タプルから Claude Code フロントマター用 tools 値文字列を生成する。

    各カテゴリを ``_CATEGORY_TO_CC_TOOLS`` で CC ツール群へ変換し、和集合・重複排除のうえ
    ``_CC_TOOL_ORDER`` 順に並べて ``", "`` 連結した文字列を返す。

    Args:
        allowed_tools: ToolCategory 値のタプル。空タプルの場合は空文字列を返す。

    Returns:
        フロントマターに埋め込む tools 値文字列。例: ``"Bash, Read, Grep, Glob"``。
        空入力の場合は ``""``。

    Raises:
        ValueError: 未知のカテゴリが含まれる場合。
    """
    if not allowed_tools:
        return ""

    collected: set[str] = set()
    for category in allowed_tools:
        if category not in _CATEGORY_TO_CC_TOOLS:
            raise ValueError(
                f"Unknown tool category: '{category}'. "
                f"Known categories: {sorted(_CATEGORY_TO_CC_TOOLS)}"
            )
        collected.update(_CATEGORY_TO_CC_TOOLS[category])

    ordered = [tool for tool in _CC_TOOL_ORDER if tool in collected]
    return ", ".join(ordered)


def to_manifest_entry(agent: AgentDefinition) -> ManifestEntry:
    """AgentDefinition から ManifestEntry を構築して返す。

    Args:
        agent: 変換元エージェント定義。

    Returns:
        ディスパッチに必要なメタデータを保持する ManifestEntry。
    """
    return ManifestEntry(
        name=agent.name,
        applicability=agent.applicability,
        phase=agent.phase,
        output_schema=agent.output_schema,
    )


def render_subagent_md(agent: AgentDefinition) -> str:
    """AgentDefinition から Claude Code サブエージェント Markdown 文字列を生成して返す。

    生成する構造:
    1. YAML フロントマター（``---`` で囲む）
       - name / description / model / tools（空の場合は省略）
       - tools に ``Bash`` が含まれる場合は hooks ブロックを追加
    2. system_prompt 本文（strip 済み）
    3. ``## Output Contract`` 節（JSON スキーマ付き）

    Args:
        agent: 変換元エージェント定義。

    Returns:
        サブエージェント ``.md`` ファイルの完全な文字列。
    """
    model_name = strip_model_prefix(agent.model)
    tools_value = tools_frontmatter_value(agent.allowed_tools)
    resolved_tools: tuple[str, ...] = (
        tuple(tools_value.split(", ")) if tools_value else ()
    )
    has_bash = "Bash" in resolved_tools

    # --- YAML フロントマター ---
    frontmatter_lines: list[str] = [
        "---",
        f"name: {agent.name}",
        f"description: {agent.description}",
        f"model: {model_name}",
    ]

    if tools_value:
        frontmatter_lines.append(f"tools: {tools_value}")

    if has_bash:
        frontmatter_lines.extend(
            [
                "hooks:",
                "  PreToolUse:",
                "    - matcher: Bash",
                "      hooks:",
                "        - type: command",
                "          command: ${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh",
            ]
        )

    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines)

    # --- Output Contract 節 ---
    schema = agent.resolved_schema.model_json_schema()
    schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
    output_contract = (
        "## Output Contract\n\n"
        f"When you finish your review, write your findings as a single JSON object\n"
        f"conforming to the schema below to the path `<run_dir>/{agent.name}.json`, where\n"
        f"`<run_dir>` is the run directory provided to you.\n\n"
        f"```json\n"
        f"{schema_json}\n"
        f"```"
    )

    return f"{frontmatter}\n{agent.system_prompt.strip()}\n\n{output_contract}\n"
