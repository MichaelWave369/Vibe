import json
from pathlib import Path

from vibe.cli import main
from vibe.ir import ast_to_ir
from vibe.negotiation import negotiate_intents, render_negotiation_json
from vibe.parser import parse_source


def _src(
    *,
    preserve: str = "latency < 200",
    constraint: str = "deterministic",
    output_type: str = "string",
    msr: str = "0.85",
) -> str:
    return f"""intent N:
  goal: "g"
  inputs:
    x: string
  outputs:
    y: {output_type}

preserve:
  {preserve}

constraint:
  {constraint}

bridge:
  measurement_safe_ratio = {msr}
  epsilon_floor = 0.02
  mode = strict

emit python
"""


def _contract(*sources: str):
    irs = [ast_to_ir(parse_source(s)) for s in sources]
    paths = [f"p{i}.vibe" for i in range(len(sources))]
    return negotiate_intents(irs, paths)


def test_compatible_merge() -> None:
    c = _contract(_src(), _src())
    assert c.success is True
    assert not c.conflicts


def test_stronger_preserve_wins() -> None:
    c = _contract(_src(preserve="latency < 200"), _src(preserve="latency < 100"))
    assert c.success is True
    assert ("latency", "<", "100") in c.preserve_rules


def test_stronger_bridge_threshold_wins() -> None:
    c = _contract(_src(msr="0.85"), _src(msr="0.90"))
    assert c.success is True
    assert c.bridge_config["measurement_safe_ratio"] == "0.9"


def test_direct_constraint_conflict() -> None:
    c = _contract(_src(constraint="no pii in logs"), _src(constraint="raw debug logs required"))
    assert c.success is False
    assert c.conflicts


def test_interface_output_conflict() -> None:
    c = _contract(_src(output_type="string"), _src(output_type="number"))
    assert c.success is False
    assert any(x.category == "output" for x in c.conflicts)


def test_negotiation_json_deterministic() -> None:
    c = _contract(_src(), _src())
    assert render_negotiation_json(c) == render_negotiation_json(c)


def test_cli_negotiate_json_and_write_artifacts(tmp_path: Path, capsys) -> None:
    a = tmp_path / "a.vibe"
    b = tmp_path / "b.vibe"
    out_vibe = tmp_path / "negotiated.vibe"
    artifact = tmp_path / "negotiated.json"
    a.write_text(_src(), encoding="utf-8")
    b.write_text(_src(preserve="latency < 100", msr="0.9"), encoding="utf-8")

    rc = main(
        [
            "negotiate",
            str(a),
            str(b),
            "--report",
            "json",
            "--write-negotiated",
            str(out_vibe),
            "--write-artifact",
            str(artifact),
            "--fail-on-conflict",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert out_vibe.exists()
    assert artifact.exists()


def test_cli_negotiate_conflict_blocks_when_requested(tmp_path: Path, capsys) -> None:
    a = tmp_path / "a.vibe"
    b = tmp_path / "b.vibe"
    a.write_text(_src(constraint="no pii in logs"), encoding="utf-8")
    b.write_text(_src(constraint="raw debug logs required"), encoding="utf-8")
    rc = main(["negotiate", str(a), str(b), "--fail-on-conflict", "--show-conflicts"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "success: False" in out
