import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.legal_compliance import derive_legal_compliance_metadata, evaluate_legal_generated_artifact
from vibe.parser import parse_source
from vibe.proof import build_proof_artifact
from vibe.verifier import verify


def _compliance_source(with_pii_guard: bool = True) -> str:
    constraint_line = "  no PII in logs\n" if with_pii_guard else ""
    return f"""domain legal_compliance

intent PrivacyPipeline:
  goal: \"process customer updates without unsafe disclosure\"
  inputs:
    customer_email: string
    event: string
  outputs:
    status: string

preserve:
  GDPR compliance
  auditability
  data minimization

constraint:
{constraint_line}  consent required
  retention_limited
  lawful_basis_required

emit compliance_report
"""


def test_legal_domain_parsing_and_metadata() -> None:
    ir = ast_to_ir(parse_source(_compliance_source()))
    assert ir.domain_profile == "legal_compliance"
    assert ir.module.legal_compliance_summary["frameworks"] == ["GDPR"]
    assert ir.module.compliance_target_metadata["emit_target"] == "compliance_report"

    summary, issues, obligations, target_meta, pii, audit = derive_legal_compliance_metadata(ir)
    assert "gdpr compliance" in summary["preserves"]
    assert target_meta["emit_target"] == "compliance_report"
    assert pii["taint_class"] == "pii_sensitive"
    assert audit["manual_review_required"] is True
    assert issues == []
    assert obligations


def test_no_pii_logs_constraint_diagnostic_when_missing() -> None:
    ir = ast_to_ir(parse_source(_compliance_source(with_pii_guard=False)))
    assert any(i["issue_id"] == "legal_compliance.pii_logging.guard_missing" for i in ir.module.legal_compliance_issues)


def test_deterministic_compliance_report_emission() -> None:
    ir = ast_to_ir(parse_source(_compliance_source()))
    c1, _ = emit_code(ir)
    c2, _ = emit_code(ir)
    assert c1 == c2
    payload = json.loads(c1)
    assert payload["artifact_kind"] == "vibe_compliance_report"
    assert "logging_findings" in payload


def test_legal_codegen_violation_surface() -> None:
    ir = ast_to_ir(parse_source(_compliance_source()))
    bad_report = json.dumps({"logging_findings": {"pii_in_logs_detected": True}})
    issues, obligations = evaluate_legal_generated_artifact(ir, bad_report)
    assert any(i["issue_id"] == "legal_compliance.codegen.no_pii_logs.violation" for i in issues)
    assert any(o["obligation_id"] == "legal_compliance.codegen.no_pii_in_logs" and o["status"] == "violated" for o in obligations)


def test_legal_verify_and_proof_visibility() -> None:
    source = _compliance_source()
    ir = ast_to_ir(parse_source(source))
    code, _ = emit_code(ir)
    result = verify(ir, code)
    assert result.legal_compliance_summary
    assert result.legal_compliance_obligations
    assert result.pii_taint_summary

    proof = build_proof_artifact(Path("lc.vibe"), source, ir, result, emitted_blocked=not result.passed)
    assert proof["legal_compliance"]["summary"]
    assert proof["legal_compliance"]["pii_taint_summary"]


def test_legal_examples_verify_and_compile(capsys) -> None:
    ex1 = Path("vibe/examples/legal_compliance_intent.vibe")
    ex2 = Path("vibe/examples/legal_compliance_no_pii_logs.vibe")

    assert main(["verify", str(ex1), "--report", "json"]) == 0
    payload1 = json.loads(capsys.readouterr().out)
    assert payload1["domain_profile"] == "legal_compliance"

    assert main(["compile", str(ex1), "--no-cache", "--report", "json"]) == 0
    assert "emitted:" in capsys.readouterr().out

    assert main(["verify", str(ex2), "--report", "json"]) == 0
    payload2 = json.loads(capsys.readouterr().out)
    assert payload2["domain_profile"] == "legal_compliance"


def test_legal_diff_visibility() -> None:
    old_ir = ast_to_ir(parse_source(_compliance_source(with_pii_guard=True)))
    new_ir = ast_to_ir(parse_source(_compliance_source(with_pii_guard=False)))
    diff = compute_intent_diff(old_ir, new_ir)
    assert any(c.category == "legal_compliance" and c.item == "legal_compliance_summary" for c in diff.changes)


def test_explain_show_compliance(capsys) -> None:
    ex = Path("vibe/examples/legal_compliance_intent.vibe")
    rc = main(["explain", str(ex), "--show-domain", "--show-compliance"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Legal Compliance:" in out
    assert "pii_taint_summary" in out
