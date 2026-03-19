"""Deterministic Snakemake emitter (Phase 7.4 genomics slice)."""

from __future__ import annotations

from .ir import IR


def generate_snakemake(ir: IR) -> str:
    inputs = sorted(ir.inputs.items())
    outputs = sorted(ir.outputs.items())
    input_names = [n for n, _ in inputs]
    output_names = [n for n, _ in outputs]

    lines = [
        f"# intent: {ir.intent_name}",
        f"# goal: {ir.goal}",
        f"# domain_profile: {ir.domain_profile}",
        f"# genomics_summary: {ir.module.genomics_summary}",
        f"# metadata_privacy_summary: {ir.module.metadata_privacy_summary}",
        f"# workflow_provenance_metadata: {ir.module.workflow_provenance_metadata}",
    ]
    lines += [f"# preserve: {k} {op} {v}".rstrip() for k, op, v in ir.preserve_rules]
    lines += [f"# constraint: {c}" for c in ir.constraints]
    lines += [
        "# NOTE: Phase 7.4 workflow scaffold. Manual pipeline command wiring required.",
        "",
        "rule all:",
        "    input:",
        f"        {output_names!r}",
        "",
        "rule deidentify_and_qc:",
        "    input:",
        f"        {input_names!r}",
        "    output:",
        "        'results/deidentified_metadata.tsv',",
        "        'results/qc_summary.tsv',",
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
        "        metadata='results/deidentified_metadata.tsv',",
        "        qc='results/qc_summary.tsv',",
        "    output:",
        "        'results/diffexpr.tsv',",
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
