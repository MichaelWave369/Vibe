import json
from pathlib import Path

from vibe.cli import main
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.semver import derive_semver_from_diff, render_semver_json


def _base_source() -> str:
    return """intent S:
  goal: "g"
  inputs:
    x: string
  outputs:
    y: string

preserve:
  quality_score >= 10

constraint:
  deterministic outputs

bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
  mode = strict

emit python
"""


def _decision(old_src: str, new_src: str):
    old_ir = ast_to_ir(parse_source(old_src))
    new_ir = ast_to_ir(parse_source(new_src))
    return derive_semver_from_diff(old_ir, new_ir, old_path="old.vibe", new_path="new.vibe")


def test_added_output_is_minor() -> None:
    new_src = _base_source().replace("  outputs:\n    y: string\n", "  outputs:\n    y: string\n    z: string\n")
    d = _decision(_base_source(), new_src)
    assert d.bump == "minor"


def test_removed_output_is_major() -> None:
    old_src = _base_source().replace("  outputs:\n    y: string\n", "  outputs:\n    y: string\n    z: string\n")
    d = _decision(old_src, _base_source())
    assert d.bump == "major"


def test_added_preserve_is_minor() -> None:
    new_src = _base_source().replace("preserve:\n  quality_score >= 10\n", "preserve:\n  quality_score >= 10\n  latency_budget <= 5\n")
    d = _decision(_base_source(), new_src)
    assert d.bump == "minor"


def test_weakened_preserve_is_major() -> None:
    new_src = _base_source().replace("quality_score >= 10", "quality_score >= 5")
    d = _decision(_base_source(), new_src)
    assert d.bump == "major"


def test_added_constraint_is_minor() -> None:
    new_src = _base_source().replace("constraint:\n  deterministic outputs\n", "constraint:\n  deterministic outputs\n  no pii logs\n")
    d = _decision(_base_source(), new_src)
    assert d.bump == "minor"


def test_removed_constraint_is_major() -> None:
    new_src = _base_source().replace("constraint:\n  deterministic outputs\n", "constraint:\n")
    d = _decision(_base_source(), new_src)
    assert d.bump == "major"


def test_bridge_weakening_is_major_and_strengthening_is_minor() -> None:
    weak = _base_source().replace("measurement_safe_ratio = 0.85", "measurement_safe_ratio = 0.7")
    strong = _base_source().replace("measurement_safe_ratio = 0.85", "measurement_safe_ratio = 0.9")
    assert _decision(_base_source(), weak).bump == "major"
    assert _decision(_base_source(), strong).bump == "minor"


def test_semver_json_is_deterministic() -> None:
    d = _decision(_base_source(), _base_source().replace("goal: \"g\"", "goal: \"g2\""))
    j1 = render_semver_json(d)
    j2 = render_semver_json(d)
    assert j1 == j2


def test_cli_semver_json_output(capsys, tmp_path: Path) -> None:
    old_path = tmp_path / "old.vibe"
    new_path = tmp_path / "new.vibe"
    old_path.write_text(_base_source(), encoding="utf-8")
    new_path.write_text(_base_source().replace("quality_score >= 10", "quality_score >= 12"), encoding="utf-8")
    rc = main(["semver", str(old_path), str(new_path), "--report", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["bump"] == "minor"


def test_manifest_preview_and_apply(tmp_path: Path, capsys) -> None:
    old_path = tmp_path / "old.vibe"
    new_path = tmp_path / "new.vibe"
    manifest = tmp_path / "vibe.toml"
    old_path.write_text(_base_source(), encoding="utf-8")
    new_path.write_text(_base_source().replace("constraint:\n  deterministic outputs\n", "constraint:\n"), encoding="utf-8")
    manifest.write_text(
        """[package]
name = "pkg"
version = "1.2.3"
description = "d"
""",
        encoding="utf-8",
    )

    rc = main(
        [
            "semver",
            str(old_path),
            str(new_path),
            "--manifest-path",
            str(manifest),
            "--report",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["recommended_next_version"] == "2.0.0"

    rc = main(
        [
            "semver",
            str(old_path),
            str(new_path),
            "--apply-manifest",
            str(manifest),
            "--report",
            "human",
        ]
    )
    assert rc == 0
    text = manifest.read_text(encoding="utf-8")
    assert 'version = "2.0.0"' in text
