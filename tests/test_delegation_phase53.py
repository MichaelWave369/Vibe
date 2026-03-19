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


BASE = """
intent DelegationFlow:
  goal: "Plan and synthesize through delegated agents."
  inputs:
    task: TaskInput
  outputs:
    plan: TaskPlan

bridge:
  measurement_safe_ratio = 0.85
  mode = strict

agent Planner:
  role: "Break task into validated substeps"
  receives: TaskInput
  emits: TaskPlan
  preserve: deterministic
  preserve: sovereignty = true
  constraint: stateless

agent Researcher:
  role: "Gather evidence"
  receives: TaskPlan
  emits: TaskPlan
  preserve: deterministic

agent Synthesizer:
  role: "Produce final synthesis"
  receives: TaskPlan
  emits: TaskPlan
  preserve: deterministic

delegate Planner -> Researcher:
  inherits: [preserve, constraint, bridge]
  max_depth: 3
  stop_when: epsilon.gradient < threshold

delegate Researcher -> Synthesizer:
  inherits: [preserve, bridge]

emit python
"""


def test_parse_delegate_syntax() -> None:
    p = parse_source(BASE)
    assert len(p.delegations) == 2
    assert p.delegations[0].parent == "Planner"
    assert p.delegations[0].child == "Researcher"


def test_inherited_contracts_visible() -> None:
    ir = _ir(BASE)
    summary = ir.module.delegation_summary
    assert summary["delegation_tree"]
    first = summary["inherited_contract_summary"][0]
    assert "deterministic" in " ".join(first["inherited_preserve"]).lower()
    assert first["inherited_bridge"]["measurement_safe_ratio"] == "0.85"


def test_child_threshold_weakening_detected_and_blocks_compile(tmp_path) -> None:
    bad = BASE.replace("agent Researcher:\n  role: \"Gather evidence\"\n  receives: TaskPlan\n  emits: TaskPlan\n  preserve: deterministic", "agent Researcher:\n  role: \"Gather evidence\"\n  receives: TaskPlan\n  emits: TaskPlan\n  preserve: deterministic\n  preserve: measurement_safe_ratio = 0.70")
    ir = _ir(bad)
    result = verify(ir, emit_code(ir)[0])
    assert any(i["category"] == "contract_weakening" for i in result.delegation_issues)

    case = tmp_path / "delegation_bad.vibe"
    case.write_text(bad, encoding="utf-8")
    rc = main(["compile", str(case)])
    assert rc == 1


def test_sovereignty_inheritance_loss_detected() -> None:
    bad = BASE.replace("inherits: [preserve, constraint, bridge]", "inherits: [constraint, bridge]")
    ir = _ir(bad)
    result = verify(ir, emit_code(ir)[0])
    assert any(i["issue_id"].startswith("delegation.sovereignty_loss") for i in result.delegation_issues)


def test_recursion_without_stop_and_cycle_risk_detected() -> None:
    cyc = BASE.replace("  stop_when: epsilon.gradient < threshold\n", "") + """
delegate Synthesizer -> Planner:
  inherits: [preserve, bridge]
"""
    ir = _ir(cyc)
    result = verify(ir, emit_code(ir)[0])
    cats = {i["category"] for i in result.delegation_issues}
    assert "recursion_stop_missing" in cats
    assert "cycle_risk" in cats


def test_delegation_visibility_in_verify_json(capsys, tmp_path) -> None:
    case = tmp_path / "delegation.vibe"
    case.write_text(BASE, encoding="utf-8")
    main(["verify", str(case), "--report", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert "delegation_summary" in payload
    assert "delegation_issues" in payload
    assert "delegation_obligations" in payload


def test_delegation_ir_deterministic_and_diff_visible() -> None:
    ir = _ir(BASE)
    assert serialize_ir(ir) == serialize_ir(ir)
    assert "delegation_summary" in serialize_ir(ir)

    changed = _ir(BASE.replace("max_depth: 3", "max_depth: 5"))
    diff = compute_intent_diff(ir, changed)
    assert any(change.category == "delegation" for change in diff.changes)


def test_delegation_emitter_metadata_and_explain_flag(capsys, tmp_path) -> None:
    ir = _ir(BASE)
    py, _ = emit_code(ir)
    assert "AGENT_DELEGATION" in py

    case = tmp_path / "delegation.vibe"
    case.write_text(BASE, encoding="utf-8")
    rc = main(["explain", str(case), "--show-delegation"])
    assert rc == 0
    assert "Delegation:" in capsys.readouterr().out
