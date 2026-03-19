"""Deterministic Snakemake emitter (Phase 7.4 genomics slice)."""

from __future__ import annotations

from .ir import IR


def generate_snakemake(ir: IR) -> str:
    inputs = sorted(ir.inputs.items())
    outputs = sorted(ir.outputs.items())
    input_names = [n for n, _ in inputs]
    output_names = [n for n, _ in outputs]
    workflow_name = f"{ir.intent_name}_genomics_pipeline".lower()
    metadata_output = "results/deidentified_metadata.tsv"
    qc_output = "results/qc_summary.tsv"
    analysis_outputs = [f"results/{name}.tsv" for name in output_names] or ["results/diffexpr.tsv"]

    lines = [
        f"# intent: {ir.intent_name}",
        f"# goal: {ir.goal}",
        f"# domain_profile: {ir.domain_profile}",
        f"# genomics_summary: {ir.module.genomics_summary}",
        f"# metadata_privacy_summary: {ir.module.metadata_privacy_summary}",
        f"# workflow_provenance_metadata: {ir.module.workflow_provenance_metadata}",
        f"# workflow_name: {workflow_name}",
    ]
    lines += [f"# preserve: {k} {op} {v}".rstrip() for k, op, v in ir.preserve_rules]
    lines += [f"# constraint: {c}" for c in ir.constraints]
    lines += [
        "# NOTE: Phase 7.4 workflow scaffold. Manual pipeline command wiring required.",
        "",
        "rule all:",
        "    input:",
        f"        {analysis_outputs!r}",
        "",
        "rule deidentify_and_qc:",
        "    input:",
        f"        {input_names!r}",
        "    output:",
        f"        '{metadata_output}',",
        f"        '{qc_output}',",
        "    params:",
        "        reference_version='GRCh38.p14',",
        "        deterministic_sample_ordering=True,",
        "    shell:",
        "        \"\"\"",
        "        # TODO: apply deidentify sample metadata strategy",
        "        # TODO: run deterministic sample ordering + QC",
        "        # TODO: pin fixed reference version in tool invocation",
        "        touch {output}",
        "        \"\"\"",
        "",
        "rule differential_expression:",
        "    input:",
        f"        metadata='{metadata_output}',",
        f"        qc='{qc_output}',",
        "    output:",
        *[f"        '{path}'," for path in analysis_outputs],
        "    params:",
        "        reference_version='GRCh38.p14',",
        "    shell:",
        "        \"\"\"",
        "        # TODO: run reproducible differential expression analysis",
        "        # TODO: preserve provenance retained contract",
        "        touch {output}",
        "        \"\"\"",
        "",
    ]
    return "\n".join(lines)
