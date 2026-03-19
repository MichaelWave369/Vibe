import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir, serialize_ir
from vibe.parser import parse_source
from vibe.verifier import verify


def _ir_from_file(path: str):
    return ast_to_ir(parse_source(Path(path).read_text(encoding="utf-8")))


def test_inference_seeded_from_declared_intent_surfaces() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    summary = ir.module.inference_summary
    inferred = summary["inferred_bindings"]
    assert summary["declared_types"]["intent.output.processor"] == "string"
    assert inferred["intent.output.processor"]["inferred_type"] == "string"
    assert inferred["intent.output.processor"]["deterministic_bias"] is True
    assert inferred["intent.input.amount"]["secret_bias"] is True


def test_inference_unresolved_and_conflicts_surface_obligations() -> None:
    source = """
interface processor_id: number

intent InferenceProbe:
  goal: "probe unresolved and contradictory type surfaces"
  inputs:
    payload: variant
  outputs:
    processor: named

preserve:
  no_hardcoded_secrets <= true

constraint:
  deterministic output ranking

bridge:
  mode = strict

emit python
"""
    ir = ast_to_ir(parse_source(source))
    generated = """
def inference_probe(payload):
    import random
    secret = 'abc'
    return random.random()
"""
    result = verify(ir, generated)
    assert result.inference_type_issues
    assert any(o.category == "inference_type" for o in result.obligations)
    assert any("contradictory" in i["category"] for i in result.inference_type_issues)


def test_inference_visibility_in_verify_json_report(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--report", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "inference_type_summary" in payload
    assert "inference_type_issues" in payload
    assert "inference_type_obligations" in payload


def test_inference_ir_serialization_deterministic() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    first = serialize_ir(ir)
    second = serialize_ir(ir)
    assert first == second
    assert "inference_summary" in first


def test_diff_includes_inference_visibility() -> None:
    old = _ir_from_file("vibe/examples/payment_router.vibe")
    new = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    result = compute_intent_diff(old, new)
    assert any(change.category == "inference_types" for change in result.changes)


def test_emitters_include_inference_profile_metadata() -> None:
    py_ir = _ir_from_file("vibe/examples/payment_router.vibe")
    py_code, _ = emit_code(py_ir)
    assert "INFERENCE_PROFILE" in py_code

    ts_ir = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    ts_code, _ = emit_code(ts_ir)
    assert "INFERENCE_PROFILE" in ts_code


def test_explain_show_inference_flag(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["explain", str(case), "--show-inference"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Inference types:" in out
