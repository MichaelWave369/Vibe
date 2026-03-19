import json
from pathlib import Path

from vibe.cli import main
from vibe.diff import compute_intent_diff
from vibe.emitter import emit_code
from vibe.genomics import derive_genomics_metadata, evaluate_genomics_generated_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.proof import build_proof_artifact
from vibe.verifier import verify


def _genomics_source(target: str = "snakemake", with_privacy_guard: bool = True) -> str:
    constraint = "  no patient-identifiable metadata in outputs\n" if with_privacy_guard else ""
    return f"""domain genomics

intent Gx:
  goal: \"g\"
  inputs:
    patient_metadata: string
    counts: string
  outputs:
    result_table: string

preserve:
  reproducibility of differential expression results
  reproducible workflow
  provenance retained

constraint:
{constraint}  deidentify sample metadata
  deterministic sample ordering
  fixed reference version

emit {target}
"""


def test_genomics_domain_parsing_and_metadata() -> None:
    ir = ast_to_ir(parse_source(_genomics_source("snakemake")))
    assert ir.domain_profile == "genomics"
    assert ir.module.genomics_summary["reproducibility_preserved"] is True
    assert ir.module.genomics_target_metadata["emit_target"] == "snakemake"

    summary, issues, obligations, target_meta, privacy, provenance = derive_genomics_metadata(ir)
    assert summary["reproducibility_preserved"] is True
    assert target_meta["emit_target"] == "snakemake"
    assert privacy["sensitive_bindings"]
    assert provenance["workflow_stub_level"] == "phase-7.4"
    assert issues == []
    assert obligations


def test_genomics_privacy_diagnostic_when_guard_missing() -> None:
    ir = ast_to_ir(parse_source(_genomics_source(with_privacy_guard=False)))
    assert any(i["issue_id"] == "genomics.privacy.guard_missing" for i in ir.module.genomics_issues)


def test_deterministic_snakemake_and_nextflow_emission() -> None:
    ir_smk = ast_to_ir(parse_source(_genomics_source("snakemake")))
    c1, _ = emit_code(ir_smk)
    c2, _ = emit_code(ir_smk)
    assert c1 == c2
    assert "rule differential_expression" in c1

    ir_nf = ast_to_ir(parse_source(_genomics_source("nextflow")))
    n1, _ = emit_code(ir_nf)
    n2, _ = emit_code(ir_nf)
    assert n1 == n2
    assert "process differential_expression" in n1


def test_genomics_codegen_privacy_violation_surface() -> None:
    ir = ast_to_ir(parse_source(_genomics_source("nextflow")))
    code = "process x { script: 'echo patient_id > out.tsv' }"
    issues, obligations = evaluate_genomics_generated_code(ir, code)
    assert any(i["issue_id"] == "genomics.codegen.patient_metadata.leak_risk" for i in issues)
    assert any(o["obligation_id"] == "genomics.codegen.no_patient_identifiable_metadata" and o["status"] == "violated" for o in obligations)


def test_genomics_verify_and_proof_visibility() -> None:
    source = _genomics_source("snakemake")
    ir = ast_to_ir(parse_source(source))
    code, _ = emit_code(ir)
    result = verify(ir, code)
    assert result.genomics_summary
    assert result.genomics_obligations
    assert result.metadata_privacy_summary

    proof = build_proof_artifact(Path("g.vibe"), source, ir, result, emitted_blocked=not result.passed)
    assert proof["genomics"]["summary"]
    assert proof["genomics"]["metadata_privacy_summary"]


def test_genomics_examples_verify_and_compile(capsys) -> None:
    ex1 = Path("vibe/examples/genomics_intent.vibe")
    ex2 = Path("vibe/examples/genomics_intent_nextflow.vibe")

    assert main(["verify", str(ex1), "--report", "json"]) == 0
    payload1 = json.loads(capsys.readouterr().out)
    assert payload1["domain_profile"] == "genomics"

    assert main(["compile", str(ex1), "--no-cache", "--report", "json"]) == 0
    assert "emitted:" in capsys.readouterr().out

    assert main(["verify", str(ex2), "--report", "json"]) == 0
    payload2 = json.loads(capsys.readouterr().out)
    assert payload2["domain_profile"] == "genomics"


def test_genomics_diff_visibility() -> None:
    old_ir = ast_to_ir(parse_source(_genomics_source("snakemake", with_privacy_guard=True)))
    new_ir = ast_to_ir(parse_source(_genomics_source("snakemake", with_privacy_guard=False)))
    diff = compute_intent_diff(old_ir, new_ir)
    assert any(c.category == "genomics" and c.item == "genomics_summary" for c in diff.changes)


def test_explain_show_genomics(capsys) -> None:
    ex = Path("vibe/examples/genomics_intent.vibe")
    rc = main(["explain", str(ex), "--show-domain", "--show-genomics"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Genomics:" in out
    assert "metadata_privacy_summary" in out
