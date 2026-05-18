"""build コマンドのテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hachimoku.agents.manifest import Manifest
from hachimoku.cli._app import app


class TestBuildCommand:
    def test_builds_subagent_md_and_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        output = tmp_path / "build"

        result = CliRunner().invoke(app, ["build", "--output", str(output)])

        assert result.exit_code == 0
        manifest_path = output / "manifest.json"
        assert manifest_path.is_file()
        manifest = Manifest.model_validate_json(manifest_path.read_text())
        assert len(manifest.entries) == 12  # ビルトインレビュー12本
        agents_dir = output / "agents"
        for entry in manifest.entries:
            md_path = agents_dir / f"{entry.name}.md"
            assert md_path.is_file()
            text = md_path.read_text()
            assert text.startswith("---\n")
            assert "## Output Contract" in text

    def test_code_reviewer_md_has_expected_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        output = tmp_path / "build"
        CliRunner().invoke(app, ["build", "--output", str(output)])

        md = (output / "agents" / "code-reviewer.md").read_text()
        assert "name: code-reviewer\n" in md
        assert "model: claude-opus-4-7\n" in md
        assert "block-git-mutations.sh" in md
