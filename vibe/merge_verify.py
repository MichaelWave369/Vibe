"""Three-way merge + verification for Vibe specs (Phase 2A/2B)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .emitter import emit_code
from .ir import IR, ast_to_ir
from .parser import parse_source
from .verifier import verify

MERGE_VERIFY_SCHEMA_VERSION = "v1"
REGRESSION_EVIDENCE_DEFAULT_TOP_N = 5
REGRESSION_EVIDENCE_MIN_TOP_N = 1
REGRESSION_EVIDENCE_MAX_TOP_N = 20


@dataclass(slots=True)
class MergeConflict:
    address: str
    conflict_type: str
    base_value: object
    left_value: object
    right_value: object
    message: str
    severity: str = "high"


@dataclass(slots=True)
class MergeVerifyResult:
    merge_status: str
    conflicts: list[MergeConflict]
    merged_text: str | None
    verification: dict[str, object] | None
    verification_context: dict[str, object] | None = None
    intent_conflicts: list[dict[str, object]] | None = None
    regression_evidence: dict[str, object] | None = None
    policy_evaluation: dict[str, object] | None = None
    error: str | None = None


def _semantic_address(intent_name: str, section: str, key: str | None = None) -> str:
    if key is None:
        return f"intent::{intent_name}::{section}"
    return f"intent::{intent_name}::{section}::{key}"


def _merge_scalar(
    *,
    intent_name: str,
    section: str,
    key: str | None,
    base: object,
    left: object,
    right: object,
    conflict_type: str,
) -> tuple[object | None, MergeConflict | None]:
    if left == right:
        return left, None
    if left == base:
        return right, None
    if right == base:
        return left, None
    address = _semantic_address(intent_name, section, key)
    return None, MergeConflict(
        address=address,
        conflict_type=conflict_type,
        base_value=base,
        left_value=left,
        right_value=right,
        message=f"conflicting updates at {address}",
    )


def _merge_map(
    *,
    intent_name: str,
    section: str,
    base: dict[str, str],
    left: dict[str, str],
    right: dict[str, str],
    conflict_type: str,
) -> tuple[dict[str, str], list[MergeConflict]]:
    merged: dict[str, str] = {}
    conflicts: list[MergeConflict] = []
    for key in sorted(set(base) | set(left) | set(right)):
        b = base.get(key)
        l = left.get(key)
        r = right.get(key)
        chosen, conflict = _merge_scalar(
            intent_name=intent_name,
            section=section,
            key=key,
            base=b,
            left=l,
            right=r,
            conflict_type=conflict_type,
        )
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if chosen is not None:
            merged[key] = str(chosen)
    return merged, conflicts


def _merge_membership(
    *,
    intent_name: str,
    section: str,
    base: list[str],
    left: list[str],
    right: list[str],
    conflict_type: str,
) -> tuple[list[str], list[MergeConflict]]:
    merged: list[str] = []
    conflicts: list[MergeConflict] = []
    bset = set(base)
    lset = set(left)
    rset = set(right)
    for item in sorted(bset | lset | rset):
        b = item in bset
        l = item in lset
        r = item in rset
        chosen, conflict = _merge_scalar(
            intent_name=intent_name,
            section=section,
            key=item,
            base=b,
            left=l,
            right=r,
            conflict_type=conflict_type,
        )
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if bool(chosen):
            merged.append(item)
    return merged, conflicts


def _rules_to_map(rules: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
    return {k: (op, value) for k, op, value in rules}


def _merge_preserve(
    *,
    intent_name: str,
    base: list[tuple[str, str, str]],
    left: list[tuple[str, str, str]],
    right: list[tuple[str, str, str]],
) -> tuple[list[tuple[str, str, str]], list[MergeConflict]]:
    merged: list[tuple[str, str, str]] = []
    conflicts: list[MergeConflict] = []
    bmap = _rules_to_map(base)
    lmap = _rules_to_map(left)
    rmap = _rules_to_map(right)
    for key in sorted(set(bmap) | set(lmap) | set(rmap)):
        b = bmap.get(key)
        l = lmap.get(key)
        r = rmap.get(key)
        chosen, conflict = _merge_scalar(
            intent_name=intent_name,
            section="preserve",
            key=key,
            base=b,
            left=l,
            right=r,
            conflict_type="preserve_conflict",
        )
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if chosen is not None:
            op, value = chosen
            merged.append((key, op, value))
    return merged, conflicts


def _agents_by_name(ir: IR) -> dict[str, dict[str, object]]:
    return {str(a.get("name")): dict(a) for a in ir.agent_definitions}


def _merge_agents(*, intent_name: str, base_ir: IR, left_ir: IR, right_ir: IR) -> tuple[list[dict[str, object]], list[MergeConflict]]:
    base = _agents_by_name(base_ir)
    left = _agents_by_name(left_ir)
    right = _agents_by_name(right_ir)
    merged: list[dict[str, object]] = []
    conflicts: list[MergeConflict] = []
    for name in sorted(set(base) | set(left) | set(right)):
        chosen, conflict = _merge_scalar(
            intent_name=intent_name,
            section="agent",
            key=name,
            base=base.get(name),
            left=left.get(name),
            right=right.get(name),
            conflict_type="agent_conflict",
        )
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if chosen is not None:
            merged.append(dict(chosen))
    return merged, conflicts


def _render_agentora(agents: list[dict[str, object]]) -> list[str]:
    if not agents:
        return []
    lines = ["", "agentora {"]
    for agent in sorted(agents, key=lambda row: str(row.get("name", ""))):
        lines.append(f"  agent {agent.get('name')} {{")
        lines.append(f"    role: {json.dumps(str(agent.get('role', '')))}")
        lines.append(f"    tools: {json.dumps(list(agent.get('tools', [])))}")
        lines.append(f"    memory: {json.dumps(str(agent.get('memory', 'session')))}")
        lines.append(f"    intention: {json.dumps(str(agent.get('intention', '')))}")
        lines.append(f"    constraints: {json.dumps(list(agent.get('constraints', [])))}")
        lines.append(f"    preserve: {json.dumps(list(agent.get('preserve', [])))}")
        lines.append("  }")
    lines.append("}")
    return lines


def _render_agentception(agentception: dict[str, object]) -> list[str]:
    if not agentception:
        return []
    lines = ["", "agentception {"]
    lines.append(f"  enabled: {json.dumps(bool(agentception.get('enabled', False)))}")
    lines.append(f"  max.depth: {int(agentception.get('max_depth', 0))}")
    lines.append(f"  spawn.policy: {json.dumps(str(agentception.get('spawn_policy', '')))}")
    lines.append(f"  inherit.preserve: {json.dumps(bool(agentception.get('inherit_preserve', False)))}")
    lines.append(f"  inherit.constraints: {json.dumps(bool(agentception.get('inherit_constraints', False)))}")
    lines.append(f"  inherit.bridge: {json.dumps(bool(agentception.get('inherit_bridge', False)))}")
    lines.append(f"  merge.strategy: {json.dumps(str(agentception.get('merge_strategy', '')))}")
    lines.append(f"  stop.when: {json.dumps(str(agentception.get('stop_when', '')))}")
    lines.append("}")
    return lines


def _to_vibe_text(
    *,
    intent_name: str,
    goal: str,
    inputs: dict[str, str],
    outputs: dict[str, str],
    preserve_rules: list[tuple[str, str, str]],
    constraints: list[str],
    bridge_config: dict[str, str],
    emit_target: str,
    domain_profile: str,
    vibe_version: str | None,
    imports: list[str],
    modules: list[str],
    types: list[str],
    enums: list[str],
    interfaces: list[str],
    agents: list[dict[str, object]],
    agentception: dict[str, object],
) -> str:
    lines: list[str] = []
    if vibe_version:
        lines.append(f"vibe_version {vibe_version}")
    for item in sorted(imports):
        lines.append(f"import {item}")
    for item in sorted(modules):
        lines.append(f"module {item}")
    for item in sorted(types):
        lines.append(f"type {item}")
    for item in sorted(enums):
        lines.append(f"enum {item}")
    for item in sorted(interfaces):
        lines.append(f"interface {item}")
    if lines:
        lines.append("")
    if domain_profile and domain_profile != "general":
        lines.extend([f"domain {domain_profile}", ""])
    lines.append(f"intent {intent_name}:")
    lines.append(f"  goal: {json.dumps(goal)}")
    lines.append("  inputs:")
    for key in sorted(inputs):
        lines.append(f"    {key}: {inputs[key]}")
    lines.append("  outputs:")
    for key in sorted(outputs):
        lines.append(f"    {key}: {outputs[key]}")
    if preserve_rules:
        lines.append("")
        lines.append("preserve:")
        for key, op, value in preserve_rules:
            lines.append(f"  {key} {op} {value}")
    if constraints:
        lines.append("")
        lines.append("constraint:")
        for item in sorted(constraints):
            lines.append(f"  {item}")

    lines.extend(_render_agentora(agents))
    lines.extend(_render_agentception(agentception))

    if bridge_config:
        lines.append("")
        lines.append("bridge:")
        for key in sorted(bridge_config):
            lines.append(f"  {key} = {bridge_config[key]}")
    lines.append("")
    lines.append(f"emit {emit_target}")
    lines.append("")
    return "\n".join(lines)


def _verification_summary_for_ir(ir: IR) -> tuple[dict[str, object], object]:
    emitted, _ = emit_code(ir)
    result = verify(ir, emitted, use_calibration=False)
    obligations_total = len(result.obligations)
    obligations_satisfied = sum(1 for o in result.obligations if o.status == "satisfied")
    summary = {
        "passed": result.passed,
        "verdict": result.verdict,
        "bridge_score": result.bridge_score,
        "epsilon_post": result.epsilon_post,
        "measurement_ratio": result.measurement_ratio,
        "epsilon_floor": result.epsilon_floor,
        "measurement_safe_ratio": result.measurement_safe_ratio,
        "obligations_total": obligations_total,
        "obligations_satisfied": obligations_satisfied,
    }
    return summary, result


def _verification_summary(source_text: str) -> tuple[dict[str, object], IR, object]:
    ir = ast_to_ir(parse_source(source_text))
    summary, result = _verification_summary_for_ir(ir)
    return summary, ir, result


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _classify_intent_conflicts(
    *,
    base_ir: IR,
    merged_ir: IR,
    base_summary: dict[str, object],
    merged_summary: dict[str, object],
    merged_result: object,
) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    intent_name = merged_ir.intent_name
    base_floor = _maybe_float(base_ir.bridge_config.get("epsilon_floor"))
    merged_floor = _maybe_float(merged_ir.bridge_config.get("epsilon_floor"))
    if base_floor is not None and merged_floor is not None and merged_floor < base_floor:
        conflicts.append(
            {
                "address": _semantic_address(intent_name, "bridge", "epsilon_floor"),
                "conflict_type": "threshold_weakening",
                "message": f"epsilon_floor weakened from {base_floor} to {merged_floor}",
                "severity": "warning",
                "bridge_impact": merged_floor - base_floor,
            }
        )
    base_safe = _maybe_float(base_ir.bridge_config.get("measurement_safe_ratio"))
    merged_safe = _maybe_float(merged_ir.bridge_config.get("measurement_safe_ratio"))
    if base_safe is not None and merged_safe is not None and merged_safe < base_safe:
        conflicts.append(
            {
                "address": _semantic_address(intent_name, "bridge", "measurement_safe_ratio"),
                "conflict_type": "threshold_weakening",
                "message": f"measurement_safe_ratio weakened from {base_safe} to {merged_safe}",
                "severity": "warning",
                "bridge_impact": merged_safe - base_safe,
            }
        )

    base_bridge = float(base_summary["bridge_score"])
    merged_bridge = float(merged_summary["bridge_score"])
    if merged_bridge < base_bridge:
        conflicts.append(
            {
                "address": _semantic_address(intent_name, "bridge", "bridge_score"),
                "conflict_type": "bridge_regression",
                "message": f"bridge_score regressed from {base_bridge:.6f} to {merged_bridge:.6f}",
                "severity": "warning",
                "bridge_impact": merged_bridge - base_bridge,
            }
        )

    violated = [o for o in merged_result.obligations if o.status == "violated"]
    if violated:
        first = violated[0]
        conflict_type = "obligation_violation"
        if str(first.category) == "constraint":
            conflict_type = "constraint_regression"
        elif str(first.category) == "preserve":
            conflict_type = "preserve_regression"
        conflicts.append(
            {
                "address": first.source_location or first.obligation_id,
                "conflict_type": conflict_type,
                "message": first.description,
                "severity": "error" if first.critical else "warning",
                "bridge_impact": None,
            }
        )
    elif merged_summary.get("passed") is False:
        conflicts.append(
            {
                "address": _semantic_address(intent_name, "verification"),
                "conflict_type": "verification_regression",
                "message": "merged intent failed verification without directly classifiable violated obligations",
                "severity": "error",
                "bridge_impact": None,
            }
        )
    return conflicts


def _obligation_severity(*, critical: bool, status: str) -> str:
    if critical:
        return "error"
    if status == "violated":
        return "warning"
    if status == "unknown":
        return "advisory"
    return "info"


def _build_regression_evidence(
    *,
    merge_status: str,
    merged_result: object | None,
    requested_top_n: int | None = None,
    include_evidence: bool = False,
    unavailable_reason: str | None = None,
) -> dict[str, object]:
    requested = requested_top_n if requested_top_n is not None else REGRESSION_EVIDENCE_DEFAULT_TOP_N
    effective_top_n = max(REGRESSION_EVIDENCE_MIN_TOP_N, min(REGRESSION_EVIDENCE_MAX_TOP_N, int(requested)))
    selection_policy = {
        "default_top_n": REGRESSION_EVIDENCE_DEFAULT_TOP_N,
        "requested_top_n": int(requested),
        "effective_top_n": effective_top_n,
        "min_top_n": REGRESSION_EVIDENCE_MIN_TOP_N,
        "max_top_n": REGRESSION_EVIDENCE_MAX_TOP_N,
        "include_evidence_requested": bool(include_evidence),
        "include_evidence_effective": bool(include_evidence),
        "problem_statuses": ["violated", "unknown"],
        "ordering": [
            "severity_priority(desc)",
            "status_priority(violated>unknown)",
            "category(asc)",
            "id(asc)",
            "address(asc)",
        ],
    }
    if merge_status != "merged" or merged_result is None:
        return {
            "available": False,
            "reason": unavailable_reason or "merged_verification_not_available",
            "total_problem_obligations": 0,
            "shown_problem_obligations": 0,
            "status_counts": {},
            "severity_counts": {},
            "selection_policy": selection_policy,
            "top_problem_obligations": [],
        }

    status_priority = {"violated": 2, "unknown": 1}
    severity_priority = {"error": 3, "warning": 2, "advisory": 1, "info": 0}
    problems: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for o in merged_result.obligations:
        if o.status not in {"violated", "unknown"}:
            continue
        severity = _obligation_severity(critical=bool(o.critical), status=str(o.status))
        status_counts[o.status] = status_counts.get(o.status, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        row: dict[str, object] = {
            "id": o.obligation_id,
            "category": o.category,
            "address": o.source_location,
            "status": o.status,
            "severity": severity,
            "message": o.description,
        }
        if include_evidence and o.evidence:
            evidence_compact = " ".join(str(o.evidence).split())
            if evidence_compact:
                row["evidence_text"] = evidence_compact[:200]
        problems.append(row)
    problems_sorted = sorted(
        problems,
        key=lambda row: (
            -severity_priority.get(str(row["severity"]), 0),
            -status_priority.get(str(row["status"]), 0),
            str(row["category"]),
            str(row["id"]),
            str(row.get("address") or ""),
        ),
    )
    top = problems_sorted[:effective_top_n]
    return {
        "available": True,
        "reason": None,
        "total_problem_obligations": len(problems_sorted),
        "shown_problem_obligations": len(top),
        "status_counts": status_counts,
        "severity_counts": severity_counts,
        "selection_policy": selection_policy,
        "top_problem_obligations": top,
    }


def _build_policy_evaluation(
    *,
    merge_status: str,
    verification: dict[str, object] | None,
    intent_conflicts: list[dict[str, object]] | None,
    require_merged_bridge: float | None = None,
    fail_on_intent_conflicts: bool = False,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    if require_merged_bridge is not None:
        if merge_status == "merged" and verification is not None and verification.get("bridge_score") is not None:
            merged_bridge = float(verification["bridge_score"])
            passed = merged_bridge >= float(require_merged_bridge)
            checks.append(
                {
                    "policy_name": "require_merged_bridge",
                    "requested_value": float(require_merged_bridge),
                    "effective_value": merged_bridge,
                    "available": True,
                    "passed": passed,
                    "reason": "threshold_met" if passed else "threshold_not_met",
                }
            )
        else:
            checks.append(
                {
                    "policy_name": "require_merged_bridge",
                    "requested_value": float(require_merged_bridge),
                    "effective_value": None,
                    "available": False,
                    "passed": False,
                    "reason": "merged_verification_not_available",
                }
            )
    if fail_on_intent_conflicts:
        if merge_status == "merged":
            conflict_count = len(intent_conflicts or [])
            passed = conflict_count == 0
            checks.append(
                {
                    "policy_name": "fail_on_intent_conflicts",
                    "requested_value": True,
                    "effective_value": conflict_count,
                    "available": True,
                    "passed": passed,
                    "reason": "no_intent_conflicts" if passed else "intent_conflicts_present",
                }
            )
        else:
            checks.append(
                {
                    "policy_name": "fail_on_intent_conflicts",
                    "requested_value": True,
                    "effective_value": None,
                    "available": False,
                    "passed": False,
                    "reason": "merged_result_not_available",
                }
            )
    requested = bool(checks)
    available = True if not requested else all(bool(c.get("available")) for c in checks)
    passed = True if not requested else all(bool(c.get("passed")) for c in checks)
    return {
        "requested": requested,
        "available": available,
        "passed": passed,
        "checks": checks,
    }


def merge_verify(
    base_text: str,
    left_text: str,
    right_text: str,
    regression_top_n: int | None = None,
    regression_include_evidence: bool = False,
    require_merged_bridge: float | None = None,
    fail_on_intent_conflicts: bool = False,
) -> MergeVerifyResult:
    try:
        base_summary, base_ir, _ = _verification_summary(base_text)
        left_summary, left_ir, _ = _verification_summary(left_text)
        right_summary, right_ir, _ = _verification_summary(right_text)
    except Exception as exc:
        return MergeVerifyResult(
            merge_status="error",
            conflicts=[],
            merged_text=None,
            verification=None,
            verification_context={
                "requested": True,
                "available": False,
                "reason": str(exc),
                "base": None,
                "left": None,
                "right": None,
                "merged": None,
                "bridge_score_delta_vs_base": None,
            },
            intent_conflicts=[],
            regression_evidence=_build_regression_evidence(
                merge_status="error",
                merged_result=None,
                requested_top_n=regression_top_n,
                include_evidence=regression_include_evidence,
                unavailable_reason="merge_verify_input_error",
            ),
            policy_evaluation=_build_policy_evaluation(
                merge_status="error",
                verification=None,
                intent_conflicts=[],
                require_merged_bridge=require_merged_bridge,
                fail_on_intent_conflicts=fail_on_intent_conflicts,
            ),
            error=str(exc),
        )

    root_intent_name = base_ir.intent_name
    intent_name, c = _merge_scalar(
        intent_name=root_intent_name,
        section="intent",
        key="name",
        base=base_ir.intent_name,
        left=left_ir.intent_name,
        right=right_ir.intent_name,
        conflict_type="structural_conflict",
    )
    if intent_name is None:
        intent_name = root_intent_name

    conflicts: list[MergeConflict] = []
    if c:
        conflicts.append(c)

    goal, c = _merge_scalar(
        intent_name=str(intent_name),
        section="intent",
        key="goal",
        base=base_ir.goal,
        left=left_ir.goal,
        right=right_ir.goal,
        conflict_type="value_conflict",
    )
    if c:
        conflicts.append(c)
    emit_target, c = _merge_scalar(
        intent_name=str(intent_name),
        section="emit",
        key="target",
        base=base_ir.emit_target,
        left=left_ir.emit_target,
        right=right_ir.emit_target,
        conflict_type="value_conflict",
    )
    if c:
        conflicts.append(c)
    domain_profile, c = _merge_scalar(
        intent_name=str(intent_name),
        section="domain",
        key="profile",
        base=base_ir.domain_profile,
        left=left_ir.domain_profile,
        right=right_ir.domain_profile,
        conflict_type="structural_conflict",
    )
    if c:
        conflicts.append(c)
    vibe_version, c = _merge_scalar(
        intent_name=str(intent_name),
        section="vibe_version",
        key="value",
        base=base_ir.vibe_version,
        left=left_ir.vibe_version,
        right=right_ir.vibe_version,
        conflict_type="structural_conflict",
    )
    if c:
        conflicts.append(c)

    inputs, input_conflicts = _merge_map(
        intent_name=str(intent_name),
        section="input",
        base=base_ir.inputs,
        left=left_ir.inputs,
        right=right_ir.inputs,
        conflict_type="structural_conflict",
    )
    outputs, output_conflicts = _merge_map(
        intent_name=str(intent_name),
        section="output",
        base=base_ir.outputs,
        left=left_ir.outputs,
        right=right_ir.outputs,
        conflict_type="structural_conflict",
    )
    bridge, bridge_conflicts = _merge_map(
        intent_name=str(intent_name),
        section="bridge",
        base=base_ir.bridge_config,
        left=left_ir.bridge_config,
        right=right_ir.bridge_config,
        conflict_type="bridge_param_conflict",
    )
    constraints, constraint_conflicts = _merge_membership(
        intent_name=str(intent_name),
        section="constraint",
        base=base_ir.constraints,
        left=left_ir.constraints,
        right=right_ir.constraints,
        conflict_type="constraint_conflict",
    )
    preserve_rules, preserve_conflicts = _merge_preserve(
        intent_name=str(intent_name),
        base=base_ir.preserve_rules,
        left=left_ir.preserve_rules,
        right=right_ir.preserve_rules,
    )

    imports, import_conflicts = _merge_membership(
        intent_name=str(intent_name),
        section="import",
        base=base_ir.imports,
        left=left_ir.imports,
        right=right_ir.imports,
        conflict_type="structural_conflict",
    )
    modules, module_conflicts = _merge_membership(
        intent_name=str(intent_name),
        section="module",
        base=base_ir.modules,
        left=left_ir.modules,
        right=right_ir.modules,
        conflict_type="structural_conflict",
    )
    types, type_conflicts = _merge_membership(
        intent_name=str(intent_name),
        section="type",
        base=base_ir.types,
        left=left_ir.types,
        right=right_ir.types,
        conflict_type="type_conflict",
    )
    enums, enum_conflicts = _merge_membership(
        intent_name=str(intent_name),
        section="enum",
        base=base_ir.enums,
        left=left_ir.enums,
        right=right_ir.enums,
        conflict_type="type_conflict",
    )
    interfaces, interface_conflicts = _merge_membership(
        intent_name=str(intent_name),
        section="interface",
        base=base_ir.interfaces,
        left=left_ir.interfaces,
        right=right_ir.interfaces,
        conflict_type="type_conflict",
    )

    agents, agent_conflicts = _merge_agents(intent_name=str(intent_name), base_ir=base_ir, left_ir=left_ir, right_ir=right_ir)
    agentception, c = _merge_scalar(
        intent_name=str(intent_name),
        section="agentception",
        key="config",
        base=base_ir.agentception_config,
        left=left_ir.agentception_config,
        right=right_ir.agentception_config,
        conflict_type="agent_conflict",
    )
    if c:
        agent_conflicts.append(c)

    conflicts.extend(
        input_conflicts
        + output_conflicts
        + bridge_conflicts
        + constraint_conflicts
        + preserve_conflicts
        + import_conflicts
        + module_conflicts
        + type_conflicts
        + enum_conflicts
        + interface_conflicts
        + agent_conflicts
    )

    if conflicts:
        return MergeVerifyResult(
            merge_status="conflict",
            conflicts=conflicts,
            merged_text=None,
            verification=None,
            verification_context={
                "requested": True,
                "available": False,
                "reason": "merge_conflict_no_merged_spec",
                "base": base_summary,
                "left": left_summary,
                "right": right_summary,
                "merged": None,
                "bridge_score_delta_vs_base": None,
            },
            intent_conflicts=[],
            regression_evidence=_build_regression_evidence(
                merge_status="conflict",
                merged_result=None,
                requested_top_n=regression_top_n,
                include_evidence=regression_include_evidence,
                unavailable_reason="merge_conflict_no_merged_spec",
            ),
            policy_evaluation=_build_policy_evaluation(
                merge_status="conflict",
                verification=None,
                intent_conflicts=[],
                require_merged_bridge=require_merged_bridge,
                fail_on_intent_conflicts=fail_on_intent_conflicts,
            ),
        )

    merged_text = _to_vibe_text(
        intent_name=str(intent_name),
        goal=str(goal),
        inputs=inputs,
        outputs=outputs,
        preserve_rules=preserve_rules,
        constraints=constraints,
        bridge_config=bridge,
        emit_target=str(emit_target),
        domain_profile=str(domain_profile),
        vibe_version=str(vibe_version) if vibe_version else None,
        imports=imports,
        modules=modules,
        types=types,
        enums=enums,
        interfaces=interfaces,
        agents=agents,
        agentception=dict(agentception or {}),
    )

    merged_summary, merged_ir, merged_result = _verification_summary(merged_text)
    bridge_delta = float(merged_summary["bridge_score"]) - float(base_summary["bridge_score"])
    intent_conflicts = _classify_intent_conflicts(
        base_ir=base_ir,
        merged_ir=merged_ir,
        base_summary=base_summary,
        merged_summary=merged_summary,
        merged_result=merged_result,
    )
    return MergeVerifyResult(
        merge_status="merged",
        conflicts=[],
        merged_text=merged_text,
        verification=merged_summary,
        verification_context={
            "requested": True,
            "available": True,
            "reason": None,
            "base": base_summary,
            "left": left_summary,
            "right": right_summary,
            "merged": merged_summary,
            "bridge_score_delta_vs_base": bridge_delta,
        },
        intent_conflicts=intent_conflicts,
        regression_evidence=_build_regression_evidence(
            merge_status="merged",
            merged_result=merged_result,
            requested_top_n=regression_top_n,
            include_evidence=regression_include_evidence,
        ),
        policy_evaluation=_build_policy_evaluation(
            merge_status="merged",
            verification=merged_summary,
            intent_conflicts=intent_conflicts,
            require_merged_bridge=require_merged_bridge,
            fail_on_intent_conflicts=fail_on_intent_conflicts,
        ),
    )


def merge_verify_payload(
    result: MergeVerifyResult,
    *,
    base_spec: str,
    left_spec: str,
    right_spec: str,
) -> dict[str, object]:
    return {
        "schema_version": MERGE_VERIFY_SCHEMA_VERSION,
        "report_type": "merge_verify",
        "base_spec": base_spec,
        "left_spec": left_spec,
        "right_spec": right_spec,
        "merge_status": result.merge_status,
        "intent_outcome": (
            "error"
            if result.merge_status == "error"
            else ("structural_conflict" if result.merge_status == "conflict" else ("merged_verified" if bool((result.verification or {}).get("passed")) else "merged_verification_failed"))
        ),
        "merged_text": result.merged_text,
        "verification": result.verification,
        "verification_context": result.verification_context,
        "intent_conflicts": list(result.intent_conflicts or []),
        "regression_evidence": result.regression_evidence,
        "policy_evaluation": result.policy_evaluation,
        "conflicts": [
            {
                "address": c.address,
                "conflict_type": c.conflict_type,
                "base_value": c.base_value,
                "left_value": c.left_value,
                "right_value": c.right_value,
                "message": c.message,
                "severity": c.severity,
            }
            for c in result.conflicts
        ],
        "error": result.error,
    }


def render_merge_verify_json(
    result: MergeVerifyResult,
    *,
    base_spec: str,
    left_spec: str,
    right_spec: str,
) -> str:
    return json.dumps(
        merge_verify_payload(result, base_spec=base_spec, left_spec=left_spec, right_spec=right_spec),
        indent=2,
        sort_keys=True,
    )


def render_merge_verify_human(result: MergeVerifyResult) -> str:
    lines = ["=== Vibe Merge Verify ===", f"merge_status: {result.merge_status}"]
    if result.error:
        lines.append(f"error: {result.error}")
    if result.conflicts:
        lines.append("conflicts:")
        for c in result.conflicts:
            lines.append(f"  - {c.address} [{c.conflict_type}] :: {c.message}")
    if result.verification is not None:
        lines.append("verification:")
        lines.append(f"  passed: {result.verification['passed']}")
        lines.append(f"  bridge_score: {result.verification['bridge_score']}")
        lines.append(f"  obligations: {result.verification['obligations_satisfied']}/{result.verification['obligations_total']}")
    if result.intent_conflicts:
        lines.append("intent_conflicts:")
        for c in result.intent_conflicts:
            lines.append(f"  - {c['conflict_type']} @ {c['address']}: {c['message']}")
    if result.regression_evidence is not None:
        lines.append("regression_evidence:")
        lines.append(f"  available: {result.regression_evidence.get('available')}")
        lines.append(f"  total_problem_obligations: {result.regression_evidence.get('total_problem_obligations')}")
        lines.append(f"  shown_problem_obligations: {result.regression_evidence.get('shown_problem_obligations')}")
    if result.policy_evaluation is not None:
        lines.append("policy_evaluation:")
        lines.append(f"  requested: {result.policy_evaluation.get('requested')}")
        lines.append(f"  available: {result.policy_evaluation.get('available')}")
        lines.append(f"  passed: {result.policy_evaluation.get('passed')}")
    return "\n".join(lines)


def maybe_write_merged(path: Path | None, result: MergeVerifyResult) -> str | None:
    if path is None or result.merge_status != "merged" or result.merged_text is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.merged_text, encoding="utf-8")
    return str(path)


def write_merge_report(path: Path | None, payload: dict[str, object]) -> str | None:
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
