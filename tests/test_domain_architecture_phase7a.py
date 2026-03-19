import json
from pathlib import Path

from vibe.cli import main
from vibe.domain_profiles import apply_domain_profile, domain_summary_json, list_domain_profiles, resolve_domain_profile
from vibe.emitter import emit_code, resolve_backend
from vibe.ir import ast_to_ir, serialize_ir
from vibe.parser import parse_source
from vibe.proof import build_proof_artifact
from vibe.report import render_report_json
from vibe.target_plugins import TargetPlugin, get_target_plugin, register_target_plugin
from vibe.verifier import verify


def _sample(domain: str, emit_target: str = "python") -> str:
    return f"""domain {domain}

intent D:
  goal: \"g\"
  inputs:
    x: number
  outputs:
    y: number

preserve:
  timing_setup < 2ns

constraint:
  synth ready rtl

emit {emit_target}
"""


def test_domain_profile_selection_and_listing_deterministic() -> None:
    rows = list_domain_profiles()
    names = [r["name"] for r in rows]
    assert names == ["genomics", "hardware", "legal_compliance", "scientific_simulation"]
    assert resolve_domain_profile("hardware") is not None
    assert resolve_domain_profile("missing") is None
    j1 = domain_summary_json()
    j2 = domain_summary_json()
    assert j1 == j2


def test_ir_domain_metadata_and_obligations_deterministic() -> None:
    ir = ast_to_ir(parse_source(_sample("hardware", "vhdl")))
    assert ir.domain_profile == "hardware"
    assert ir.module.domain_summary["profile"] == "hardware"
    assert ir.module.domain_obligations
    s1 = serialize_ir(ir)
    s2 = serialize_ir(ir)
    assert s1 == s2


def test_unknown_domain_is_visible() -> None:
    ir = ast_to_ir(parse_source(_sample("unknown_domain", "python")))
    assert ir.domain_profile == "unknown_domain"
    assert any(i["issue_id"].startswith("domain.unknown") for i in ir.module.domain_issues)


def test_target_plugin_contract_registration_and_scaffold_backend() -> None:
    register_target_plugin(TargetPlugin("custom_domain_target", ".cdt", False, "hardware", "test plugin"))
    plugin = get_target_plugin("custom_domain_target")
    assert plugin is not None
    backend = resolve_backend("custom_domain_target")
    ir = ast_to_ir(parse_source(_sample("hardware", "custom_domain_target")))
    code, used = emit_code(ir)
    assert used.target == "custom_domain_target"
    assert "scaffold emitter" in code


def test_domain_metadata_flows_to_report_and_proof() -> None:
    source = _sample("legal_compliance", "compliance_report")
    ir = ast_to_ir(parse_source(source))
    emitted, _ = emit_code(ir)
    result = verify(ir, emitted)
    report = json.loads(render_report_json(result))
    assert report["domain_profile"] == "legal_compliance"
    assert report["domain_summary"]["profile"] == "legal_compliance"

    proof = build_proof_artifact(Path("x.vibe"), source, ir, result, emitted_blocked=not result.passed)
    assert proof["domain"]["profile"] == "legal_compliance"


def test_domain_examples_compile_through_architecture_layer() -> None:
    examples = [
        Path("vibe/examples/hardware_intent.vibe"),
        Path("vibe/examples/scientific_simulation_intent.vibe"),
        Path("vibe/examples/scientific_simulation_reproducible.vibe"),
        Path("vibe/examples/legal_compliance_intent.vibe"),
        Path("vibe/examples/legal_compliance_no_pii_logs.vibe"),
        Path("vibe/examples/genomics_intent.vibe"),
    ]
    for ex in examples:
        program = parse_source(ex.read_text(encoding="utf-8"))
        ir = ast_to_ir(program)
        emitted, backend = emit_code(ir)
        assert ir.domain_profile in {"hardware", "scientific_simulation", "legal_compliance", "genomics"}
        assert backend.target == ir.emit_target
        assert "scaffold" in emitted or backend.target in {
            "python",
            "typescript",
            "julia",
            "vhdl",
            "systemverilog",
            "compliance_report",
        }


def test_cli_domains_and_explain_show_domain(capsys) -> None:
    rc = main(["domains", "--report", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "hardware" in out

    ex = Path("vibe/examples/hardware_intent.vibe")
    rc2 = main(["explain", str(ex), "--show-domain"])
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "Domain:" in out2
    assert "profile: hardware" in out2
