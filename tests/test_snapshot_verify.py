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
