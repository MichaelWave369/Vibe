import json
from pathlib import Path

from vibe.calibration import (
    fit_calibration_model,
    load_calibration_corpus,
    load_calibration_model,
    save_calibration_model,
)
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.verifier import verify


def test_calibration_corpus_loading_seed() -> None:
    records = load_calibration_corpus("vibe/calibration_corpus/seed_corpus.json")
    assert records
    assert records[0].expected_epsilon_pre > 0


def test_calibration_artifact_deterministic_generation(tmp_path) -> None:
    records = load_calibration_corpus("vibe/calibration_corpus/seed_corpus.json")
    model = fit_calibration_model(records)
    out = tmp_path / "bridge_calibration.json"
    save_calibration_model(model, out)
    first = out.read_text(encoding="utf-8")
    save_calibration_model(model, out)
    second = out.read_text(encoding="utf-8")
    assert first == second
    payload = json.loads(first)
    assert payload["model_version"] == "v1"


def test_verify_without_calibration_metadata() -> None:
    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    code, _ = emit_code(ir)
    result = verify(ir, code, use_calibration=False)
    assert result.calibration_applied is False


def test_verify_with_calibration_metadata(tmp_path) -> None:
    records = load_calibration_corpus("vibe/calibration_corpus/seed_corpus.json")
    model = fit_calibration_model(records)
    artifact = tmp_path / "bridge_calibration.json"
    save_calibration_model(model, artifact)

    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    code, _ = emit_code(ir)
    result = verify(ir, code, use_calibration=True, calibration_path=str(artifact))
    assert result.calibration_applied is True
    assert result.calibration_model_version == "v1"


def test_corrupt_calibration_artifact_falls_back(tmp_path) -> None:
    artifact = tmp_path / "bridge_calibration.json"
    artifact.write_text("not-json", encoding="utf-8")
    assert load_calibration_model(artifact) is None

    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    code, _ = emit_code(ir)
    result = verify(ir, code, use_calibration=True, calibration_path=str(artifact))
    assert result.calibration_applied is False
    assert "missing or invalid" in result.calibration_notes


def test_calibration_never_bypasses_critical_failures(tmp_path) -> None:
    records = load_calibration_corpus("vibe/calibration_corpus/seed_corpus.json")
    model = fit_calibration_model(records)
    artifact = tmp_path / "bridge_calibration.json"
    save_calibration_model(model, artifact)

    src = """
intent HardFail:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.95
  measurement_safe_ratio = 1.3
emit python
"""
    ir = ast_to_ir(parse_source(src))
    code, _ = emit_code(ir)
    result = verify(ir, code, use_calibration=True, calibration_path=str(artifact))
    assert result.passed is False
