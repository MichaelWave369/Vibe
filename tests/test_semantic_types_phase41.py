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


def test_semantic_qualifiers_derived_from_constraints_preserve_bridge() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    summary = ir.module.semantic_summary
    bindings = summary["binding_qualifiers"]

    assert "secret_sensitive" in bindings["intent.input.amount"]
    assert "deterministic" in bindings["intent.output.processor"]
    assert "fallback_required" in bindings["intent.output.processor"]
    assert "latency_bounded" in bindings["intent.output.processor"]
    assert "bridge_critical" in bindings["intent.output.processor"]


def test_semantic_qualifier_propagation_to_intent_bindings() -> None:
    ir = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    bindings = ir.module.semantic_summary["binding_qualifiers"]
    for name, qualifiers in bindings.items():
        if name.startswith("intent.input.") or name.startswith("intent.output."):
            assert "intent_derived" in qualifiers


def test_semantic_mismatch_detection_surfaces_issues_and_obligations() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    generated = """
def payment_router(amount, country, card_brand):
    secret = 'abc'
    import random
    x = random.random()
    return x
"""
    result = verify(ir, generated)
    assert result.semantic_type_issues
    assert any(o.category == "semantic_type" for o in result.obligations)


def test_semantic_type_visibility_in_verify_report_json(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--report", "json"])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert "semantic_type_summary" in payload
    assert "semantic_type_issues" in payload
    assert "semantic_type_obligations" in payload


def test_semantic_ir_serialization_is_deterministic() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    first = serialize_ir(ir)
    second = serialize_ir(ir)
    assert first == second
    assert "semantic_summary" in first


def test_diff_includes_semantic_type_change_visibility() -> None:
    old = _ir_from_file("vibe/examples/payment_router.vibe")
    new = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    result = compute_intent_diff(old, new)
    assert any(change.category == "semantic_types" for change in result.changes)


def test_emitters_include_semantic_qualifier_metadata_markers() -> None:
    py_ir = _ir_from_file("vibe/examples/payment_router.vibe")
    py_code, _ = emit_code(py_ir)
    assert "SEMANTIC_QUALIFIERS" in py_code

    ts_ir = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    ts_code, _ = emit_code(ts_ir)
    assert "SEMANTIC_QUALIFIERS" in ts_code
