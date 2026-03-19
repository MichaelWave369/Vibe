"""Phase 8.4 interchange helpers for intent-as-intermediate-language workflows."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .cache import sha256_text
from .parser import parse_source

INTERCHANGE_ARTIFACT_VERSION = "phase-8.4.interchange.v1"
PROOF_BRIEF_VERSION = "phase-8.4.proof-brief.v1"
INTENT_BRIEF_VERSION = "phase-8.4.intent-brief.v1"


_word_re = re.compile(r"[A-Za-z0-9]+")


def _stable_words(text: str) -> list[str]:
    return [w.lower() for w in _word_re.findall(text)]


def derive_intent_name(text: str) -> str:
    words = _stable_words(text)
    if not words:
        return "InterchangeIntent"
    core = words[:4]
    return "".join(w.capitalize() for w in core) + "Intent"


def _first_sentence(text: str) -> str:
    clean = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not clean:
        return "Interchange requirement scaffold generated from empty text input"
    parts = re.split(r"(?<=[.!?])\s+", clean)
    return parts[0][:220]


def render_vibe_scaffold(intent_name: str, goal: str) -> str:
    return (
        f"intent {intent_name}:\n"
        f"  goal: \"{goal.replace(chr(34), chr(39))}\"\n"
        "  inputs:\n"
        "    requirement_text: string\n"
        "    context_blob: string\n"
        "  outputs:\n"
        "    decision_summary: string\n"
        "    machine_contract: string\n\n"
        "preserve:\n"
        "  requirement_traceability >= 1\n"
        "  deterministic_contract_shape >= 1\n\n"
        "constraint:\n"
        "  deterministic outputs\n"
        "  preserve requirement semantics\n"
        "  expose unknowns explicitly\n\n"
        "emit python\n"
    )


def build_interchange_from_text(text: str, source_path: Path | None = None) -> dict[str, object]:
    normalized = text.replace("\r\n", "\n")
    intent_name = derive_intent_name(normalized)
    goal = _first_sentence(normalized)
    vibe_spec = render_vibe_scaffold(intent_name, goal)

    return {
        "artifact_version": INTERCHANGE_ARTIFACT_VERSION,
        "source_requirement": {
            "kind": "plain_text",
            "origin": "human_text",
            "path": str(source_path) if source_path is not None else None,
            "sha256": sha256_text(normalized),
            "line_count": len(normalized.splitlines()) if normalized else 0,
            "char_count": len(normalized),
            "text_preview": goal,
        },
        "generated_intent": {
            "mode": "deterministic_scaffold",
            "intent_name": intent_name,
            "generated_vibe": vibe_spec,
        },
        "consumer_contract_summary": {
            "intent_name": intent_name,
            "goal": goal,
            "inputs": ["requirement_text", "context_blob"],
            "outputs": ["decision_summary", "machine_contract"],
            "preserve": ["requirement_traceability >= 1", "deterministic_contract_shape >= 1"],
            "constraints": [
                "deterministic outputs",
                "preserve requirement semantics",
                "expose unknowns explicitly",
            ],
            "emit_target": "python",
        },
        "export_metadata": {
            "deterministic": True,
            "interchange_role": "bounded_nl_to_vibe_scaffold",
            "non_goals": [
                "no live remote LLM integration",
                "no claim of perfect natural-language understanding",
                "not an autonomous correctness guarantee",
            ],
            "next_step": "human/agent review then vibec verify or compile",
        },
    }


def build_intent_brief(source_path: Path, source_text: str) -> dict[str, object]:
    program = parse_source(source_text)
    return {
        "brief_version": INTENT_BRIEF_VERSION,
        "source_path": str(source_path),
        "source_sha256": sha256_text(source_text),
        "intent": {
            "name": program.intent.name,
            "goal": program.intent.goal,
            "inputs": [{"name": f.name, "type": f.type_name} for f in program.intent.inputs],
            "outputs": [{"name": f.name, "type": f.type_name} for f in program.intent.outputs],
        },
        "preserve": [f"{r.key} {r.op} {r.value}" for r in program.preserve],
        "constraints": list(program.constraints),
        "bridge": [{"key": b.key, "value": b.value} for b in program.bridge],
        "emit_target": program.emit_target,
        "domain_profile": program.domain_profile,
        "interchange_metadata": {
            "source_kind": "vibe_spec",
            "transformation_state": "raw_intent_contract",
        },
    }


def build_proof_brief(proof: dict[str, object], *, proof_path: Path | None = None) -> dict[str, object]:
    obligations = proof.get("obligations", [])
    obligation_rows = obligations if isinstance(obligations, list) else []
    sample = []
    for row in obligation_rows[:10]:
        if isinstance(row, dict):
            sample.append(
                {
                    "obligation_id": row.get("obligation_id"),
                    "category": row.get("category"),
                    "status": row.get("status"),
                    "critical": bool(row.get("critical", False)),
                }
            )

    bridge = proof.get("bridge_metrics", {}) if isinstance(proof.get("bridge_metrics"), dict) else {}
    eq = proof.get("equivalence", {}) if isinstance(proof.get("equivalence"), dict) else {}

    return {
        "brief_version": PROOF_BRIEF_VERSION,
        "proof_path": str(proof_path) if proof_path is not None else None,
        "proof_artifact_version": proof.get("artifact_version"),
        "source_path": proof.get("source_path"),
        "verification_backend": proof.get("verification_backend"),
        "result": proof.get("result", {}),
        "intent_summary": {
            "source_hash": proof.get("source_hash"),
            "ir_hash": proof.get("ir_hash"),
            "emit_target": proof.get("emit_target"),
            "package_context": proof.get("package_context", {}),
            "domain_profile": (proof.get("domain", {}) or {}).get("profile")
            if isinstance(proof.get("domain"), dict)
            else None,
            "self_hosting": proof.get("self_hosting", {}),
        },
        "preserve_constraint_summary": {
            "obligation_summary": proof.get("obligation_summary", {}),
            "obligations_sample": sample,
            "obligations_total": len(obligation_rows),
        },
        "bridge_result": {
            "bridge_score": bridge.get("bridge_score"),
            "verdict": bridge.get("verdict"),
            "measurement_ratio": bridge.get("measurement_ratio"),
            "epsilon_metrics": proof.get("epsilon_metrics", {}),
        },
        "equivalence_drift_summary": {
            "intent_equivalence_score": eq.get("intent_equivalence_score"),
            "drift_score": eq.get("drift_score"),
            "intent_items_total": eq.get("intent_items_total"),
            "intent_items_missing": eq.get("intent_items_missing"),
            "intent_items_unknown": eq.get("intent_items_unknown"),
        },
        "interchange_metadata": {
            "source_kind": "proof_artifact",
            "consumer_safe": True,
            "deterministic_projection": True,
            "notes": [
                "Derived from existing proof artifact fields.",
                "Represents machine-readable understanding, not full formal behavior proof.",
            ],
        },
    }


def write_json_artifact(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
