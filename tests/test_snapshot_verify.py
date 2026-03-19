import json
from pathlib import Path

from vibe.cache import sha256_text
from vibe.cli import main


def _sample_spec() -> str:
    return """
intent Snap:
  goal: "snapshot verify"
  inputs:
    x: number
  outputs:
    y: number
emit python
"""


def _normalize_snapshot_paths(payload: dict[str, object], store: Path) -> dict[str, object]:
    normalized = dict(payload)
    store_resolved = str(store.resolve())
    if normalized.get("snapshot_store") == store_resolved:
        normalized["snapshot_store"] = "<SNAPSHOT_STORE>"
    if isinstance(normalized.get("blob_path"), str):
        normalized["blob_path"] = str(normalized["blob_path"]).replace(store_resolved, "<SNAPSHOT_STORE>")
    if isinstance(normalized.get("proof_artifact_path"), str):
        normalized["proof_artifact_path"] = str(normalized["proof_artifact_path"]).replace(store_resolved, "<SNAPSHOT_STORE>")
    if isinstance(normalized.get("error"), str):
        normalized["error"] = str(normalized["error"]).replace(store_resolved, "<SNAPSHOT_STORE>")
    proof = normalized.get("proof")
    if isinstance(proof, dict) and isinstance(proof.get("artifact_path"), str):
        proof = dict(proof)
        proof["artifact_path"] = str(proof["artifact_path"]).replace(store_resolved, "<SNAPSHOT_STORE>")
        normalized["proof"] = proof
    provenance = normalized.get("provenance")
    if isinstance(provenance, dict) and provenance.get("snapshot_store") == store_resolved:
        provenance = dict(provenance)
        provenance["snapshot_store"] = "<SNAPSHOT_STORE>"
        normalized["provenance"] = provenance
    return normalized


def test_verify_by_path_still_works(tmp_path: Path, capsys) -> None:
    case = tmp_path / "path_case.vibe"
    case.write_text(_sample_spec(), encoding="utf-8")
    assert main(["verify", str(case), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["input_mode"] == "path"
    assert payload["spec_path"] == str(case)


def test_verify_by_snapshot_success_with_explicit_store(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    source = _sample_spec()
    sid = sha256_text(source)
    (store / sid).write_text(source, encoding="utf-8")

    assert main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["input_mode"] == "snapshot"
    assert payload["snapshot_id"] == sid
    assert payload["snapshot_store"] == str(store.resolve())
    assert payload["spec_path"] is None


def test_verify_snapshot_missing_hash_reports_machine_readable_error(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    sid = "a" * 64
    rc = main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_type"] == "snapshot_not_found"
    assert payload["input_mode"] == "snapshot"


def test_verify_snapshot_hash_mismatch_detected(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    sid = "b" * 64
    (store / sid).write_text(_sample_spec(), encoding="utf-8")
    rc = main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_type"] == "snapshot_hash_mismatch"


def test_verify_snapshot_invalid_content_reports_parse_error(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    source = "intent Broken:\n goal:"
    sid = sha256_text(source)
    (store / sid).write_text(source, encoding="utf-8")
    rc = main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_type"] == "parse_error"


def test_snapshot_proof_path_and_json_linkage_are_deterministic(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    source = _sample_spec()
    sid = sha256_text(source)
    (store / sid).write_text(source, encoding="utf-8")

    rc = main(
        [
            "verify",
            "--snapshot",
            sid,
            "--snapshot-store",
            str(store),
            "--report",
            "json",
            "--write-proof",
        ]
    )
    assert rc in {0, 1}
    out = capsys.readouterr().out
    payload = json.loads(out.split("proof:")[0])
    expected = store / f"{sid}.vibe.proof.json"
    assert payload["proof_artifact_path"] == str(expected)
    assert expected.exists()
    first = expected.read_text(encoding="utf-8")

    main(
        [
            "verify",
            "--snapshot",
            sid,
            "--snapshot-store",
            str(store),
            "--report",
            "json",
            "--write-proof",
        ]
    )
    second = expected.read_text(encoding="utf-8")
    assert first == second


def test_snapshot_put_cli_success_json(tmp_path: Path, capsys) -> None:
    case = tmp_path / "spec.vibe"
    case.write_text(_sample_spec(), encoding="utf-8")
    store = tmp_path / "store"

    rc = main(["snapshot-put", str(case), "--snapshot-store", str(store), "--report", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "v1"
    assert payload["report_type"] == "snapshot_put"
    assert payload["snapshot_id"] == sha256_text(_sample_spec())
    assert payload["snapshot_store"] == str(store.resolve())
    assert payload["blob_path"] == str((store / payload["snapshot_id"]).resolve())
    assert payload["already_present"] is False


def test_snapshot_put_cli_idempotence_json(tmp_path: Path, capsys) -> None:
    case = tmp_path / "spec.vibe"
    case.write_text(_sample_spec(), encoding="utf-8")
    store = tmp_path / "store"

    assert main(["snapshot-put", str(case), "--snapshot-store", str(store), "--report", "json"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert main(["snapshot-put", str(case), "--snapshot-store", str(store), "--report", "json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["blob_path"] == second["blob_path"]
    assert first["already_present"] is False
    assert second["already_present"] is True


def test_snapshot_put_json_matches_golden_fixture(tmp_path: Path, capsys) -> None:
    case = tmp_path / "spec.vibe"
    case.write_text(_sample_spec(), encoding="utf-8")
    store = tmp_path / "store"
    fixture_path = Path("tests/fixtures/snapshot_contract/snapshot_put_success.json")

    assert main(["snapshot-put", str(case), "--snapshot-store", str(store), "--report", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    normalized = _normalize_snapshot_paths(payload, store)
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert normalized == expected


def test_verify_snapshot_json_success_matches_golden_fixture(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    source = _sample_spec()
    sid = sha256_text(source)
    (store / sid).write_text(source, encoding="utf-8")
    fixture_path = Path("tests/fixtures/snapshot_contract/verify_snapshot_success.json")

    assert main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    contract_view = {
        "schema_version": payload["schema_version"],
        "report_type": payload["report_type"],
        "input_mode": payload["input_mode"],
        "spec_path": payload["spec_path"],
        "snapshot_id": payload["snapshot_id"],
        "snapshot_store": "<SNAPSHOT_STORE>",
        "provenance": {
            "input_mode": payload["provenance"]["input_mode"],
            "spec_path": payload["provenance"]["spec_path"],
            "snapshot_id": payload["provenance"]["snapshot_id"],
            "snapshot_store": "<SNAPSHOT_STORE>",
        },
        "passed": payload["passed"],
        "verdict": payload["verdict"],
    }
    assert contract_view == expected


def test_verify_snapshot_json_missing_matches_golden_fixture(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    sid = "a" * 64
    fixture_path = Path("tests/fixtures/snapshot_contract/verify_snapshot_missing.json")

    rc = main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    normalized = _normalize_snapshot_paths(payload, store)
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert normalized == expected


def test_verify_snapshot_json_hash_mismatch_matches_golden_fixture(tmp_path: Path, capsys) -> None:
    store = tmp_path / "store"
    store.mkdir()
    sid = "b" * 64
    (store / sid).write_text(_sample_spec(), encoding="utf-8")
    fixture_path = Path("tests/fixtures/snapshot_contract/verify_snapshot_hash_mismatch.json")

    rc = main(["verify", "--snapshot", sid, "--snapshot-store", str(store), "--report", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    normalized = _normalize_snapshot_paths(payload, store)
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert normalized == expected
