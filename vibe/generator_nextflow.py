"""Deterministic Nextflow emitter (Phase 7.4 genomics slice)."""

from __future__ import annotations

from .ir import IR


def generate_nextflow(ir: IR) -> str:
    inputs = sorted(ir.inputs.items())

    lines = [
        f"// intent: {ir.intent_name}",
        f"// goal: {ir.goal}",
        f"// domain_profile: {ir.domain_profile}",
        f"// genomics_summary: {ir.module.genomics_summary}",
        f"// metadata_privacy_summary: {ir.module.metadata_privacy_summary}",
        f"// workflow_provenance_metadata: {ir.module.workflow_provenance_metadata}",
    ]
    lines += [f"// preserve: {k} {op} {v}".rstrip() for k, op, v in ir.preserve_rules]
    lines += [f"// constraint: {c}" for c in ir.constraints]

    lines += [
        "// NOTE: Phase 7.4 workflow scaffold. Manual command wiring required.",
        "",
        "nextflow.enable.dsl=2",
        "",
        "params.reference_version = 'GRCh38.p14'",
        "params.deterministic_sample_ordering = true",
        "",
        "workflow {",
        "  Channel.of(" + ", ".join(repr(n) for n, _ in inputs) + ").set { input_meta }",
        "  deidentify(input_meta)",
        "  differential_expression(deidentify.out)",
        "}",
        "",
        "process deidentify {",
        "  tag 'deidentify sample metadata'",
        "  input:",
        "    val meta from input_meta",
        "  output:",
        "    path 'deidentified.tsv'",
        "  script:",
        "  \"\"\"",
        "  # TODO: implement deidentify sample metadata stage",
        "  # TODO: enforce deterministic sample ordering",
        "  touch deidentified.tsv",
        "  \"\"\"",
        "}",
        "",
        "process differential_expression {",
        "  tag 'reproducibility of differential expression results'",
        "  input:",
        "    path deid",
        "  output:",
        "    path 'diffexpr.tsv'",
        "  script:",
        "  \"\"\"",
        "  # TODO: pin fixed reference version and run analysis",
        "  # TODO: retain provenance metadata for workflow reproducibility",
        "  touch diffexpr.tsv",
        "  \"\"\"",
        "}",
        "",
    ]

    return "\n".join(lines)
