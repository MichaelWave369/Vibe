import json
from pathlib import Path

from vibe.cli import main


def test_interchange_from_text_is_deterministic(tmp_path: Path, capsys) -> None:
    req = tmp_path / "req.txt"
    req.write_text(
        "Route payment requests to a compliant gateway with deterministic fallback and explicit unknown handling.\n",
        encoding="utf-8",
    )

    out1 = tmp_path / "interchange1.json"
    out2 = tmp_path / "interchange2.json"

    assert main(["interchange-from-text", str(req), "--report", "json", "--write-output", str(out1)]) == 0
    payload1 = json.loads(capsys.readouterr().out)
    assert payload1["artifact_version"] == "phase-8.4.interchange.v1"
    assert payload1["generated_intent"]["mode"] == "deterministic_scaffold"

    assert main(["interchange-from-text", str(req), "--report", "json", "--write-output", str(out2)]) == 0
    payload2 = json.loads(capsys.readouterr().out)
    assert payload1 == payload2
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


def test_intent_brief_and_proof_brief_surfaces(tmp_path: Path, capsys) -> None:
    source = Path("stdlib/vibe_http/src/main.vibe")
    proof_path = source.with_suffix(".vibe.proof.json")

    assert main(["intent-brief", str(source), "--report", "json"]) == 0
    intent_payload = json.loads(capsys.readouterr().out)
    assert intent_payload["brief_version"] == "phase-8.4.intent-brief.v1"
    assert intent_payload["intent"]["name"] == "HttpRequestResponseContract"

    assert main(["verify-proof", str(source), "--report", "json"]) == 0
    _ = capsys.readouterr().out

    out_brief = tmp_path / "proof_brief.json"
    assert main(["proof-brief", str(proof_path), "--report", "json", "--write-output", str(out_brief)]) == 0
    proof_payload = json.loads(capsys.readouterr().out)

    assert proof_payload["brief_version"] == "phase-8.4.proof-brief.v1"
    assert "intent_summary" in proof_payload
    assert "preserve_constraint_summary" in proof_payload
    assert "bridge_result" in proof_payload
    assert "equivalence_drift_summary" in proof_payload
    assert proof_payload["interchange_metadata"]["deterministic_projection"] is True
    assert out_brief.exists()


def test_interchange_cli_human_modes(tmp_path: Path, capsys) -> None:
    req = tmp_path / "req.txt"
    req.write_text("Summarize support tickets into deterministic escalation actions.", encoding="utf-8")

    assert main(["interchange-from-text", str(req)]) == 0
    out = capsys.readouterr().out
    assert "Vibe Interchange Artifact" in out

    assert main(["intent-brief", "stdlib/vibe_agent/src/main.vibe"]) == 0
    out2 = capsys.readouterr().out
    assert "Vibe Intent Brief" in out2
