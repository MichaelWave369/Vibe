from pathlib import Path

from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.report import render_report, render_report_json
from vibe.verifier import verify


def _load(path: str) -> tuple[object, object]:
    ast = parse_source(Path(path).read_text(encoding="utf-8"))
    ir = ast_to_ir(ast)
    code, _ = emit_code(ir)
    return ir, verify(ir, code)


def test_obligations_generated_for_core_layers() -> None:
    ir, result = _load("vibe/examples/payment_router.vibe")
    assert result.obligations
    ids = {o.obligation_id for o in result.obligations}
    assert "bridge.founding.epsilon_post_gt_floor" in ids
    assert "bridge.founding.measurement_ratio_safe" in ids
    assert any(o.category == "constraint" for o in result.obligations)
    assert any(o.category == "preserve" for o in result.obligations)


def test_sovereignty_and_delegation_obligations_present() -> None:
    _, result = _load("vibe/examples/sovereign_bridge.vibe")
    ids = {o.obligation_id for o in result.obligations}
    assert "sovereignty.preserve" in ids
    assert "delegation.inherit_bridge" in ids


def test_report_includes_obligation_summary_and_json() -> None:
    _, result = _load("vibe/examples/agentora_agentception.vibe")
    text = render_report(result, show_obligations=True)
    assert "obligations:" in text
    assert "counts:" in text
    payload = render_report_json(result)
    assert '"obligations"' in payload
    assert '"obligation_counts"' in payload


def test_unknown_obligations_are_reported() -> None:
    _, result = _load("vibe/examples/payment_router.vibe")
    assert result.obligation_counts.get("unknown", 0) >= 1


def test_compile_failure_on_violated_key_obligation() -> None:
    src = """
intent LawBreaker:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.8
  measurement_safe_ratio = 1.2
emit python
"""
    ir = ast_to_ir(parse_source(src))
    code, _ = emit_code(ir)
    result = verify(ir, code)
    assert result.passed is False
    assert any(o.status == "violated" for o in result.obligations if o.category == "bridge")
