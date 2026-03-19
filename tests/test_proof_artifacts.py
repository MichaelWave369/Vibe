import json
from pathlib import Path

from vibe.cache import sha256_text
from vibe.cli import main
from vibe.proof import load_proof_artifact


def test_verify_write_proof_pass_case(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--write-proof"])
    assert rc == 0

    proof_path = case.with_suffix(".vibe.proof.json")
    assert proof_path.exists()
    payload = load_proof_artifact(proof_path)
    assert payload["result"]["passed"] is True
    assert payload["verification_backend"] == "heuristic"
    assert "equivalence" in payload


def test_verify_write_proof_fail_case(tmp_path) -> None:
    src = """
intent HardFail:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.95
  measurement_safe_ratio = 1.2
emit python
"""
    case = tmp_path / "hard_fail.vibe"
    case.write_text(src, encoding="utf-8")

    rc = main(["verify", str(case), "--write-proof"])
    assert rc == 1

    proof_path = case.with_suffix(".vibe.proof.json")
    payload = load_proof_artifact(proof_path)
    assert payload["result"]["passed"] is False
    assert payload["result"]["emission_blocked"] is True


def test_verify_proof_command_writes_artifact(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify-proof", str(case)])
    assert rc == 0
    assert case.with_suffix(".vibe.proof.json").exists()


def test_inspect_proof_command(tmp_path, capsys) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    main(["verify-proof", str(case)])

    proof_path = case.with_suffix(".vibe.proof.json")
    rc = main(["inspect-proof", str(proof_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Vibe Proof Summary" in out
    assert "backend:" in out


def test_corrupted_proof_artifact_handled(tmp_path, capsys) -> None:
    proof = tmp_path / "bad.vibe.proof.json"
    proof.write_text("not-json", encoding="utf-8")
    rc = main(["inspect-proof", str(proof)])
    assert rc == 1
    assert "inspect-proof failed" in capsys.readouterr().out


def test_invalid_proof_version_handled(tmp_path, capsys) -> None:
    proof = tmp_path / "bad.vibe.proof.json"
    proof.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "artifact_version": "v0",
                "source_path": "x",
                "source_hash": "x",
                "ir_hash": "x",
                "emit_target": "python",
                "verification_backend": "heuristic",
                "backend_metadata": {},
                "calibration": {},
                "obligation_summary": {},
                "obligations": [],
                "equivalence": {},
                "bridge_metrics": {},
                "epsilon_metrics": {},
                "result": {"passed": False, "emission_blocked": True},
                "candidates": {},
                "intent_guided_tests": {},
                "refinement": {},
                "semantic_types": {},
                "effect_types": {},
                "resource_types": {},
                "inference_types": {},
                "agent_graph": {},
                "agent_boundary_bridges": {},
                "delegation": {},
                "runtime_monitor": {},
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    rc = main(["inspect-proof", str(proof)])
    assert rc == 1
    assert "invalid proof artifact version" in capsys.readouterr().out


def test_proof_json_deterministic(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    main(["verify", str(case), "--write-proof"])
    proof_path = case.with_suffix(".vibe.proof.json")
    first = proof_path.read_text(encoding="utf-8")
    main(["verify", str(case), "--write-proof"])
    second = proof_path.read_text(encoding="utf-8")
    assert first == second


def test_proof_schema_fields_present(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    main(["verify", str(case), "--write-proof"])

    payload = json.loads(case.with_suffix(".vibe.proof.json").read_text(encoding="utf-8"))
    for key in [
        "schema_version",
        "artifact_version",
        "source_path",
        "source_hash",
        "ir_hash",
        "emit_target",
        "verification_backend",
        "backend_metadata",
        "calibration",
        "obligation_summary",
        "obligations",
        "equivalence",
        "bridge_metrics",
        "epsilon_metrics",
        "result",
        "candidates",
        "intent_guided_tests",
        "refinement",
        "semantic_types",
        "effect_types",
        "resource_types",
        "inference_types",
        "agent_graph",
        "agent_boundary_bridges",
        "delegation",
        "runtime_monitor",
        "provenance",
    ]:
        assert key in payload


def test_proof_artifact_includes_path_mode_provenance(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["verify", str(case), "--write-proof"]) == 0

    payload = json.loads(case.with_suffix(".vibe.proof.json").read_text(encoding="utf-8"))
    assert payload["provenance"]["input_mode"] == "path"
    assert payload["provenance"]["spec_path"] == str(case)
    assert payload["provenance"]["snapshot_id"] is None
    assert payload["provenance"]["snapshot_store"] is None


def test_proof_artifact_includes_snapshot_mode_provenance(tmp_path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    source = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    sid = sha256_text(source)
    (store / sid).write_text(source, encoding="utf-8")

    rc = main(
        [
            "verify",
            "--snapshot",
            sid,
            "--snapshot-store",
            str(store),
            "--write-proof",
            "--report",
            "json",
        ]
    )
    assert rc in {0, 1}
    capsys.readouterr()

    proof_path = store / f"{sid}.vibe.proof.json"
    payload = json.loads(proof_path.read_text(encoding="utf-8"))
    assert payload["provenance"]["input_mode"] == "snapshot"
    assert payload["provenance"]["spec_path"] is None
    assert payload["provenance"]["snapshot_id"] == sid
    assert payload["provenance"]["snapshot_store"] == str(store.resolve())
