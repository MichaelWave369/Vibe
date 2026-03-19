import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir, serialize_ir
from vibe.parser import parse_source
from vibe.verifier import verify


AGENT_SOURCE = """
intent PaymentPipeline:
  goal: "Route and validate processor decisions."
  inputs:
    request: PaymentRequest
  outputs:
    result: ValidatedDecision

preserve:
  deterministic = true

constraint:
  stateless routing

agent Router:
  role: "Select optimal processor"
  receives: PaymentRequest
  emits: ProcessorDecision
  preserve: deterministic
  constraint: stateless

agent Validator:
  role: "Validate decision against compliance rules"
  receives: ProcessorDecision
  emits: ValidatedDecision
  preserve: deterministic

agent DefaultProcessor:
  role: "Fallback processor"
  receives: PaymentRequest
  emits: ValidatedDecision
  preserve: deterministic

orchestrate PaymentPipeline:
  Router -> Validator
  on_error: fallback(DefaultProcessor)

emit python
"""


def _ir(source: str):
    return ast_to_ir(parse_source(source))


def test_parse_agent_graph_syntax() -> None:
    program = parse_source(AGENT_SOURCE)
    assert len(program.agents) == 3
    assert program.orchestrations[0].name == "PaymentPipeline"
    assert program.orchestrations[0].edges[0].source == "Router"


def test_ir_agent_graph_representation() -> None:
    ir = _ir(AGENT_SOURCE)
    summary = ir.module.agent_graph_summary
    assert summary["agent_count"] == 3
    assert summary["edge_count"] == 1
    assert summary["graph_name"] == "PaymentPipeline"


def test_orchestration_mismatch_and_fallback_validation() -> None:
    bad = AGENT_SOURCE.replace("receives: ProcessorDecision", "receives: ComplianceError").replace(
        "fallback(DefaultProcessor)", "fallback(MissingAgent)"
    )
    ir = _ir(bad)
    result = verify(ir, emit_code(ir)[0])
    assert result.agent_graph_issues
    assert any(i["category"] == "boundary_type_mismatch" for i in result.agent_graph_issues)
    assert any(i["category"] == "fallback_route" for i in result.agent_graph_issues)
    assert any(o.category == "agent_graph" for o in result.obligations)


def test_agent_graph_visibility_in_verify_json(capsys, tmp_path) -> None:
    case = tmp_path / "agent_graph.vibe"
    case.write_text(AGENT_SOURCE, encoding="utf-8")
    rc = main(["verify", str(case), "--report", "json"])
    assert rc in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert "agent_graph_summary" in payload
    assert "agent_graph_issues" in payload
    assert "agent_graph_obligations" in payload


def test_agent_graph_ir_serialization_deterministic() -> None:
    ir = _ir(AGENT_SOURCE)
    assert serialize_ir(ir) == serialize_ir(ir)
    assert "agent_graph_summary" in serialize_ir(ir)


def test_diff_includes_agent_graph_visibility() -> None:
    old = _ir(AGENT_SOURCE)
    new = _ir(AGENT_SOURCE.replace("Router -> Validator", "Validator -> Router"))
    diff = compute_intent_diff(old, new)
    assert any(change.category == "agent_graph" for change in diff.changes)


def test_emitters_include_agent_graph_metadata() -> None:
    ir = _ir(AGENT_SOURCE)
    py_code, _ = emit_code(ir)
    assert "AGENT_GRAPH" in py_code
    ts_src = AGENT_SOURCE.replace("emit python", "emit typescript")
    ts_code, _ = emit_code(_ir(ts_src))
    assert "AGENT_GRAPH" in ts_code


def test_explain_show_agents(capsys, tmp_path) -> None:
    case = tmp_path / "agent_graph.vibe"
    case.write_text(AGENT_SOURCE, encoding="utf-8")
    rc = main(["explain", str(case), "--show-agents"])
    assert rc == 0
    assert "Agent graph:" in capsys.readouterr().out
