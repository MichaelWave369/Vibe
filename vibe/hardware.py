"""Hardware intent analysis and obligation helpers (Phase 7.1)."""

from __future__ import annotations

import re

from .ir import IR

_TIMING_OPERATORS = {"<", "<="}
_LATENCY_OPERATORS = {"<", "<=", "="}


def _parse_timing_ns(value: str) -> float | None:
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*ns\s*", value.lower())
    if not m:
        return None
    return float(m.group(1))


def _parse_latency_cycles(value: str) -> int | None:
    m = re.fullmatch(r"\s*([0-9]+)\s*", value)
    if not m:
        return None
    return int(m.group(1))


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
        "category": "hardware",
        "description": description,
        "source_location": None,
        "status": status,
        "evidence": evidence,
        "critical": critical,
    }


def derive_hardware_metadata(ir: IR) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    timing_rules: list[dict[str, object]] = []
    latency_rules: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []

    constraint_set = {c.lower() for c in ir.constraints}
    has_no_comb_loops = any("no combinational loops" in c for c in constraint_set)
    has_synchronous = any("synchronous" in c for c in constraint_set)
    has_deterministic = any("deterministic" in c for c in constraint_set)

    for idx, (key, op, value) in enumerate(ir.preserve_rules, start=1):
        k = key.lower().strip()
        if k == "timing":
            if op not in _TIMING_OPERATORS:
                issues.append(
                    {
                        "issue_id": "hardware.timing.operator",
                        "severity": "high",
                        "message": f"timing preserve expects one of {_TIMING_OPERATORS}, got `{op}`",
                    }
                )
                obligations.append(
                    _obligation(
                        f"hardware.timing.{idx}",
                        "timing preserve rule must use supported operator",
                        "violated",
                        f"unsupported operator `{op}`",
                        critical=True,
                    )
                )
                continue
            ns = _parse_timing_ns(value)
            if ns is None:
                issues.append(
                    {
                        "issue_id": "hardware.timing.parse",
                        "severity": "high",
                        "message": f"hardware timing preserve expects ns literal, got `{value}`",
                    }
                )
                obligations.append(
                    _obligation(
                        f"hardware.timing.{idx}",
                        "timing preserve rule must be parseable in ns",
                        "violated",
                        f"unparseable timing literal `{value}`",
                        critical=True,
                    )
                )
                continue
            timing_rules.append({"operator": op, "target_ns": ns})
            obligations.append(
                _obligation(
                    f"hardware.timing.{idx}",
                    "timing preserve rule captured",
                    "satisfied",
                    f"timing {op} {ns}ns",
                    critical=True,
                )
            )
        if k == "latency_cycles":
            if op not in _LATENCY_OPERATORS:
                issues.append(
                    {
                        "issue_id": "hardware.latency_cycles.operator",
                        "severity": "medium",
                        "message": f"latency_cycles preserve expects one of {_LATENCY_OPERATORS}, got `{op}`",
                    }
                )
                obligations.append(
                    _obligation(
                        f"hardware.latency_cycles.{idx}",
                        "latency_cycles preserve rule must use supported operator",
                        "violated",
                        f"unsupported operator `{op}`",
                        critical=False,
                    )
                )
                continue
            cycles = _parse_latency_cycles(value)
            if cycles is None:
                issues.append(
                    {
                        "issue_id": "hardware.latency_cycles.parse",
                        "severity": "medium",
                        "message": f"latency_cycles preserve expects integer literal, got `{value}`",
                    }
                )
                status = "unknown"
            else:
                latency_rules.append({"operator": op, "target_cycles": cycles})
                status = "satisfied"
            obligations.append(
                _obligation(
                    f"hardware.latency_cycles.{idx}",
                    "latency_cycles preserve rule captured",
                    status,
                    f"latency_cycles {op} {value}",
                    critical=False,
                )
            )

    if not timing_rules:
        issues.append(
            {
                "issue_id": "hardware.timing.missing",
                "severity": "medium",
                "message": "hardware profile recommends explicit `preserve: timing < Nns` rule",
            }
        )

    obligations.extend(
        [
            _obligation(
                "hardware.constraint.no_combinational_loops",
                "constraint includes `no combinational loops`",
                "satisfied" if has_no_comb_loops else "unknown",
                "constraint declared" if has_no_comb_loops else "constraint not declared",
                critical=True,
            ),
            _obligation(
                "hardware.constraint.synchronous",
                "constraint includes `synchronous`",
                "satisfied" if has_synchronous else "unknown",
                "constraint declared" if has_synchronous else "constraint not declared",
                critical=False,
            ),
            _obligation(
                "hardware.constraint.deterministic",
                "constraint includes `deterministic`",
                "satisfied" if has_deterministic else "unknown",
                "constraint declared" if has_deterministic else "constraint not declared",
                critical=False,
            ),
        ]
    )

    summary = {
        "timing_rules": timing_rules,
        "latency_cycle_rules": latency_rules,
        "has_no_combinational_loops_constraint": has_no_comb_loops,
        "has_synchronous_constraint": has_synchronous,
        "has_deterministic_constraint": has_deterministic,
    }
    # Declarative mapping only; this is not a synthesis/P&R timing proof.
    timing_budget_ns = None
    if timing_rules:
        timing_budget_ns = min(float(rule["target_ns"]) for rule in timing_rules)
    target_meta = {
        "emit_target": ir.emit_target,
        "timing_rule_count": len(timing_rules),
        "latency_rule_count": len(latency_rules),
        "timing_budget_ns": timing_budget_ns,
        "rtl_stub_level": "phase-7.1",
    }
    return summary, sorted(issues, key=lambda r: str(r.get("issue_id", ""))), sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))), target_meta



def evaluate_hardware_generated_code(ir: IR, generated_code: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []
    code = generated_code.lower()

    has_clocked_block = any(tok in code for tok in ["rising_edge", "always_ff", "posedge"]) 
    has_self_assign_loop = bool(re.search(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(<=|=)\s*\1\b", code))
    has_cont_assign_self_loop = bool(re.search(r"\bassign\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\1\b", code))

    requires_no_loops = any("no combinational loops" in c.lower() for c in ir.constraints)
    if requires_no_loops:
        if has_self_assign_loop or has_cont_assign_self_loop:
            issues.append(
                {
                    "issue_id": "hardware.combinational_loop.risk",
                    "severity": "high",
                    "message": "potential self-referential assignment or continuous assignment loop pattern detected",
                }
            )
            status = "violated"
            evidence = "self-referential assignment pattern detected"
        else:
            status = "satisfied"
            evidence = "no simple self-referential assignment pattern detected"
        obligations.append(
            _obligation(
                "hardware.codegen.no_combinational_loops",
                "generated RTL should avoid simple combinational loop patterns",
                status,
                evidence,
                critical=True,
            )
        )

    requires_sync = any("synchronous" in c.lower() for c in ir.constraints)
    if requires_sync:
        obligations.append(
            _obligation(
                "hardware.codegen.synchronous",
                "generated RTL should include a clocked construct",
                "satisfied" if has_clocked_block else "unknown",
                "clocked block marker found" if has_clocked_block else "clocked construct marker not found",
                critical=False,
            )
        )

    return sorted(issues, key=lambda r: str(r.get("issue_id", ""))), sorted(obligations, key=lambda r: str(r.get("obligation_id", "")))
