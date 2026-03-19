"""Genomics intent analysis and obligation helpers (Phase 7.4)."""

from __future__ import annotations

import re

from .ir import IR


_ALLOWED_PRESERVES = {
    "reproducibility of differential expression results",
    "reproducible workflow",
    "provenance retained",
    "stable normalization method",
}


_METADATA_HINTS = ("patient", "subject", "donor", "name", "dob", "mrn", "id", "metadata")
_IDENTIFIABLE_MARKERS = ("patient", "name", "dob", "mrn", "ssn", "address", "phone", "email")


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
        "category": "genomics",
        "description": description,
        "source_location": None,
        "status": status,
        "evidence": evidence,
        "critical": critical,
    }


def _sensitive_bindings(ir: IR) -> list[str]:
    names = [*ir.inputs.keys(), *ir.outputs.keys()]
    return sorted([n for n in names if any(h in n.lower() for h in _METADATA_HINTS)])


def derive_genomics_metadata(
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

    has_no_patient_meta = "no patient-identifiable metadata in outputs" in constraints
    has_deidentify = "deidentify sample metadata" in constraints
    has_deterministic_order = "deterministic sample ordering" in constraints
    has_fixed_ref = "fixed reference version" in constraints
    has_batch_leak_block = "no uncontrolled batch-effect metadata leakage" in constraints

    for idx, (key, op, value) in enumerate(ir.preserve_rules, start=1):
        preserve_text = key.strip() if not op else f"{key.strip()} {op} {value.strip()}"
        key_lower = key.strip().lower()
        if key_lower in _ALLOWED_PRESERVES:
            preserves.append(key_lower)
            obligations.append(
                _obligation(
                    f"genomics.preserve.{idx}",
                    f"preserve `{key}` captured",
                    "satisfied",
                    preserve_text,
                    critical=True if "reproducibility" in key_lower else False,
                )
            )
        else:
            obligations.append(
                _obligation(
                    f"genomics.preserve.{idx}",
                    f"preserve `{key}` mapped to genomics contract surface",
                    "unknown",
                    preserve_text,
                    critical=False,
                )
            )

    has_stable_normalization = "stable normalization method" in preserves

    if "reproducibility of differential expression results" not in preserves:
        issues.append(
            {
                "issue_id": "genomics.reproducibility.dex.missing",
                "severity": "medium",
                "message": "genomics profile recommends `preserve: reproducibility of differential expression results`",
            }
        )

    sensitive = _sensitive_bindings(ir)
    metadata_privacy_summary = {
        "sensitive_bindings": sensitive,
        "has_no_patient_identifiable_metadata_constraint": has_no_patient_meta,
        "has_deidentify_sample_metadata_constraint": has_deidentify,
        "potentially_identifiable_outputs": sorted(
            [name for name in ir.outputs if any(tok in name.lower() for tok in _IDENTIFIABLE_MARKERS)]
        ),
        "privacy_mode": "guarded" if has_no_patient_meta and has_deidentify else "declared",
    }

    workflow_provenance_metadata = {
        "provenance_retained": "provenance retained" in preserves,
        "deterministic_sample_ordering": has_deterministic_order,
        "fixed_reference_version": has_fixed_ref,
        "stable_normalization_method": has_stable_normalization,
        "batch_effect_metadata_leakage_blocked": has_batch_leak_block,
        "workflow_stub_level": "phase-7.4",
    }

    obligations.extend(
        [
            _obligation(
                "genomics.constraint.no_patient_identifiable_metadata",
                "constraint includes `no patient-identifiable metadata in outputs`",
                "satisfied" if has_no_patient_meta else "unknown",
                "constraint declared" if has_no_patient_meta else "constraint not declared",
                critical=True,
            ),
            _obligation(
                "genomics.constraint.deidentify_sample_metadata",
                "constraint includes `deidentify sample metadata`",
                "satisfied" if has_deidentify else "unknown",
                "constraint declared" if has_deidentify else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "genomics.constraint.deterministic_sample_ordering",
                "constraint includes `deterministic sample ordering`",
                "satisfied" if has_deterministic_order else "unknown",
                "constraint declared" if has_deterministic_order else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "genomics.constraint.fixed_reference_version",
                "constraint includes `fixed reference version`",
                "satisfied" if has_fixed_ref else "unknown",
                "constraint declared" if has_fixed_ref else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "genomics.constraint.no_uncontrolled_batch_effect_metadata_leakage",
                "constraint includes `no uncontrolled batch-effect metadata leakage` when declared",
                "satisfied" if has_batch_leak_block else "unknown",
                "constraint declared" if has_batch_leak_block else "constraint not declared",
                critical=False,
            ),
        ]
    )

    if sensitive and not has_no_patient_meta:
        issues.append(
            {
                "issue_id": "genomics.privacy.guard_missing",
                "severity": "high",
                "message": "sensitive sample/patient-like fields detected without `no patient-identifiable metadata in outputs`",
            }
        )

    summary = {
        "preserves": sorted(set(preserves)),
        "reproducibility_preserved": any("reproducibility" in p for p in preserves),
        "provenance_retained": "provenance retained" in preserves,
        "stable_normalization_method_preserved": has_stable_normalization,
        "has_no_patient_identifiable_metadata_constraint": has_no_patient_meta,
        "has_deidentify_sample_metadata_constraint": has_deidentify,
        "has_deterministic_sample_ordering_constraint": has_deterministic_order,
        "has_fixed_reference_version_constraint": has_fixed_ref,
        "has_batch_effect_metadata_leakage_constraint": has_batch_leak_block,
    }

    target_metadata = {
        "emit_target": ir.emit_target,
        "workflow_profile": "differential_expression",
        "obligation_count": len(obligations),
        "manual_bioinformatics_review_required": True,
        "genomics_stub_level": "phase-7.4",
    }

    return (
        summary,
        sorted(issues, key=lambda r: str(r.get("issue_id", ""))),
        sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))),
        target_metadata,
        metadata_privacy_summary,
        workflow_provenance_metadata,
    )


def evaluate_genomics_generated_code(ir: IR, generated_code: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []
    lower = generated_code.lower()

    req_no_patient_meta = any(c.lower().strip() == "no patient-identifiable metadata in outputs" for c in ir.constraints)
    req_deidentify = any(c.lower().strip() == "deidentify sample metadata" for c in ir.constraints)
    req_deterministic_order = any(c.lower().strip() == "deterministic sample ordering" for c in ir.constraints)
    req_fixed_ref = any(c.lower().strip() == "fixed reference version" for c in ir.constraints)
    req_batch_leak_block = any(
        c.lower().strip() == "no uncontrolled batch-effect metadata leakage" for c in ir.constraints
    )

    has_deid_marker = any(tok in lower for tok in ["deidentify", "anonym", "pseudonym"])
    has_order_marker = any(tok in lower for tok in ["sorted(", "sort", "deterministic sample ordering"])
    has_ref_marker = bool(re.search(r"reference(_version|_build)?", lower)) or "fixed reference version" in lower
    has_batch_control_marker = any(tok in lower for tok in ["batch_effect", "batch effect", "combat", "blocked_batch"])

    if req_no_patient_meta:
        leaked_marker = "patient" in lower and "deidentify" not in lower
        status = "violated" if leaked_marker else "satisfied"
        if status == "violated":
            issues.append(
                {
                    "issue_id": "genomics.codegen.patient_metadata.leak_risk",
                    "severity": "high",
                    "message": "potential patient-identifiable metadata marker found without deidentification marker",
                }
            )
        obligations.append(
            _obligation(
                "genomics.codegen.no_patient_identifiable_metadata",
                "generated workflow should avoid patient-identifiable metadata exposure",
                status,
                "workflow metadata markers inspected",
                critical=True,
            )
        )

    if req_deidentify:
        obligations.append(
            _obligation(
                "genomics.codegen.deidentify_sample_metadata",
                "generated workflow should include deidentification handling markers",
                "satisfied" if has_deid_marker else "unknown",
                "deidentification marker found" if has_deid_marker else "deidentification marker not found",
                critical=False,
            )
        )

    if req_deterministic_order:
        obligations.append(
            _obligation(
                "genomics.codegen.deterministic_sample_ordering",
                "generated workflow should include deterministic ordering markers",
                "satisfied" if has_order_marker else "unknown",
                "ordering marker found" if has_order_marker else "ordering marker not found",
                critical=False,
            )
        )

    if req_fixed_ref:
        obligations.append(
            _obligation(
                "genomics.codegen.fixed_reference_version",
                "generated workflow should include fixed reference marker",
                "satisfied" if has_ref_marker else "unknown",
                "reference marker found" if has_ref_marker else "reference marker not found",
                critical=False,
            )
        )

    if req_batch_leak_block:
        obligations.append(
            _obligation(
                "genomics.codegen.no_uncontrolled_batch_effect_metadata_leakage",
                "generated workflow should include batch-effect leakage control marker",
                "satisfied" if has_batch_control_marker else "unknown",
                "batch-effect control marker found"
                if has_batch_control_marker
                else "batch-effect control marker not found",
                critical=False,
            )
        )

    return (
        sorted(issues, key=lambda r: str(r.get("issue_id", ""))),
        sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))),
    )
