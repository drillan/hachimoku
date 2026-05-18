"""aggregate コマンドのテスト。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest, ManifestEntry
from hachimoku.agents.models import ApplicabilityRule, Phase
from hachimoku.cli._app import app


def _write_manifest(path: Path) -> Path:
    manifest = Manifest(
        version=MANIFEST_VERSION,
        entries=(
            ManifestEntry(
                name="code-reviewer",
                applicability=ApplicabilityRule(always=True),
                phase=Phase.MAIN,
                output_schema="scored_issues",
            ),
        ),
    )
    manifest_path = path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json())
    return manifest_path


def _write_dispatch_plan(run_dir: Path, agent_names: list[str]) -> None:
    plan = {
        "run_dir": str(run_dir),
        "phases": {"early": [], "main": agent_names, "final": []},
    }
    (run_dir / "dispatch-plan.json").write_text(json.dumps(plan))


def _findings(issues: list[dict[str, object]], score: float) -> str:
    return json.dumps({"issues": issues, "overall_score": score})


def _issue(severity: str) -> dict[str, object]:
    return {
        "agent_name": "code-reviewer",
        "severity": severity,
        "description": f"a {severity} issue",
        "location": None,
        "suggestion": None,
        "category": None,
    }


class TestAggregateCommand:
    def test_aggregates_findings_and_outputs_report(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        (run_dir / "code-reviewer.json").write_text(
            _findings([_issue("Important")], 7.0)
        )
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        assert result.exit_code == 2  # Important → 2
        assert "Review Report" in result.stdout
        assert "code-reviewer" in result.stdout

    def test_missing_findings_file_becomes_agent_error(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        assert result.exit_code == 0  # issue 0件
        assert "code-reviewer" in result.stdout

    def test_malformed_findings_becomes_agent_error(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        (run_dir / "code-reviewer.json").write_text("{not valid json")
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        assert result.exit_code == 0
        assert "code-reviewer" in result.stdout

    def test_critical_issue_exits_1(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _write_dispatch_plan(run_dir, ["code-reviewer"])
        (run_dir / "code-reviewer.json").write_text(
            _findings([_issue("Critical")], 2.0)
        )
        manifest_path = _write_manifest(tmp_path)

        result = CliRunner().invoke(
            app,
            ["aggregate", "--run-dir", str(run_dir), "--manifest", str(manifest_path)],
        )

        assert result.exit_code == 1

    def test_missing_run_dir_exits_3(self, tmp_path: Path) -> None:
        manifest_path = _write_manifest(tmp_path)
        result = CliRunner().invoke(
            app,
            [
                "aggregate",
                "--run-dir",
                str(tmp_path / "nonexistent"),
                "--manifest",
                str(manifest_path),
            ],
        )
        assert result.exit_code == 3
