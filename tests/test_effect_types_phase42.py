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


def test_effect_derivation_from_constraint_and_bridge() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    summary = ir.module.effect_summary
    assert "fallback_path" in summary["inferred_effects"]
    assert "bridge_critical_effect" in summary["inferred_effects"]
    assert "nondeterministic" in summary["forbidden_effects"]


def test_effect_propagation_to_output_bindings() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    value_effects = ir.module.effect_summary["value_effects"]
    assert "fallback_path" in value_effects["intent.output.processor"]
    assert "bridge_critical_effect" in value_effects["intent.output.processor"]


def test_effect_mismatch_detection_for_purity_and_determinism() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    generated = """
def payment_router(amount, country, card_brand):
    import random
    print('x')
    return random.random()
"""
    result = verify(ir, generated)
    assert result.effect_type_issues
    assert any(o.category == "effect_type" for o in result.obligations)


def test_effect_visibility_in_verify_json_report(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--report", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "effect_type_summary" in payload
    assert "effect_type_issues" in payload
    assert "effect_type_obligations" in payload


def test_effect_ir_serialization_deterministic() -> None:
    ir = _ir_from_file("vibe/examples/payment_router.vibe")
    first = serialize_ir(ir)
    second = serialize_ir(ir)
    assert first == second
    assert "effect_summary" in first


def test_diff_includes_effect_type_change_visibility() -> None:
    old = _ir_from_file("vibe/examples/payment_router.vibe")
    new = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    result = compute_intent_diff(old, new)
    assert any(change.category == "effect_types" for change in result.changes)


def test_emitters_include_effect_profile_metadata() -> None:
    py_ir = _ir_from_file("vibe/examples/payment_router.vibe")
    py_code, _ = emit_code(py_ir)
    assert "EFFECT_PROFILE" in py_code

    ts_ir = _ir_from_file("vibe/examples/edge_contract_ts.vibe")
    ts_code, _ = emit_code(ts_ir)
    assert "EFFECT_PROFILE" in ts_code


def test_explain_show_effects_flag(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["explain", str(case), "--show-effects"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Effect types:" in out
