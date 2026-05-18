"""TOML → サブエージェント変換の純粋関数テスト。"""

from __future__ import annotations

from hachimoku.agents import load_builtin_agents
from hachimoku.agents.manifest import ManifestEntry
from hachimoku.agents.models import AgentDefinition
from hachimoku.agents.subagent import (
    render_subagent_md,
    strip_model_prefix,
    to_manifest_entry,
    tools_frontmatter_value,
)


def _agent(name: str = "code-reviewer") -> AgentDefinition:
    result = load_builtin_agents()
    return next(a for a in result.agents if a.name == name)


class TestStripModelPrefix:
    def test_strips_claudecode_prefix(self) -> None:
        assert strip_model_prefix("claudecode:claude-opus-4-7") == "claude-opus-4-7"

    def test_strips_anthropic_prefix(self) -> None:
        assert strip_model_prefix("anthropic:claude-opus-4-7") == "claude-opus-4-7"

    def test_no_prefix_returned_as_is(self) -> None:
        assert strip_model_prefix("claude-opus-4-7") == "claude-opus-4-7"


class TestToolsFrontmatterValue:
    def test_git_and_file_categories(self) -> None:
        assert tools_frontmatter_value(("git_read", "gh_read", "file_read")) == (
            "Bash, Read, Grep, Glob"
        )

    def test_web_fetch_category(self) -> None:
        assert tools_frontmatter_value(("file_read", "web_fetch")) == (
            "Read, Grep, Glob, WebFetch"
        )

    def test_empty_returns_empty_string(self) -> None:
        assert tools_frontmatter_value(()) == ""


class TestToManifestEntry:
    def test_builds_entry_from_agent(self) -> None:
        agent = _agent("code-reviewer")
        entry = to_manifest_entry(agent)
        assert isinstance(entry, ManifestEntry)
        assert entry.name == agent.name
        assert entry.phase == agent.phase
        assert entry.output_schema == agent.output_schema
        assert entry.applicability == agent.applicability


class TestRenderSubagentMd:
    def test_frontmatter_and_body(self) -> None:
        agent = _agent("code-reviewer")
        md = render_subagent_md(agent)
        assert md.startswith("---\n")
        assert f"name: {agent.name}\n" in md
        assert "model: claude-opus-4-7\n" in md
        assert agent.system_prompt.strip() in md
        assert "## Output Contract" in md
        assert "```json" in md

    def test_bash_agent_has_hook_block(self) -> None:
        agent = _agent("code-reviewer")
        md = render_subagent_md(agent)
        assert "hooks:" in md
        assert "block-git-mutations.sh" in md
        assert "PreToolUse" in md
