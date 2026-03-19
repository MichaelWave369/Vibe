"""Scientific simulation intent analysis and obligation helpers (Phase 7.2)."""

from __future__ import annotations

import re

from .ir import IR


_ALLOWED_INVARIANTS = {
    "conservation of energy",
    "conservation of mass",
    "stable_time_step",
    "monotonic entropy",
}


_BOUNDED_ERROR_OPS = {"<", "<="}


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
        "category": "scientific_simulation",
        "description": description,
        "source_location": None,
        "status": status,
        "evidence": evidence,
        "critical": critical,
    }


def _parse_bounded_error(value: str) -> float | None:
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]+)?\s*", value)
    if not m:
        return None
    return float(m.group(1))


def derive_scientific_simulation_metadata(
    ir: IR,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []

    invariants: list[str] = []
    bounded_error_rules: list[dict[str, object]] = []

    constraints_lower = {c.lower().strip() for c in ir.constraints}
    has_reproducible = "reproducible" in constraints_lower
    has_seeded_rng = "seeded_rng" in constraints_lower
    has_deterministic_fp = "deterministic_fp" in constraints_lower
    has_fixed_precision = "fixed_precision" in constraints_lower

    for idx, (key, op, value) in enumerate(ir.preserve_rules, start=1):
        normalized = f"{key.strip()} {value.strip()}" if op == "" else f"{key.strip()} {op} {value.strip()}"
        key_lower = key.strip().lower()

        if key_lower == "bounded_error":
            if op not in _BOUNDED_ERROR_OPS:
                issues.append(
                    {
                        "issue_id": "scientific_simulation.bounded_error.operator",
                        "severity": "high",
                        "message": f"bounded_error expects one of {_BOUNDED_ERROR_OPS}, got `{op}`",
                    }
                )
                obligations.append(
                    _obligation(
                        f"scientific_simulation.bounded_error.{idx}",
                        "bounded_error preserve must use supported operator",
                        "violated",
                        f"unsupported operator `{op}`",
                        critical=True,
                    )
                )
                continue
            parsed = _parse_bounded_error(value)
            if parsed is None:
                issues.append(
                    {
                        "issue_id": "scientific_simulation.bounded_error.parse",
                        "severity": "high",
                        "message": f"bounded_error preserve must be numeric literal, got `{value}`",
                    }
                )
                obligations.append(
                    _obligation(
                        f"scientific_simulation.bounded_error.{idx}",
                        "bounded_error preserve must be parseable",
                        "violated",
                        f"unparseable bounded_error value `{value}`",
                        critical=True,
                    )
                )
                continue
            bounded_error_rules.append({"operator": op, "threshold": parsed})
            obligations.append(
                _obligation(
                    f"scientific_simulation.bounded_error.{idx}",
                    "bounded_error preserve captured",
                    "satisfied",
                    f"bounded_error {op} {value}",
                    critical=True,
                )
            )
            continue

        if key_lower in _ALLOWED_INVARIANTS:
            invariants.append(key_lower)
            obligations.append(
                _obligation(
                    f"scientific_simulation.invariant.{idx}",
                    f"invariant preserve `{key}` captured",
                    "satisfied",
                    normalized,
                    critical=True,
                )
            )
            continue

        obligations.append(
            _obligation(
                f"scientific_simulation.preserve.{idx}",
                f"preserve `{key}` mapped to simulation contract surface",
                "unknown",
                normalized,
                critical=False,
            )
        )

    if not invariants:
        issues.append(
            {
                "issue_id": "scientific_simulation.invariant.missing",
                "severity": "medium",
                "message": "scientific_simulation profile recommends at least one explicit invariant preserve",
            }
        )

    if has_seeded_rng and not has_reproducible:
        issues.append(
            {
                "issue_id": "scientific_simulation.reproducibility.partial",
                "severity": "medium",
                "message": "seeded_rng declared without `reproducible` constraint",
            }
        )

    obligations.extend(
        [
            _obligation(
                "scientific_simulation.constraint.reproducible",
                "constraint includes `reproducible`",
                "satisfied" if has_reproducible else "unknown",
                "constraint declared" if has_reproducible else "constraint not declared",
                critical=True,
            ),
            _obligation(
                "scientific_simulation.constraint.seeded_rng",
                "constraint includes `seeded_rng`",
                "satisfied" if has_seeded_rng else "unknown",
                "constraint declared" if has_seeded_rng else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "scientific_simulation.constraint.deterministic_fp",
                "constraint includes `deterministic_fp`",
                "satisfied" if has_deterministic_fp else "unknown",
                "constraint declared" if has_deterministic_fp else "constraint not declared",
                critical=False,
            ),
        ]
    )

    summary = {
        "invariants": sorted(set(invariants)),
        "bounded_error_rules": bounded_error_rules,
        "has_stable_time_step": "stable_time_step" in set(invariants),
        "has_reproducible_constraint": has_reproducible,
        "has_seeded_rng_constraint": has_seeded_rng,
        "has_deterministic_fp_constraint": has_deterministic_fp,
        "has_fixed_precision_constraint": has_fixed_precision,
    }

    target_meta = {
        "emit_target": ir.emit_target,
        "invariant_count": len(set(invariants)),
        "bounded_error_rule_count": len(bounded_error_rules),
        "reproducibility_mode": "strict" if has_reproducible and has_seeded_rng and has_deterministic_fp else "declared",
        "numerics_notes": "metadata/structural checks only; no full numerical correctness proof",
        "simulation_stub_level": "phase-7.2",
    }

    return (
        summary,
        sorted(issues, key=lambda r: str(r.get("issue_id", ""))),
        sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))),
        target_meta,
    )


def evaluate_scientific_generated_code(ir: IR, generated_code: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []
    lower = generated_code.lower()

    requires_reproducible = any(c.lower().strip() == "reproducible" for c in ir.constraints)
    requires_seeded_rng = any(c.lower().strip() == "seeded_rng" for c in ir.constraints)
    requires_deterministic_fp = any(c.lower().strip() == "deterministic_fp" for c in ir.constraints)

    has_seed_hint = any(tok in lower for tok in ["seed", "mersennetwister", "random.seed", "rng"])
    has_fp_hint = any(tok in lower for tok in ["deterministic_fp", "float64", "round(", "setrounding"]) 

    if requires_seeded_rng:
        status = "satisfied" if has_seed_hint else "unknown"
        if status != "satisfied":
            issues.append(
                {
                    "issue_id": "scientific_simulation.codegen.seeded_rng.missing",
                    "severity": "medium",
                    "message": "seeded_rng requested but no seed/rng marker found in generated code",
                }
            )
        obligations.append(
            _obligation(
                "scientific_simulation.codegen.seeded_rng",
                "generated code should expose seeded RNG structure",
                status,
                "seed/rng marker found" if status == "satisfied" else "seed/rng marker not found",
                critical=False,
            )
        )

    if requires_deterministic_fp:
        obligations.append(
            _obligation(
                "scientific_simulation.codegen.deterministic_fp",
                "generated code should include deterministic floating-point markers",
                "satisfied" if has_fp_hint else "unknown",
                "deterministic FP marker found" if has_fp_hint else "deterministic FP marker not found",
                critical=False,
            )
        )

    if requires_reproducible:
        repro_status = "satisfied" if (not requires_seeded_rng or has_seed_hint) else "unknown"
        obligations.append(
            _obligation(
                "scientific_simulation.codegen.reproducible",
                "generated code should structurally support reproducible execution",
                repro_status,
                "reproducibility structure markers present" if repro_status == "satisfied" else "reproducibility markers incomplete",
                critical=True,
            )
        )

    return (
        sorted(issues, key=lambda r: str(r.get("issue_id", ""))),
        sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))),
    )
