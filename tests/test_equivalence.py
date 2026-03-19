from pathlib import Path

from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.report import render_report_json
from vibe.verifier import verify


def _result_from_example(path: str):
    src = Path(path).read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    code, _ = emit_code(ir)
    return ir, code, verify(ir, code)


def test_python_intent_correspondence_surface_present() -> None:
    _, _, result = _result_from_example("vibe/examples/payment_router.vibe")
    assert result.intent_items_total > 0
    assert result.intent_equivalence_score >= 0.0
    assert result.drift_score >= 0.0
    assert any(c.category == "intent" for c in result.correspondence_entries)


def test_typescript_intent_correspondence_surface_present() -> None:
    _, _, result = _result_from_example("vibe/examples/edge_contract_ts.vibe")
    assert result.intent_items_total > 0
    assert any(c.target == "typescript" for c in result.correspondence_entries)


def test_missing_output_detected_in_correspondence() -> None:
    src = """
intent MissingOutput:
  goal: "x"
  inputs:
    a: number
  outputs:
    unknown_output: string
emit python
"""
    ir = ast_to_ir(parse_source(src))
    code = "def missing_output(a: float) -> str:\n    return 'x'\n"
    result = verify(ir, code)
    assert any(c.status == "missing_in_output" for c in result.correspondence_entries if c.source_item.startswith("output:"))


def test_extra_helper_detection_surface() -> None:
    src = Path("vibe/examples/edge_contract_ts.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    code = "export function edgeContractTs(a: number): number { return a; }\nexport const EXTRA_HELPER = true;"
    result = verify(ir, code)
    assert any(c.status == "extra_in_output" for c in result.correspondence_entries)


def test_preserve_rule_comment_representation_partial() -> None:
    _, _, result = _result_from_example("vibe/examples/payment_router.vibe")
    preserve_rows = [c for c in result.correspondence_entries if c.category == "preserve"]
    assert preserve_rows
    assert any(c.status in {"partially_matched", "unknown"} for c in preserve_rows)


def test_deterministic_json_includes_equivalence_fields() -> None:
    _, _, result = _result_from_example("vibe/examples/payment_router.vibe")
    payload = render_report_json(result)
    assert '"intent_equivalence_score"' in payload
    assert '"drift_score"' in payload
    assert '"correspondence_entries"' in payload


def test_experimental_module_correspondence_reported() -> None:
    _, _, result = _result_from_example("vibe/examples/sovereign_bridge.vibe")
    assert any(c.category == "experimental" for c in result.correspondence_entries)
