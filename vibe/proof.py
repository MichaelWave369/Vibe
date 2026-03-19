"""Preservation proof artifact generation and inspection."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .cache import sha256_text
from .ir import IR, serialize_ir
from .verifier import VerificationResult

PROOF_ARTIFACT_VERSION = "v1"


REQUIRED_FIELDS = {
    "artifact_version",
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
) -> dict[str, object]:
    ir_ser = serialize_ir(ir)
    artifact = {
        "artifact_version": PROOF_ARTIFACT_VERSION,
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
    missing = sorted(REQUIRED_FIELDS - set(payload.keys()))
    if missing:
        raise ValueError(f"invalid proof artifact: missing fields: {', '.join(missing)}")
    if payload.get("artifact_version") != PROOF_ARTIFACT_VERSION:
        raise ValueError(
            f"invalid proof artifact version `{payload.get('artifact_version')}`; expected `{PROOF_ARTIFACT_VERSION}`"
        )


def render_proof_summary(payload: dict[str, object]) -> str:
    result = payload["result"]
    backend = payload["verification_backend"]
    calibration = payload["calibration"]
    bridge = payload["bridge_metrics"]
    eq = payload["equivalence"]
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
            f"obligation_counts: {payload['obligation_summary']}",
        ]
    )
