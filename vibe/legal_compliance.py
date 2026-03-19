"""Legal/compliance intent analysis and obligation helpers (Phase 7.3)."""

from __future__ import annotations

import json

from .ir import IR


_ALLOWED_PRESERVES = {
    "gdpr compliance",
    "auditability",
    "data minimization",
    "right_to_erasure",
}


_PII_HINTS = ("email", "name", "ssn", "phone", "address", "dob", "pii")


def _obligation(
    obligation_id: str,
    description: str,
    status: str,
    evidence: str,
    *,
    critical: bool,
) -> dict[str, object]:
    return {
        "obligation_id": obligation_id,
        "category": "legal_compliance",
        "description": description,
        "source_location": None,
        "status": status,
        "evidence": evidence,
        "critical": critical,
    }


def _infer_pii_categories(ir: IR) -> list[str]:
    names = [n.lower() for n in [*ir.inputs.keys(), *ir.outputs.keys()]]
    categories: list[str] = []
    for n in names:
        for hint in _PII_HINTS:
            if hint in n and hint not in categories:
                categories.append(hint)
    return sorted(categories)


def derive_legal_compliance_metadata(
    ir: IR,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []

    preserves: list[str] = []
    constraints = {c.lower().strip() for c in ir.constraints}

    has_no_pii_logs = "no pii in logs" in constraints
    has_consent_required = "consent required" in constraints
    has_retention_limited = "retention_limited" in constraints
    has_lawful_basis = "lawful_basis_required" in constraints
    has_purpose_limited = "purpose_limited" in constraints

    for idx, (key, op, value) in enumerate(ir.preserve_rules, start=1):
        preserve_text = key.strip() if not op else f"{key.strip()} {op} {value.strip()}"
        key_lower = key.strip().lower()
        if key_lower in _ALLOWED_PRESERVES:
            preserves.append(key_lower)
            obligations.append(
                _obligation(
                    f"legal_compliance.preserve.{idx}",
                    f"preserve `{key}` captured",
                    "satisfied",
                    preserve_text,
                    critical=True if key_lower == "gdpr compliance" else False,
                )
            )
        else:
            obligations.append(
                _obligation(
                    f"legal_compliance.preserve.{idx}",
                    f"preserve `{key}` mapped to legal/compliance surface",
                    "unknown",
                    preserve_text,
                    critical=False,
                )
            )

    if "gdpr compliance" not in preserves:
        issues.append(
            {
                "issue_id": "legal_compliance.gdpr.missing",
                "severity": "medium",
                "message": "legal_compliance profile recommends explicit `preserve: GDPR compliance`",
            }
        )

    pii_categories = _infer_pii_categories(ir)
    pii_taint_summary = {
        "pii_categories_detected": pii_categories,
        "pii_sensitive_bindings": sorted([n for n in [*ir.inputs.keys(), *ir.outputs.keys()] if any(h in n.lower() for h in _PII_HINTS)]),
        "taint_class": "pii_sensitive" if pii_categories else "none_detected",
        "logging_constraint_no_pii": has_no_pii_logs,
    }

    audit_trail_metadata = {
        "auditability_preserved": "auditability" in preserves,
        "retention_limited": has_retention_limited,
        "consent_required": has_consent_required,
        "lawful_basis_required": has_lawful_basis,
        "manual_review_required": True,
    }

    obligations.extend(
        [
            _obligation(
                "legal_compliance.constraint.no_pii_in_logs",
                "constraint includes `no PII in logs`",
                "satisfied" if has_no_pii_logs else "unknown",
                "constraint declared" if has_no_pii_logs else "constraint not declared",
                critical=True,
            ),
            _obligation(
                "legal_compliance.constraint.consent_required",
                "constraint includes `consent required`",
                "satisfied" if has_consent_required else "unknown",
                "constraint declared" if has_consent_required else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "legal_compliance.constraint.retention_limited",
                "constraint includes `retention_limited`",
                "satisfied" if has_retention_limited else "unknown",
                "constraint declared" if has_retention_limited else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "legal_compliance.constraint.lawful_basis_required",
                "constraint includes `lawful_basis_required`",
                "satisfied" if has_lawful_basis else "unknown",
                "constraint declared" if has_lawful_basis else "constraint not declared",
                critical=False,
            ),
        ]
    )

    if pii_categories and not has_no_pii_logs:
        issues.append(
            {
                "issue_id": "legal_compliance.pii_logging.guard_missing",
                "severity": "high",
                "message": "PII-like fields detected but `constraint: no PII in logs` is not declared",
            }
        )

    summary = {
        "frameworks": ["GDPR"] if "gdpr compliance" in preserves else [],
        "preserves": sorted(set(preserves)),
        "has_no_pii_in_logs_constraint": has_no_pii_logs,
        "has_consent_required_constraint": has_consent_required,
        "has_retention_limited_constraint": has_retention_limited,
        "has_lawful_basis_required_constraint": has_lawful_basis,
        "has_purpose_limited_constraint": has_purpose_limited,
    }

    target_metadata = {
        "emit_target": ir.emit_target,
        "policy_scope": "data_pipeline",
        "policy_obligation_count": len(obligations),
        "manual_legal_review_required": True,
        "compliance_stub_level": "phase-7.3",
    }

    return (
        summary,
        sorted(issues, key=lambda r: str(r.get("issue_id", ""))),
        sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))),
        target_metadata,
        pii_taint_summary,
        audit_trail_metadata,
    )


def evaluate_legal_generated_artifact(ir: IR, generated_code: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []

    parsed: dict[str, object] | None = None
    try:
        parsed = json.loads(generated_code)
    except Exception:
        parsed = None

    if parsed is None:
        issues.append(
            {
                "issue_id": "legal_compliance.codegen.parse",
                "severity": "high",
                "message": "compliance_report artifact should be deterministic JSON",
            }
        )
        obligations.append(
            _obligation(
                "legal_compliance.codegen.json_format",
                "generated compliance_report should be valid JSON",
                "violated",
                "artifact is not parseable JSON",
                critical=True,
            )
        )
        return issues, obligations

    lower_constraints = {c.lower().strip() for c in ir.constraints}
    logging = parsed.get("logging_findings", {}) if isinstance(parsed, dict) else {}
    pii_in_logs = bool(logging.get("pii_in_logs_detected", False)) if isinstance(logging, dict) else False

    if "no pii in logs" in lower_constraints:
        status = "violated" if pii_in_logs else "satisfied"
        if status == "violated":
            issues.append(
                {
                    "issue_id": "legal_compliance.codegen.no_pii_logs.violation",
                    "severity": "high",
                    "message": "compliance artifact indicates PII in logs while `no PII in logs` is required",
                }
            )
        obligations.append(
            _obligation(
                "legal_compliance.codegen.no_pii_in_logs",
                "generated compliance report should not indicate PII in logs",
                status,
                "logging findings reviewed",
                critical=True,
            )
        )

    controls = parsed.get("controls", {}) if isinstance(parsed, dict) else {}
    controls = controls if isinstance(controls, dict) else {}
    for key, obligation_id in [
        ("consent required", "legal_compliance.codegen.consent_required"),
        ("retention_limited", "legal_compliance.codegen.retention_limited"),
        ("lawful_basis_required", "legal_compliance.codegen.lawful_basis_required"),
    ]:
        if key in lower_constraints:
            declared = bool(controls.get(key.replace(" ", "_"), False))
            obligations.append(
                _obligation(
                    obligation_id,
                    f"generated compliance report should map `{key}` control",
                    "satisfied" if declared else "unknown",
                    "control marker found" if declared else "control marker missing",
                    critical=False,
                )
            )

    return (
        sorted(issues, key=lambda r: str(r.get("issue_id", ""))),
        sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))),
    )
