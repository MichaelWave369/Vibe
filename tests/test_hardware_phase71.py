import json
from pathlib import Path

from vibe.cli import main
from vibe.emitter import emit_code
from vibe.hardware import derive_hardware_metadata, evaluate_hardware_generated_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.proof import build_proof_artifact
from vibe.verifier import verify


def _hardware_source(target: str = "vhdl") -> str:
    return f"""domain hardware

intent H:
  goal: \"g\"
  inputs:
    x: number
  outputs:
    y: number

preserve:
  timing < 10ns
  latency_cycles <= 4

constraint:
  no combinational loops
  synchronous
  deterministic

emit {target}
"""


def test_hardware_domain_parsing_and_metadata() -> None:
    ir = ast_to_ir(parse_source(_hardware_source("vhdl")))
    assert ir.domain_profile == "hardware"
    assert ir.module.hardware_summary["timing_rules"]
    assert ir.module.hardware_target_metadata["emit_target"] == "vhdl"
    summary, issues, obligations, target_meta = derive_hardware_metadata(ir)
    assert summary["has_no_combinational_loops_constraint"] is True
    assert any(o["obligation_id"].startswith("hardware.timing") for o in obligations)
    assert target_meta["emit_target"] == "vhdl"
    assert issues == []


def test_hardware_loop_diagnostic_detection() -> None:
    ir = ast_to_ir(parse_source(_hardware_source("vhdl")))
    issues, obligations = evaluate_hardware_generated_code(ir, "process(clk)\nbegin\n y <= y;\nend")
    assert any(i["issue_id"] == "hardware.combinational_loop.risk" for i in issues)
    assert any(o["status"] == "violated" for o in obligations)


def test_deterministic_vhdl_and_systemverilog_emission() -> None:
    ir_vhdl = ast_to_ir(parse_source(_hardware_source("vhdl")))
    c1, _ = emit_code(ir_vhdl)
    c2, _ = emit_code(ir_vhdl)
    assert c1 == c2
    assert "entity H is" in c1
    assert "rising_edge(clk)" in c1

    ir_sv = ast_to_ir(parse_source(_hardware_source("systemverilog")))
    s1, _ = emit_code(ir_sv)
    s2, _ = emit_code(ir_sv)
    assert s1 == s2
    assert "module H(" in s1
    assert "always_ff" in s1


def test_hardware_verify_and_proof_visibility() -> None:
    source = _hardware_source("vhdl")
    ir = ast_to_ir(parse_source(source))
    code, _ = emit_code(ir)
    result = verify(ir, code)
    assert result.domain_profile == "hardware"
    assert result.hardware_summary
    assert result.hardware_obligations

    proof = build_proof_artifact(Path("h.vibe"), source, ir, result, emitted_blocked=not result.passed)
    assert proof["domain"]["profile"] == "hardware"
    assert proof["hardware"]["summary"]
    assert "target_metadata" in proof["hardware"]


def test_hardware_examples_verify_and_compile(capsys) -> None:
    vhdl_example = Path("vibe/examples/hardware_intent.vibe")
    sv_example = Path("vibe/examples/hardware_intent_systemverilog.vibe")

    assert main(["verify", str(vhdl_example), "--report", "json"]) == 0
    verify_payload = json.loads(capsys.readouterr().out)
    assert verify_payload["domain_profile"] == "hardware"

    assert main(["compile", str(vhdl_example), "--no-cache", "--report", "json"]) == 0
    out = capsys.readouterr().out
    assert "emitted:" in out

    assert main(["verify", str(sv_example), "--report", "json"]) == 0
    sv_payload = json.loads(capsys.readouterr().out)
    assert sv_payload["domain_profile"] == "hardware"


def test_explain_show_hardware(capsys) -> None:
    ex = Path("vibe/examples/hardware_intent.vibe")
    rc = main(["explain", str(ex), "--show-domain", "--show-hardware"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Hardware:" in out
    assert "timing_rules" in out
