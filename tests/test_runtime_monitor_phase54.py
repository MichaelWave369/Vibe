import json
from pathlib import Path

from vibe.cli import main
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir, serialize_ir
from vibe.parser import parse_source
from vibe.runtime_monitor import evaluate_runtime_events
from vibe.verifier import verify


SOURCE = """
intent MonitorFlow:
  goal: "Observe runtime drift against compiled contracts."
  inputs:
    request: PaymentRequest
  outputs:
    result: ProcessorDecision

preserve:
  latency < 50ms

bridge:
  measurement_safe_ratio = 0.85
  mode = strict

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

orchestrate MonitorPipe:
  Router -> Validator

emit python
"""


def _ir():
    return ast_to_ir(parse_source(SOURCE))


def test_monitor_config_generation_visible_in_ir_and_verify() -> None:
    ir = _ir()
    assert "monitored_agents" in ir.module.runtime_monitor
    result = verify(ir, emit_code(ir)[0])
    assert hasattr(result, "runtime_monitor_summary")


def test_runtime_event_evaluation_deterministic_and_detects_drift() -> None:
    ir = _ir()
    config = dict(ir.module.runtime_monitor)
    events = [
        {"event_type": "agent_invocation_finished", "agent_name": "Router", "latency_ms": 80, "result_signature": "a"},
        {"event_type": "agent_invocation_finished", "agent_name": "Router", "latency_ms": 90, "result_signature": "b"},
        {"event_type": "edge_transfer_observed", "edge_name": "Router->Validator", "observed_type": "ComplianceError", "edge_bridge_score": 0.6},
        {"event_type": "fallback_triggered", "agent_name": "Validator"},
    ]
    first = evaluate_runtime_events(config, events)
    second = evaluate_runtime_events(config, events)
    assert first == second
    drift_types = {d.get("type") for d in first["drift_signals"]}
    assert "boundary_shape_mismatch" in drift_types
    assert "latency_threshold_drop" in drift_types


def test_monitor_eval_cli_json(tmp_path, capsys) -> None:
    case = tmp_path / "monitor.vibe"
    case.write_text(SOURCE, encoding="utf-8")
    main(["verify", str(case), "--write-proof"])
    capsys.readouterr()
    proof = case.with_suffix(".vibe.proof.json")
    events = tmp_path / "events.json"
    events.write_text(
        json.dumps(
            [
                {"event_type": "edge_transfer_observed", "edge_name": "Router->Validator", "observed_type": "ProcessorDecision", "edge_bridge_score": 0.9},
                {"event_type": "fallback_triggered", "agent_name": "Validator"},
            ]
        ),
        encoding="utf-8",
    )

    rc = main(["monitor-eval", str(proof), str(events), "--report", "json", "--show-events"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "runtime_monitor_config" in payload
    assert "runtime_evaluation" in payload
    assert "events" in payload


def test_runtime_check_alias_and_emitter_visibility(tmp_path, capsys) -> None:
    ir = _ir()
    py_code, _ = emit_code(ir)
    assert "MONITOR_CONFIG" in py_code

    case = tmp_path / "monitor.vibe"
    case.write_text(SOURCE, encoding="utf-8")
    main(["verify", str(case), "--write-proof"])
    proof = case.with_suffix(".vibe.proof.json")
    events = tmp_path / "events.json"
    events.write_text(json.dumps([]), encoding="utf-8")
    rc = main(["runtime-check", str(proof), str(events)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Vibe Runtime Monitor Eval" in out


def test_runtime_monitor_ir_serialization_deterministic() -> None:
    ir = _ir()
    assert serialize_ir(ir) == serialize_ir(ir)
    assert "runtime_monitor" in serialize_ir(ir)
