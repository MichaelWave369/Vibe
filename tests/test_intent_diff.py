import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff, render_intent_diff_json
from vibe.ir import ast_to_ir
from vibe.parser import parse_source


def _ir(src: str):
    return ast_to_ir(parse_source(src))


def test_goal_and_io_diff_classification() -> None:
    old = _ir(
        """
intent PaymentRouter:
  goal: "route cheapest"
  inputs:
    amount: number
  outputs:
    processor: string
bridge:
  epsilon_floor = 0.02
emit python
"""
    )
    new = _ir(
        """
intent PaymentRouter:
  goal: "route cheapest valid with sla"
  inputs:
    amount: number
    country: string
  outputs:
    processor: string
    total_fee: number
bridge:
  epsilon_floor = 0.02
emit python
"""
    )

    result = compute_intent_diff(old, new)
    keys = {(c.category, c.item, c.change_type, c.semantic_effect) for c in result.changes}
    assert ("goal", "intent.goal", "modified", "unknown") in keys
    assert ("input", "country", "added", "narrowed") in keys
    assert ("output", "total_fee", "added", "broadened") in keys


def test_preserve_constraint_bridge_emit_diff() -> None:
    old = _ir(
        """
intent X:
  goal: "g"
  inputs:
    a: number
  outputs:
    b: number
preserve:
  latency < 300ms
constraint:
  graceful fallback
bridge:
  epsilon_floor = 0.03
  measurement_safe_ratio = 0.85
emit python
"""
    )
    new = _ir(
        """
intent X:
  goal: "g"
  inputs:
    a: number
  outputs:
    b: number
preserve:
  latency < 200ms
  compliance = strict
constraint:
  deterministic ordering
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.90
emit typescript
"""
    )

    result = compute_intent_diff(old, new)
    by_cat = {(c.category, c.item, c.change_type, c.semantic_effect) for c in result.changes}
    assert ("preserve", "compliance", "added", "narrowed") in by_cat
    assert ("constraint", "graceful fallback", "removed", "broadened") in by_cat
    assert ("bridge", "epsilon_floor", "modified", "narrowed") in by_cat
    assert ("emit", "emit_target", "target_changed", "unknown") in by_cat


def test_tesla_agentora_agentception_changes_detected() -> None:
    old = _ir(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"))
    new = _ir(Path("vibe/examples/sovereign_bridge.vibe").read_text(encoding="utf-8"))

    result = compute_intent_diff(old, new)
    categories = {c.category for c in result.changes}
    assert "tesla_victory_layer" in categories
    assert "agentora" in categories
    assert "agentception" in categories


def test_intent_diff_json_deterministic() -> None:
    old = _ir(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"))
    new = _ir(Path("vibe/examples/edge_contract_ts.vibe").read_text(encoding="utf-8"))

    r1 = render_intent_diff_json(compute_intent_diff(old, new))
    r2 = render_intent_diff_json(compute_intent_diff(old, new))
    assert r1 == r2
    payload = json.loads(r1)
    assert "summary" in payload
    assert "changes" in payload


def test_cli_diff_json_snapshot(capsys, tmp_path) -> None:
    old_src = Path("vibe/examples/payment_router.vibe")
    new_src = Path("vibe/examples/edge_contract_ts.vibe")
    old_case = tmp_path / "old.vibe"
    new_case = tmp_path / "new.vibe"
    old_case.write_text(old_src.read_text(encoding="utf-8"), encoding="utf-8")
    new_case.write_text(new_src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["diff", str(old_case), str(new_case), "--report", "json"])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert "summary" in payload
    assert any(change["category"] == "emit" for change in payload["changes"])
