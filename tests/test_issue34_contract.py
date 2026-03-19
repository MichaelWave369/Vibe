import json
from pathlib import Path

from vibe.cli import main
from vibe.verification_flow import prepare_verification_input


def test_verify_report_json_contract_fields(tmp_path: Path, capsys) -> None:
    case = tmp_path / "c.vibe"
    case.write_text(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["verify", str(case), "--report", "json", "--write-proof"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out.split("proof:")[0])

    assert payload["schema_version"] == "v1"
    assert payload["report_type"] == "verify"
    assert payload["spec_path"] == str(case)
    assert isinstance(payload["bridge_score"], float)
    assert isinstance(payload["measurement_ratio"], float)
    assert isinstance(payload["epsilon_floor"], float)
    assert isinstance(payload["measurement_safe_ratio"], float)
    assert payload["obligations_total"] >= payload["obligations_satisfied"]
    assert payload["proof_artifact_path"].endswith(".vibe.proof.json")
    assert payload["proof_sha256"]
    assert payload["obligations"]
    row = payload["obligations"][0]
    assert {"id", "category", "address", "status", "message", "severity"}.issubset(row.keys())


def test_diff_report_json_contract_fields(tmp_path: Path, capsys) -> None:
    old_case = tmp_path / "old.vibe"
    new_case = tmp_path / "new.vibe"
    old_case.write_text(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"), encoding="utf-8")
    new_case.write_text(Path("vibe/examples/edge_contract_ts.vibe").read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["diff", str(old_case), str(new_case), "--report", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "v1"
    assert payload["report_type"] == "diff"
    assert payload["old_spec"] == str(old_case)
    assert payload["new_spec"] == str(new_case)
    assert "drift_score" in payload
    assert "ops" in payload
    assert payload["ops"]
    op = payload["ops"][0]
    assert {"op", "address", "field", "old_value", "new_value", "semantic_polarity", "bridge_impact", "severity"}.issubset(
        op.keys()
    )


def test_proof_schema_version_present(tmp_path: Path) -> None:
    case = tmp_path / "p.vibe"
    case.write_text(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["verify", str(case), "--write-proof"]) == 0
    payload = json.loads(case.with_suffix(".vibe.proof.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "v1"


def test_prepare_verification_input_supports_memory_source() -> None:
    source = """
intent Inline:
  goal: \"memory seam\"
  inputs:
    x: number
  outputs:
    y: number
emit python
"""
    prepared = prepare_verification_input(source_text=source, source_name="snapshot:abc123")
    assert prepared.spec_path == "snapshot:abc123"
    assert prepared.ir.goal == "memory seam"


def test_snapshot_put_report_json_contract_fields(tmp_path: Path, capsys) -> None:
    case = tmp_path / "s.vibe"
    case.write_text(
        Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    store = tmp_path / "snapshots"

    assert main(["snapshot-put", str(case), "--snapshot-store", str(store), "--report", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "v1"
    assert payload["report_type"] == "snapshot_put"
    assert payload["snapshot_id"]
    assert payload["snapshot_store"] == str(store.resolve())
    assert payload["blob_path"].endswith(payload["snapshot_id"])
    assert payload["already_present"] is False
