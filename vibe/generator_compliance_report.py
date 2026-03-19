"""Deterministic compliance_report emitter (Phase 7.3 legal/compliance slice)."""

from __future__ import annotations

import json

from .ir import IR


def generate_compliance_report(ir: IR) -> str:
    constraints = sorted(ir.constraints)
    preserve_rules = sorted([f"{k} {op} {v}".rstrip() for k, op, v in ir.preserve_rules])

    payload = {
        "artifact_kind": "vibe_compliance_report",
        "artifact_version": "phase-7.3",
        "intent": {
            "name": ir.intent_name,
            "goal": ir.goal,
            "domain_profile": ir.domain_profile,
            "emit_target": ir.emit_target,
            "inputs": dict(sorted(ir.inputs.items())),
            "outputs": dict(sorted(ir.outputs.items())),
        },
        "policy_scope": {
            "frameworks": ir.module.legal_compliance_summary.get("frameworks", []),
            "preserves": ir.module.legal_compliance_summary.get("preserves", []),
            "constraints": constraints,
            "preserve_rules": preserve_rules,
        },
        "compliance_summary": ir.module.legal_compliance_summary,
        "pii_taint_summary": ir.module.pii_taint_summary,
        "audit_trail": ir.module.audit_trail_metadata,
        "controls": {
            "consent_required": any(c.lower() == "consent required" for c in constraints),
            "retention_limited": any(c.lower() == "retention_limited" for c in constraints),
            "lawful_basis_required": any(c.lower() == "lawful_basis_required" for c in constraints),
            "purpose_limited": any(c.lower() == "purpose_limited" for c in constraints),
        },
        "logging_findings": {
            "no_pii_in_logs_required": any(c.lower() == "no pii in logs" for c in constraints),
            "pii_in_logs_detected": False,
            "notes": [
                "Phase 7.3 performs structural/metadata checks only.",
                "Manual legal + data governance review is still required.",
            ],
        },
        "obligations": ir.module.legal_compliance_obligations,
        "issues": ir.module.legal_compliance_issues,
        "target_metadata": ir.module.compliance_target_metadata,
        "status": {
            "critical_violations": [
                o.get("obligation_id")
                for o in ir.module.legal_compliance_obligations
                if o.get("critical") and o.get("status") == "violated"
            ],
            "unknown_critical": [
                o.get("obligation_id")
                for o in ir.module.legal_compliance_obligations
                if o.get("critical") and o.get("status") == "unknown"
            ],
            "manual_review_required": True,
        },
        "notes": [
            "This artifact is machine-checkable compliance structure, not legal certification.",
            "Evidence mappings are deterministic and auditable for review workflows.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
