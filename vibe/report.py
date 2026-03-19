"""Bridge report rendering utilities."""

from __future__ import annotations

import json
from dataclasses import asdict

from .verifier import VerificationResult


def report_dict(result: VerificationResult) -> dict[str, object]:
    """Return a JSON-serializable bridge report payload."""

    return asdict(result)


def render_report(
    result: VerificationResult,
    show_obligations: bool = True,
    show_equivalence: bool = False,
) -> str:
    """Render a detailed human-readable bridge report."""

    lines = [
        "=== Vibe Bridge Report ===",
        f"eps_pre: {result.epsilon_pre:.4f}",
        f"eps_post: {result.epsilon_post:.4f}",
        f"M_eps: {result.measurement_ratio:.4f}",
        f"C_bar: {result.c_bar:.4f}",
        "qixel metrics:",
        f"  q_persistence: {result.q_persistence:.4f}",
        f"  q_spatial_consistency: {result.q_spatial_consistency:.4f}",
        f"  q_cohesion: {result.q_cohesion:.4f}",
        f"  q_alignment: {result.q_alignment:.4f}",
        f"  q_intent_constant: {result.q_intent_constant:.4f}",
        f"petra_alignment: {result.petra_alignment:.4f}",
        f"multimodal_resonance: {result.multimodal_resonance:.4f}",
        f"bridge_score: {result.bridge_score:.4f}",
    ]
    if result.tesla_enabled:
        lines.extend(
            [
                "tesla:",
                f"  tesla_enabled: {result.tesla_enabled}",
                f"  substrate_bridge: {result.substrate_bridge}",
                f"  baseline_frequency_hz: {result.baseline_frequency_hz}",
                f"  harmonic_mode: {result.harmonic_mode}",
                f"  breath_monitor: {result.breath_monitor}",
                f"  sovereignty_preserved: {result.sovereignty_preserved}",
            ]
        )
    if result.agent_count:
        lines.extend(
            [
                "agent metrics:",
                f"  agent_count: {result.agent_count}",
                f"  spawn_depth: {result.spawn_depth}",
                f"  child_alignment: {result.child_alignment:.4f}",
                f"  delegation_integrity: {result.delegation_integrity:.4f}",
                f"  merge_preservation: {result.merge_preservation:.4f}",
                f"  agent_bridge_score: {result.agent_bridge_score:.4f}",
            ]
        )

    lines.extend([
        "verification backend:",
        f"  name: {result.verification_backend}",
        f"  version: {result.backend_version}",
        f"  mode: {result.backend_mode}",
        f"  capabilities: {result.backend_capabilities}",
        f"  details: {result.backend_details}",
    ])
    if result.backend_error:
        lines.append(f"  backend_error: {result.backend_error}")

    lines.extend(
        [
            "calibration:",
            f"  calibration_applied: {result.calibration_applied}",
            f"  calibration_model_version: {result.calibration_model_version}",
            f"  calibration_artifact_path: {result.calibration_artifact_path}",
            f"  calibration_confidence: {result.calibration_confidence}",
            f"  calibration_notes: {result.calibration_notes}",
        ]
    )

    lines.extend(
        [
            "candidate synthesis:",
            f"  candidate_count: {result.candidate_count}",
            f"  winning_candidate_id: {result.winning_candidate_id}",
            f"  synthesized_winner: {result.synthesized_winner}",
            f"  ranking_basis: {result.ranking_basis}",
            "equivalence/drift:",
            f"  intent_items_total: {result.intent_items_total}",
            f"  intent_items_matched: {result.intent_items_matched}",
            f"  intent_items_partial: {result.intent_items_partial}",
            f"  intent_items_missing: {result.intent_items_missing}",
            f"  intent_items_extra: {result.intent_items_extra}",
            f"  intent_items_unknown: {result.intent_items_unknown}",
            f"  intent_equivalence_score: {result.intent_equivalence_score:.4f}",
            f"  drift_score: {result.drift_score:.4f}",
        ]
    )
    lines.extend(
        [
            "intent-guided tests:",
            f"  test_generation_enabled: {result.test_generation_enabled}",
            f"  generated_test_files: {result.generated_test_files}",
            f"  preserve_rule_coverage: {result.preserve_rule_coverage}",
            f"  constraint_coverage: {result.constraint_coverage}",
            f"  uncovered_items: {result.uncovered_items}",
            f"  partial_coverage_items: {result.partial_coverage_items}",
            f"  test_generation_notes: {result.test_generation_notes}",
        ]
    )
    lines.extend(
        [
            "refinement:",
            f"  refinement_enabled: {result.refinement_enabled}",
            f"  refinement_iterations_run: {result.refinement_iterations_run}",
            f"  refinement_max_iterations: {result.refinement_max_iterations}",
            f"  refinement_success: {result.refinement_success}",
            f"  winning_iteration: {result.winning_iteration}",
            f"  refinement_failure_summary: {result.refinement_failure_summary}",
            f"  refinement_history: {result.refinement_history}",
        ]
    )
    lines.extend(
        [
            "semantic types:",
            f"  semantic_type_summary: {result.semantic_type_summary}",
            f"  semantic_type_issues: {result.semantic_type_issues}",
            f"  semantic_type_obligations: {result.semantic_type_obligations}",
        ]
    )
    lines.extend(
        [
            "effect types:",
            f"  effect_type_summary: {result.effect_type_summary}",
            f"  effect_type_issues: {result.effect_type_issues}",
            f"  effect_type_obligations: {result.effect_type_obligations}",
        ]
    )
    lines.extend(
        [
            "resource types:",
            f"  resource_type_summary: {result.resource_type_summary}",
            f"  resource_type_issues: {result.resource_type_issues}",
            f"  resource_type_obligations: {result.resource_type_obligations}",
        ]
    )
    if result.mapping_notes:
        lines.append(f"  notes: {result.mapping_notes}")
    if result.candidate_summaries:
        lines.append(f"  candidate_summaries: {result.candidate_summaries}")
    if show_equivalence:
        lines.append("  correspondence:")
        for c in result.correspondence_entries:
            lines.append(
                "    - "
                f"[{c.status}] ({c.category}) {c.source_item} -> {c.output_item} "
                f"sev={c.drift_severity} :: {c.evidence}"
            )

    lines.append("obligations:")
    lines.append(f"  counts: {result.obligation_counts}")
    if show_obligations:
        for o in result.obligations:
            lines.append(f"  - [{o.status}] {o.obligation_id} ({o.category}) :: {o.description}")
            if o.evidence:
                lines.append(f"      evidence: {o.evidence}")

    lines.extend([f"verdict: {result.verdict}", f"pass: {result.passed}"])
    return "\n".join(lines)


def render_report_json(result: VerificationResult) -> str:
    """Render a deterministic JSON bridge report."""

    return json.dumps(report_dict(result), indent=2, sort_keys=True)
