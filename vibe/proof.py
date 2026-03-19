"""Preservation proof artifact generation and inspection."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .cache import sha256_text
from .ir import IR, serialize_ir
from .verifier import VerificationResult

PROOF_ARTIFACT_VERSION = "v1"
PROOF_SCHEMA_VERSION = "v1"


REQUIRED_FIELDS = {
    "artifact_version",
    "schema_version",
    "source_path",
    "source_hash",
    "ir_hash",
    "emit_target",
    "verification_backend",
    "backend_metadata",
    "calibration",
    "obligation_summary",
    "obligations",
    "equivalence",
    "bridge_metrics",
    "epsilon_metrics",
    "result",
    "candidates",
    "intent_guided_tests",
    "refinement",
    "semantic_types",
    "effect_types",
    "resource_types",
    "inference_types",
    "agent_graph",
    "agent_boundary_bridges",
    "delegation",
    "runtime_monitor",
    "provenance",
    "package_context",
    "domain",
    "hardware",
    "scientific_simulation",
    "legal_compliance",
    "genomics",
    "self_hosting",
    "notes",
}


def default_proof_path(source_path: Path) -> Path:
    return source_path.with_suffix(".vibe.proof.json")


def build_proof_artifact(
    source_path: Path,
    source_text: str,
    ir: IR,
    result: VerificationResult,
    *,
    emitted_blocked: bool,
    notes: list[str] | None = None,
    input_mode: str = "path",
    spec_path: str | None = None,
    snapshot_id: str | None = None,
    snapshot_store: str | None = None,
) -> dict[str, object]:
    ir_ser = serialize_ir(ir)
    artifact = {
        "artifact_version": PROOF_ARTIFACT_VERSION,
        "schema_version": PROOF_SCHEMA_VERSION,
        "source_path": str(source_path),
        "source_hash": sha256_text(source_text),
        "ir_hash": sha256_text(ir_ser),
        "emit_target": ir.emit_target,
        "verification_backend": result.verification_backend,
        "backend_metadata": {
            "version": result.backend_version,
            "mode": result.backend_mode,
            "capabilities": result.backend_capabilities,
            "details": result.backend_details,
            "error": result.backend_error,
        },
        "calibration": {
            "applied": result.calibration_applied,
            "model_version": result.calibration_model_version,
            "artifact_path": result.calibration_artifact_path,
            "confidence": result.calibration_confidence,
            "notes": result.calibration_notes,
        },
        "obligation_summary": dict(result.obligation_counts),
        "obligations": [asdict(o) for o in result.obligations],
        "equivalence": {
            "intent_items_total": result.intent_items_total,
            "intent_items_matched": result.intent_items_matched,
            "intent_items_partial": result.intent_items_partial,
            "intent_items_missing": result.intent_items_missing,
            "intent_items_extra": result.intent_items_extra,
            "intent_items_unknown": result.intent_items_unknown,
            "intent_equivalence_score": result.intent_equivalence_score,
            "drift_score": result.drift_score,
            "mapping_notes": result.mapping_notes,
            "structural_only": True,
            "correspondence_entries": [asdict(c) for c in result.correspondence_entries],
        },
        "bridge_metrics": {
            "bridge_score": result.bridge_score,
            "verdict": result.verdict,
            "measurement_ratio": result.measurement_ratio,
            "c_bar": result.c_bar,
            "q_persistence": result.q_persistence,
            "q_spatial_consistency": result.q_spatial_consistency,
            "q_cohesion": result.q_cohesion,
            "q_alignment": result.q_alignment,
            "q_intent_constant": result.q_intent_constant,
            "petra_alignment": result.petra_alignment,
            "multimodal_resonance": result.multimodal_resonance,
        },
        "epsilon_metrics": {
            "epsilon_pre": result.epsilon_pre,
            "epsilon_post": result.epsilon_post,
        },
        "result": {
            "passed": result.passed,
            "emission_blocked": emitted_blocked,
        },
        "candidates": {
            "candidate_count": result.candidate_count,
            "winning_candidate_id": result.winning_candidate_id,
            "synthesized_winner": result.synthesized_winner,
            "ranking_basis": result.ranking_basis,
            "candidate_summaries": result.candidate_summaries,
        },
        "intent_guided_tests": {
            "test_generation_enabled": result.test_generation_enabled,
            "generated_test_files": result.generated_test_files,
            "preserve_rule_coverage": result.preserve_rule_coverage,
            "constraint_coverage": result.constraint_coverage,
            "uncovered_items": result.uncovered_items,
            "partial_coverage_items": result.partial_coverage_items,
            "test_generation_notes": result.test_generation_notes,
        },
        "refinement": {
            "refinement_enabled": result.refinement_enabled,
            "refinement_iterations_run": result.refinement_iterations_run,
            "refinement_max_iterations": result.refinement_max_iterations,
            "refinement_success": result.refinement_success,
            "winning_iteration": result.winning_iteration,
            "winning_candidate_id": result.winning_candidate_id,
            "refinement_failure_summary": result.refinement_failure_summary,
            "refinement_history": result.refinement_history,
            "hit_max_iterations": result.refinement_enabled
            and (not result.refinement_success)
            and (result.refinement_iterations_run >= result.refinement_max_iterations),
        },
        "semantic_types": {
            "summary": result.semantic_type_summary,
            "issues": result.semantic_type_issues,
            "derived_obligations": result.semantic_type_obligations,
        },
        "effect_types": {
            "summary": result.effect_type_summary,
            "issues": result.effect_type_issues,
            "derived_obligations": result.effect_type_obligations,
        },
        "resource_types": {
            "summary": result.resource_type_summary,
            "issues": result.resource_type_issues,
            "derived_obligations": result.resource_type_obligations,
        },
        "inference_types": {
            "summary": result.inference_type_summary,
            "issues": result.inference_type_issues,
            "derived_obligations": result.inference_type_obligations,
        },
        "agent_graph": {
            "summary": result.agent_graph_summary,
            "issues": result.agent_graph_issues,
            "derived_obligations": result.agent_graph_obligations,
        },
        "agent_boundary_bridges": {
            "summary": result.agent_boundary_summary,
            "issues": result.agent_boundary_issues,
            "derived_obligations": result.agent_boundary_obligations,
        },
        "delegation": {
            "summary": result.delegation_summary,
            "issues": result.delegation_issues,
            "derived_obligations": result.delegation_obligations,
        },
        "runtime_monitor": dict(result.runtime_monitor_summary),
        "package_context": dict(result.package_context),
        "domain": {
            "profile": result.domain_profile,
            "summary": result.domain_summary,
            "issues": result.domain_issues,
            "obligations": result.domain_obligations,
            "target_metadata": result.domain_target_metadata,
        },
        "hardware": {
            "summary": result.hardware_summary,
            "issues": result.hardware_issues,
            "obligations": result.hardware_obligations,
            "target_metadata": result.hardware_target_metadata,
        },
        "scientific_simulation": {
            "summary": result.scientific_simulation_summary,
            "issues": result.scientific_simulation_issues,
            "obligations": result.scientific_simulation_obligations,
            "target_metadata": result.scientific_target_metadata,
        },
        "legal_compliance": {
            "summary": result.legal_compliance_summary,
            "issues": result.legal_compliance_issues,
            "obligations": result.legal_compliance_obligations,
            "target_metadata": result.compliance_target_metadata,
            "pii_taint_summary": result.pii_taint_summary,
            "audit_trail_metadata": result.audit_trail_metadata,
        },
        "genomics": {
            "summary": result.genomics_summary,
            "issues": result.genomics_issues,
            "obligations": result.genomics_obligations,
            "target_metadata": result.genomics_target_metadata,
            "metadata_privacy_summary": result.metadata_privacy_summary,
            "workflow_provenance_metadata": result.workflow_provenance_metadata,
        },
        "self_hosting": {
            "self_hosting_enabled": result.self_hosting_enabled,
            "compiler_spec_path": result.compiler_spec_path,
            "self_bridge_score": result.self_bridge_score,
            "self_regression_status": result.self_regression_status,
            "self_baseline_reference": result.self_baseline_reference,
        },
        "interchange": {
            "source_kind": "direct_vibe_source",
            "transformation_state": "verified_compiled_intent",
            "artifact_links": [],
            "consumer_brief_links": [],
        },
        "provenance": {
            "input_mode": input_mode,
            "spec_path": spec_path if spec_path is not None else (str(source_path) if input_mode == "path" else None),
            "snapshot_id": snapshot_id,
            "snapshot_store": snapshot_store,
        },
        "external_obligation_providers": list(result.external_obligation_providers),
        "notes": notes or [],
    }
    return artifact


def write_proof_artifact(path: Path, artifact: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")


def load_proof_artifact(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_proof_artifact(payload)
    return payload


def validate_proof_artifact(payload: dict[str, object]) -> None:
    if payload.get("schema_version") != PROOF_SCHEMA_VERSION:
        raise ValueError(
            f"invalid proof schema version `{payload.get('schema_version')}`; expected `{PROOF_SCHEMA_VERSION}`"
        )
    if payload.get("artifact_version") != PROOF_ARTIFACT_VERSION:
        raise ValueError(
            f"invalid proof artifact version `{payload.get('artifact_version')}`; expected `{PROOF_ARTIFACT_VERSION}`"
        )
    missing = sorted(REQUIRED_FIELDS - set(payload.keys()))
    if missing:
        raise ValueError(f"invalid proof artifact: missing fields: {', '.join(missing)}")


def render_proof_summary(payload: dict[str, object]) -> str:
    result = payload["result"]
    backend = payload["verification_backend"]
    calibration = payload["calibration"]
    bridge = payload["bridge_metrics"]
    eq = payload["equivalence"]
    candidate_meta = payload["candidates"]
    test_meta = payload["intent_guided_tests"]
    refinement_meta = payload["refinement"]
    semantic_meta = payload["semantic_types"]
    effect_meta = payload["effect_types"]
    resource_meta = payload["resource_types"]
    inference_meta = payload["inference_types"]
    agent_graph_meta = payload["agent_graph"]
    boundary_meta = payload["agent_boundary_bridges"]
    delegation_meta = payload["delegation"]
    monitor_meta = payload["runtime_monitor"]
    package_meta = payload["package_context"]
    domain_meta = payload["domain"]
    hardware_meta = payload["hardware"]
    simulation_meta = payload["scientific_simulation"]
    legal_meta = payload["legal_compliance"]
    genomics_meta = payload["genomics"]
    self_hosting_meta = payload["self_hosting"]
    interchange_meta = payload.get("interchange", {})
    return "\n".join(
        [
            "=== Vibe Proof Summary ===",
            f"source: {payload['source_path']}",
            f"result: {'PASS' if result['passed'] else 'FAIL'}",
            f"emission_blocked: {result['emission_blocked']}",
            f"backend: {backend}",
            f"calibration_applied: {calibration['applied']}",
            f"bridge_score: {bridge['bridge_score']:.4f}",
            f"measurement_ratio: {bridge['measurement_ratio']:.4f}",
            f"equivalence_score: {eq['intent_equivalence_score']:.4f}",
            f"drift_score: {eq['drift_score']:.4f}",
            f"candidate_count: {candidate_meta['candidate_count']}",
            f"winning_candidate: {candidate_meta['winning_candidate_id']}",
            f"obligation_counts: {payload['obligation_summary']}",
            f"test_generation_enabled: {test_meta['test_generation_enabled']}",
            f"generated_test_files: {test_meta['generated_test_files']}",
            f"refinement_enabled: {refinement_meta['refinement_enabled']}",
            f"refinement_iterations_run: {refinement_meta['refinement_iterations_run']}",
            f"refinement_success: {refinement_meta['refinement_success']}",
            f"semantic_issue_count: {len(semantic_meta['issues'])}",
            f"effect_issue_count: {len(effect_meta['issues'])}",
            f"resource_issue_count: {len(resource_meta['issues'])}",
            f"inference_issue_count: {len(inference_meta['issues'])}",
            f"agent_graph_issue_count: {len(agent_graph_meta['issues'])}",
            f"agent_boundary_issue_count: {len(boundary_meta['issues'])}",
            f"delegation_issue_count: {len(delegation_meta['issues'])}",
            f"monitor_bridge_threshold: {monitor_meta.get('bridge_threshold')}",
            f"package: {package_meta.get('package_name', '<none>')}@{package_meta.get('package_version', '<none>')}",
            f"domain_profile: {domain_meta.get('profile', 'general')}",
            f"hardware_issue_count: {len(hardware_meta.get('issues', []))}",
            f"scientific_simulation_issue_count: {len(simulation_meta.get('issues', []))}",
            f"legal_compliance_issue_count: {len(legal_meta.get('issues', []))}",
            f"genomics_issue_count: {len(genomics_meta.get('issues', []))}",
            f"self_hosting_enabled: {self_hosting_meta.get('self_hosting_enabled')}",
            f"self_regression_status: {self_hosting_meta.get('self_regression_status')}",
            f"interchange_source_kind: {interchange_meta.get('source_kind', '<unknown>')}",
        ]
    )
