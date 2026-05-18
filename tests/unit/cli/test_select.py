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
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=path, check=True, capture_output=True
    )


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
        subprocess.run(
            ["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "base"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "feature.py").write_text("y = 2\n")
        subprocess.run(
            ["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "feature"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        manifest_path = _write_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(app, ["select", "--manifest", str(manifest_path)])

        assert result.exit_code == 0
        plan = json.loads(result.stdout)
        assert plan["phases"]["early"] == ["py-agent"]
        assert plan["phases"]["main"] == ["always-agent"]
        assert plan["phases"]["final"] == []
        assert Path(plan["run_dir"]).is_dir()

    def test_missing_manifest_file_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            app, ["select", "--manifest", str(tmp_path / "nonexistent.json")]
        )
        assert result.exit_code == 4

    def test_changeset_failure_exits_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_path = _write_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)  # git リポジトリではない
        result = CliRunner().invoke(app, ["select", "--manifest", str(manifest_path)])
        assert result.exit_code == 3

    def test_commit_with_positional_args_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest_path = _write_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(
            app,
            [
                "select",
                "123",
                "--commit",
                "HEAD~1",
                "--manifest",
                str(manifest_path),
            ],
        )
        assert result.exit_code == 4
