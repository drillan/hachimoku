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
