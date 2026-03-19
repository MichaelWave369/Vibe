from pathlib import Path

from vibe.cli import main
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.verifier import verify


def _load_ir_and_code(src_text: str):
    ir = ast_to_ir(parse_source(src_text))
    code, _ = emit_code(ir)
    return ir, code


def test_smt_solves_founding_law_obligations() -> None:
    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir, code = _load_ir_and_code(src)
    result = verify(ir, code, backend="smt")
    bridge = {o.obligation_id: o for o in result.obligations if o.category == "bridge"}
    assert bridge["bridge.founding.epsilon_post_gt_floor"].status == "satisfied"
    assert bridge["bridge.founding.measurement_ratio_safe"].status == "satisfied"
    assert result.verification_backend == "smt"


def test_smt_solves_simple_numeric_preserve_rules() -> None:
    src = """
intent NumericPreserve:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
preserve:
  latency < 200ms
  count >= 1
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
emit python
"""
    ir, code = _load_ir_and_code(src)
    result = verify(ir, code, backend="smt")
    preserve = {o.obligation_id: o for o in result.obligations if o.category == "preserve"}
    assert preserve["preserve.1"].status in {"satisfied", "violated", "unknown"}
    assert "solver-evaluated" in (preserve["preserve.1"].evidence or "")
    assert preserve["preserve.2"].status == "satisfied"


def test_smt_solves_simple_equality_and_boolean_constraints() -> None:
    src = """
intent BooleanConstraint:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
preserve:
  compliance = strict
constraint:
  compliance = strict
  preserve.epsilon: true
emit python
"""
    ir, code = _load_ir_and_code(src)
    result = verify(ir, code, backend="smt")
    constraint_statuses = [o.status for o in result.obligations if o.category == "constraint"]
    assert "satisfied" in constraint_statuses


def test_smt_unsupported_obligations_are_deferred_unknown() -> None:
    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir, code = _load_ir_and_code(src)
    result = verify(ir, code, backend="smt")
    assert any(
        o.status == "unknown" and (o.evidence or "").startswith("deferred:")
        for o in result.obligations
    )


def test_smt_compile_fails_on_violated_bridge_obligation(tmp_path) -> None:
    src = """
intent HardFail:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.9
  measurement_safe_ratio = 1.2
emit python
"""
    case = tmp_path / "hard_fail.vibe"
    case.write_text(src, encoding="utf-8")
    rc = main(["compile", str(case), "--backend", "smt"])
    assert rc == 1


def test_smt_with_heuristic_fallback_marks_fallback_usage() -> None:
    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir, code = _load_ir_and_code(src)
    result = verify(ir, code, backend="smt", fallback_backend="heuristic")
    assert result.verification_backend == "smt"
    assert "fallback_used" in result.backend_details
