import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.proof import build_proof_artifact
from vibe.scientific_simulation import derive_scientific_simulation_metadata, evaluate_scientific_generated_code
from vibe.verifier import verify


def _simulation_source(bounded_error: str = "0.001") -> str:
    return f"""domain scientific_simulation

intent SimA:
  goal: \"g\"
  inputs:
    dt: number
    x: number
  outputs:
    y: number

preserve:
  conservation of energy
  bounded_error < {bounded_error}
  stable_time_step

constraint:
  reproducible
  seeded_rng
  deterministic_fp

emit julia
"""


def test_simulation_domain_parsing_and_metadata() -> None:
    ir = ast_to_ir(parse_source(_simulation_source()))
    assert ir.domain_profile == "scientific_simulation"
    assert ir.module.scientific_simulation_summary["invariants"]
    assert ir.module.scientific_target_metadata["emit_target"] == "julia"

    summary, issues, obligations, target_meta = derive_scientific_simulation_metadata(ir)
    assert "conservation of energy" in summary["invariants"]
    assert any(o["obligation_id"].startswith("scientific_simulation.constraint.reproducible") for o in obligations)
    assert target_meta["emit_target"] == "julia"
    assert issues == []


def test_simulation_reproducibility_codegen_obligations() -> None:
    ir = ast_to_ir(parse_source(_simulation_source()))
    code = "function evolve_step(dt, x)\n  return (y=0.0)\nend"
    issues, obligations = evaluate_scientific_generated_code(ir, code)
    assert any(i["issue_id"] == "scientific_simulation.codegen.seeded_rng.missing" for i in issues)
    assert any(o["obligation_id"] == "scientific_simulation.codegen.reproducible" for o in obligations)


def test_deterministic_julia_emission() -> None:
    ir = ast_to_ir(parse_source(_simulation_source()))
    c1, _ = emit_code(ir)
    c2, _ = emit_code(ir)
    assert c1 == c2
    assert "module SimA" in c1
    assert "function evolve_step" in c1
    assert "MersenneTwister(seed)" in c1


def test_simulation_verify_and_proof_visibility() -> None:
    source = _simulation_source()
    ir = ast_to_ir(parse_source(source))
    code, _ = emit_code(ir)
    result = verify(ir, code)
    assert result.domain_profile == "scientific_simulation"
    assert result.scientific_simulation_summary
    assert result.scientific_simulation_obligations

    proof = build_proof_artifact(Path("sim.vibe"), source, ir, result, emitted_blocked=not result.passed)
    assert proof["domain"]["profile"] == "scientific_simulation"
    assert proof["scientific_simulation"]["summary"]
    assert "target_metadata" in proof["scientific_simulation"]


def test_simulation_examples_verify_and_compile(capsys) -> None:
    ex1 = Path("vibe/examples/scientific_simulation_intent.vibe")
    ex2 = Path("vibe/examples/scientific_simulation_reproducible.vibe")

    assert main(["verify", str(ex1), "--report", "json"]) == 0
    payload1 = json.loads(capsys.readouterr().out)
    assert payload1["domain_profile"] == "scientific_simulation"

    assert main(["compile", str(ex1), "--no-cache", "--report", "json"]) == 0
    assert "emitted:" in capsys.readouterr().out

    assert main(["verify", str(ex2), "--report", "json"]) == 0
    payload2 = json.loads(capsys.readouterr().out)
    assert payload2["domain_profile"] == "scientific_simulation"


def test_simulation_diff_surfaces_changes() -> None:
    old_ir = ast_to_ir(parse_source(_simulation_source("0.001")))
    new_ir = ast_to_ir(parse_source(_simulation_source("0.01")))
    diff = compute_intent_diff(old_ir, new_ir)
    assert any(c.category == "scientific_simulation" and c.item == "scientific_simulation_summary" for c in diff.changes)


def test_explain_show_simulation(capsys) -> None:
    ex = Path("vibe/examples/scientific_simulation_intent.vibe")
    rc = main(["explain", str(ex), "--show-domain", "--show-simulation"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Scientific Simulation:" in out
    assert "invariants" in out
