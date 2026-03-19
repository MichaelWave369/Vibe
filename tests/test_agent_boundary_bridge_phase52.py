import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir, serialize_ir
from vibe.parser import parse_source
from vibe.verifier import verify


def _ir(source: str):
    return ast_to_ir(parse_source(source))


GOOD_SOURCE = """
intent BoundaryGood:
  goal: "Propagate bridge guarantees through agent edges."
  inputs:
    request: PaymentRequest
  outputs:
    decision: ProcessorDecision

constraint:
  deterministic routing

agent Router:
  role: "Route"
  receives: PaymentRequest
  emits: ProcessorDecision
  preserve: deterministic

agent Validator:
  role: "Validate"
  receives: ProcessorDecision
  emits: ProcessorDecision
  preserve: deterministic

orchestrate Pipeline:
  Router -> Validator

emit python
"""


def test_compatible_boundary_passes_without_boundary_issues() -> None:
    ir = _ir(GOOD_SOURCE)
    result = verify(ir, emit_code(ir)[0])
    assert result.agent_boundary_issues == []
    assert result.agent_boundary_summary["pipeline_bridge_score"] == 1.0


def test_boundary_type_mismatch_detected() -> None:
    bad = GOOD_SOURCE.replace("receives: ProcessorDecision", "receives: ComplianceError", 1)
    ir = _ir(bad)
    result = verify(ir, emit_code(ir)[0])
    assert any(i["category"] == "agent_boundary_type_mismatch" for i in result.agent_boundary_issues)
    assert any(o.category == "agent_boundary" for o in result.obligations)


def test_boundary_semantic_mismatch_detected() -> None:
    bad = GOOD_SOURCE.replace("preserve: deterministic", "", 1)
    ir = _ir(bad)
    result = verify(ir, emit_code(ir)[0])
    assert any(i["category"] == "agent_boundary_semantic_loss" for i in result.agent_boundary_issues)


def test_boundary_effect_and_resource_mismatch_detected() -> None:
    source = GOOD_SOURCE + """
agentception {
  enabled: true
  max.depth: 1
  spawn.policy: safe
  inherit.preserve: true
  inherit.constraints: true
  inherit.bridge: true
  merge.strategy: conservative
  stop.when: bridge_stable
}
"""
    source = source.replace('role: "Validate"\n  receives: ProcessorDecision', 'role: "Validate"\n  receives: ProcessorDecision\n  constraint: stateless')
    source = source.replace('agent Validator:\n  role: "Validate"\n  receives: ProcessorDecision\n  constraint: stateless\n  emits: ProcessorDecision\n  preserve: deterministic', 'agent Validator:\n  role: "Validate"\n  receives: ProcessorDecision\n  constraint: stateless\n  emits: ProcessorDecision\n  preserve: deterministic\n  preserve: latency < 50ms')
    source = source.replace("preserve: deterministic", "preserve: deterministic\n  preserve: latency < 50ms", 1)
    ir = _ir(source)
    result = verify(ir, emit_code(ir)[0])
    cats = {i["category"] for i in result.agent_boundary_issues}
    assert "agent_boundary_effect_mismatch" in cats
    assert "agent_boundary_resource_mismatch" in cats


def test_pipeline_bridge_score_deterministic() -> None:
    ir = _ir(GOOD_SOURCE.replace("preserve: deterministic", "", 1))
    one = verify(ir, emit_code(ir)[0]).agent_boundary_summary["pipeline_bridge_score"]
    two = verify(ir, emit_code(ir)[0]).agent_boundary_summary["pipeline_bridge_score"]
    assert one == two


def test_compile_fails_on_critical_boundary_violation(tmp_path) -> None:
    bad = GOOD_SOURCE.replace("receives: ProcessorDecision", "receives: ComplianceError", 1)
    case = tmp_path / "bad_boundary.vibe"
    case.write_text(bad, encoding="utf-8")
    rc = main(["compile", str(case)])
    assert rc == 1


def test_boundary_visibility_in_verify_json(capsys, tmp_path) -> None:
    case = tmp_path / "good_boundary.vibe"
    case.write_text(GOOD_SOURCE, encoding="utf-8")
    main(["verify", str(case), "--report", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert "agent_boundary_summary" in payload
    assert "agent_boundary_issues" in payload
    assert "agent_boundary_obligations" in payload


def test_boundary_ir_serialization_deterministic() -> None:
    ir = _ir(GOOD_SOURCE)
    first = serialize_ir(ir)
    second = serialize_ir(ir)
    assert first == second
    assert "agent_boundary_summary" in first


def test_explain_show_agent_bridges_flag(capsys, tmp_path) -> None:
    case = tmp_path / "good_boundary.vibe"
    case.write_text(GOOD_SOURCE, encoding="utf-8")
    rc = main(["explain", str(case), "--show-agent-bridges"])
    assert rc == 0
    assert "Agent boundary bridges:" in capsys.readouterr().out


def test_diff_and_emitter_boundary_visibility() -> None:
    old = _ir(GOOD_SOURCE)
    new = _ir(GOOD_SOURCE.replace("Router -> Validator", "Validator -> Router"))
    diff = compute_intent_diff(old, new)
    assert any(change.category == "agent_boundary" for change in diff.changes)

    py_code, _ = emit_code(old)
    assert "AGENT_BOUNDARY_BRIDGES" in py_code
