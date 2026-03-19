"""Hardware intent analysis and obligation helpers (Phase 7.1)."""

from __future__ import annotations

import re

from .ir import IR


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
                    {
                        "obligation_id": f"hardware.timing.{idx}",
                        "category": "hardware",
                        "description": "timing preserve rule must be parseable in ns",
                        "source_location": None,
                        "status": "violated",
                        "evidence": f"unparseable timing literal `{value}`",
                        "critical": True,
                    }
                )
                continue
            timing_rules.append({"operator": op, "target_ns": ns})
            obligations.append(
                {
                    "obligation_id": f"hardware.timing.{idx}",
                    "category": "hardware",
                    "description": "timing preserve rule captured",
                    "source_location": None,
                    "status": "satisfied",
                    "evidence": f"timing {op} {ns}ns",
                    "critical": True,
                }
            )
        if k == "latency_cycles":
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
                {
                    "obligation_id": f"hardware.latency_cycles.{idx}",
                    "category": "hardware",
                    "description": "latency_cycles preserve rule captured",
                    "source_location": None,
                    "status": status,
                    "evidence": f"latency_cycles {op} {value}",
                    "critical": False,
                }
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
            {
                "obligation_id": "hardware.constraint.no_combinational_loops",
                "category": "hardware",
                "description": "constraint includes `no combinational loops`",
                "source_location": None,
                "status": "satisfied" if has_no_comb_loops else "unknown",
                "evidence": "constraint declared" if has_no_comb_loops else "constraint not declared",
                "critical": True,
            },
            {
                "obligation_id": "hardware.constraint.synchronous",
                "category": "hardware",
                "description": "constraint includes `synchronous`",
                "source_location": None,
                "status": "satisfied" if has_synchronous else "unknown",
                "evidence": "constraint declared" if has_synchronous else "constraint not declared",
                "critical": False,
            },
            {
                "obligation_id": "hardware.constraint.deterministic",
                "category": "hardware",
                "description": "constraint includes `deterministic`",
                "source_location": None,
                "status": "satisfied" if has_deterministic else "unknown",
                "evidence": "constraint declared" if has_deterministic else "constraint not declared",
                "critical": False,
            },
        ]
    )

    summary = {
        "timing_rules": timing_rules,
        "latency_cycle_rules": latency_rules,
        "has_no_combinational_loops_constraint": has_no_comb_loops,
        "has_synchronous_constraint": has_synchronous,
        "has_deterministic_constraint": has_deterministic,
    }
    target_meta = {
        "emit_target": ir.emit_target,
        "timing_rule_count": len(timing_rules),
        "latency_rule_count": len(latency_rules),
        "rtl_stub_level": "phase-7.1",
    }
    return summary, sorted(issues, key=lambda r: str(r.get("issue_id", ""))), sorted(obligations, key=lambda r: str(r.get("obligation_id", ""))), target_meta



def evaluate_hardware_generated_code(ir: IR, generated_code: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []
    code = generated_code.lower()

    has_clocked_block = any(tok in code for tok in ["rising_edge", "always_ff", "posedge"]) 
    has_self_assign_loop = bool(re.search(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(<=|=)\s*\1\b", code))

    requires_no_loops = any("no combinational loops" in c.lower() for c in ir.constraints)
    if requires_no_loops:
        if has_self_assign_loop:
            issues.append(
                {
                    "issue_id": "hardware.combinational_loop.risk",
                    "severity": "high",
                    "message": "potential self-referential assignment pattern detected",
                }
            )
            status = "violated"
            evidence = "self-referential assignment pattern detected"
        else:
            status = "satisfied"
            evidence = "no simple self-referential assignment pattern detected"
        obligations.append(
            {
                "obligation_id": "hardware.codegen.no_combinational_loops",
                "category": "hardware",
                "description": "generated RTL should avoid simple combinational loop patterns",
                "source_location": None,
                "status": status,
                "evidence": evidence,
                "critical": True,
            }
        )

    requires_sync = any("synchronous" in c.lower() for c in ir.constraints)
    if requires_sync:
        obligations.append(
            {
                "obligation_id": "hardware.codegen.synchronous",
                "category": "hardware",
                "description": "generated RTL should include a clocked construct",
                "source_location": None,
                "status": "satisfied" if has_clocked_block else "unknown",
                "evidence": "clocked block marker found" if has_clocked_block else "clocked construct marker not found",
                "critical": False,
            }
        )

    return sorted(issues, key=lambda r: str(r.get("issue_id", ""))), sorted(obligations, key=lambda r: str(r.get("obligation_id", "")))
