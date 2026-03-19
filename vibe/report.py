"""Bridge report rendering utilities."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .cache import sha256_text
from .verifier import VerificationResult

VERIFY_REPORT_SCHEMA_VERSION = "v1"


def report_dict(result: VerificationResult) -> dict[str, object]:
    """Return a JSON-serializable bridge report payload."""

    return asdict(result)


def _obligation_severity(result_row: dict[str, object]) -> str:
    if result_row.get("critical"):
        return "error"
    status = str(result_row.get("status", "")).lower()
    if status == "violated":
        return "warning"
    if status == "unknown":
        return "advisory"
    return "info"


def verify_contract_payload(
    result: VerificationResult,
    *,
    spec_path: str | None,
    proof_artifact_path: str | None = None,
    proof_sha256: str | None = None,
    input_mode: str = "path",
    snapshot_id: str | None = None,
    snapshot_store: str | None = None,
) -> dict[str, object]:
    """Stable, versioned verify JSON contract used by Muse integration."""

    legacy = report_dict(result)
    obligations: list[dict[str, object]] = []
    for row in legacy.get("obligations", []):
        obligation = {
            "id": row.get("obligation_id"),
            "category": row.get("category"),
            "address": row.get("source_location"),
            "status": row.get("status"),
            "message": row.get("description"),
            "severity": _obligation_severity(row),
            "expected": None,
            "observed": None,
        }
        obligations.append(obligation)

    obligations_satisfied = sum(1 for o in obligations if o["status"] == "satisfied")
    payload: dict[str, object] = dict(legacy)
    payload["schema_version"] = VERIFY_REPORT_SCHEMA_VERSION
    payload["report_type"] = "verify"
    payload["spec_path"] = spec_path
    payload["input_mode"] = input_mode
    payload["snapshot_id"] = snapshot_id
    payload["snapshot_store"] = snapshot_store
    payload["provenance"] = {
        "input_mode": input_mode,
        "spec_path": spec_path,
        "snapshot_id": snapshot_id,
        "snapshot_store": snapshot_store,
    }
    payload["bridge_score"] = result.bridge_score
    payload["epsilon_post"] = result.epsilon_post
    payload["measurement_ratio"] = result.measurement_ratio
    payload["epsilon_floor"] = result.epsilon_floor
    payload["measurement_safe_ratio"] = result.measurement_safe_ratio
    payload["obligations_total"] = len(obligations)
    payload["obligations_satisfied"] = obligations_satisfied
    payload["obligations"] = obligations
    payload["proof_artifact_path"] = proof_artifact_path
    payload["proof_sha256"] = proof_sha256
    payload["proof"] = {
        "artifact_path": proof_artifact_path,
        "sha256": proof_sha256,
    }
    payload["legacy_report"] = legacy
    return payload


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
    lines.extend(
        [
            "inference types:",
            f"  inference_type_summary: {result.inference_type_summary}",
            f"  inference_type_issues: {result.inference_type_issues}",
            f"  inference_type_obligations: {result.inference_type_obligations}",
        ]
    )
    lines.extend(
        [
            "agent graph:",
            f"  agent_graph_summary: {result.agent_graph_summary}",
            f"  agent_graph_issues: {result.agent_graph_issues}",
            f"  agent_graph_obligations: {result.agent_graph_obligations}",
        ]
    )
    lines.extend(
        [
            "agent boundary bridges:",
            f"  agent_boundary_summary: {result.agent_boundary_summary}",
            f"  agent_boundary_issues: {result.agent_boundary_issues}",
            f"  agent_boundary_obligations: {result.agent_boundary_obligations}",
        ]
    )
    lines.extend(
        [
            "delegation:",
            f"  delegation_summary: {result.delegation_summary}",
            f"  delegation_issues: {result.delegation_issues}",
            f"  delegation_obligations: {result.delegation_obligations}",
        ]
    )
    lines.extend(
        [
            "runtime monitor:",
            f"  runtime_monitor_summary: {result.runtime_monitor_summary}",
        ]
    )
    lines.extend(
        [
            "package context:",
            f"  package_context: {result.package_context}",
        ]
    )
    lines.extend(
        [
            "domain:",
            f"  domain_profile: {result.domain_profile}",
            f"  domain_summary: {result.domain_summary}",
            f"  domain_issues: {result.domain_issues}",
            f"  domain_target_metadata: {result.domain_target_metadata}",
        ]
    )
    lines.extend(
        [
            "hardware:",
            f"  hardware_summary: {result.hardware_summary}",
            f"  hardware_issues: {result.hardware_issues}",
            f"  hardware_target_metadata: {result.hardware_target_metadata}",
        ]
    )
    lines.extend(
        [
            "scientific simulation:",
            f"  scientific_simulation_summary: {result.scientific_simulation_summary}",
            f"  scientific_simulation_issues: {result.scientific_simulation_issues}",
            f"  scientific_simulation_obligations: {result.scientific_simulation_obligations}",
            f"  scientific_target_metadata: {result.scientific_target_metadata}",
        ]
    )
    lines.extend(
        [
            "legal compliance:",
            f"  legal_compliance_summary: {result.legal_compliance_summary}",
            f"  legal_compliance_issues: {result.legal_compliance_issues}",
            f"  legal_compliance_obligations: {result.legal_compliance_obligations}",
            f"  compliance_target_metadata: {result.compliance_target_metadata}",
            f"  pii_taint_summary: {result.pii_taint_summary}",
            f"  audit_trail_metadata: {result.audit_trail_metadata}",
        ]
    )
    lines.extend(
        [
            "genomics:",
            f"  genomics_summary: {result.genomics_summary}",
            f"  genomics_issues: {result.genomics_issues}",
            f"  genomics_obligations: {result.genomics_obligations}",
            f"  genomics_target_metadata: {result.genomics_target_metadata}",
            f"  metadata_privacy_summary: {result.metadata_privacy_summary}",
            f"  workflow_provenance_metadata: {result.workflow_provenance_metadata}",
        ]
    )
    lines.extend(
        [
            "self hosting:",
            f"  self_hosting_enabled: {result.self_hosting_enabled}",
            f"  compiler_spec_path: {result.compiler_spec_path}",
            f"  self_bridge_score: {result.self_bridge_score}",
            f"  self_regression_status: {result.self_regression_status}",
            f"  self_baseline_reference: {result.self_baseline_reference}",
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


def render_report_json(
    result: VerificationResult,
    *,
    spec_path: str | Path | None = "<unknown>",
    proof_artifact_path: str | Path | None = None,
    input_mode: str = "path",
    snapshot_id: str | None = None,
    snapshot_store: str | Path | None = None,
) -> str:
    """Render a deterministic JSON bridge report."""

    proof_sha256 = None
    if proof_artifact_path is not None:
        proof_text = Path(proof_artifact_path).read_text(encoding="utf-8") if Path(proof_artifact_path).exists() else None
        if proof_text is not None:
            proof_sha256 = sha256_text(proof_text)
    payload = verify_contract_payload(
        result,
        spec_path=str(spec_path) if spec_path is not None else None,
        proof_artifact_path=str(proof_artifact_path) if proof_artifact_path is not None else None,
        proof_sha256=proof_sha256,
        input_mode=input_mode,
        snapshot_id=snapshot_id,
        snapshot_store=str(snapshot_store) if snapshot_store is not None else None,
    )
    return json.dumps(payload, indent=2, sort_keys=True)
