"""Three-way merge + verification for Vibe specs (Phase 2A)."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .emitter import emit_code
from .ir import IR, ast_to_ir
from .parser import parse_source
from .verifier import verify

MERGE_VERIFY_SCHEMA_VERSION = "v1"


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
    error: str | None = None


def _merge_scalar(address: str, base: object, left: object, right: object, conflict_type: str) -> tuple[object | None, MergeConflict | None]:
    if left == right:
        return left, None
    if left == base:
        return right, None
    if right == base:
        return left, None
    return None, MergeConflict(
        address=address,
        conflict_type=conflict_type,
        base_value=base,
        left_value=left,
        right_value=right,
        message=f"conflicting updates at {address}",
    )


def _merge_map(
    prefix: str,
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
        chosen, conflict = _merge_scalar(f"{prefix}.{key}", b, l, r, conflict_type)
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if chosen is not None:
            merged[key] = str(chosen)
    return merged, conflicts


def _merge_constraints(base: list[str], left: list[str], right: list[str]) -> tuple[list[str], list[MergeConflict]]:
    merged: list[str] = []
    conflicts: list[MergeConflict] = []
    bset = set(base)
    lset = set(left)
    rset = set(right)
    for item in sorted(bset | lset | rset):
        b = item in bset
        l = item in lset
        r = item in rset
        chosen, conflict = _merge_scalar(f"constraint.{item}", b, l, r, "constraint_conflict")
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if bool(chosen):
            merged.append(item)
    return merged, conflicts


def _rules_to_map(rules: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
    return {k: (op, value) for k, op, value in rules}


def _merge_preserve(
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
        chosen, conflict = _merge_scalar(f"preserve.{key}", b, l, r, "preserve_conflict")
        if conflict is not None:
            conflicts.append(conflict)
            continue
        if chosen is not None:
            op, value = chosen
            merged.append((key, op, value))
    return merged, conflicts


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
) -> str:
    lines: list[str] = []
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
    if bridge_config:
        lines.append("")
        lines.append("bridge:")
        for key in sorted(bridge_config):
            lines.append(f"  {key} = {bridge_config[key]}")
    lines.append("")
    lines.append(f"emit {emit_target}")
    lines.append("")
    return "\n".join(lines)


def _verification_summary(merged_text: str) -> dict[str, object]:
    ir = ast_to_ir(parse_source(merged_text))
    emitted, _ = emit_code(ir)
    result = verify(ir, emitted, use_calibration=False)
    obligations_total = len(result.obligations)
    obligations_satisfied = sum(1 for o in result.obligations if o.status == "satisfied")
    return {
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


def merge_verify(base_text: str, left_text: str, right_text: str) -> MergeVerifyResult:
    try:
        base_ir = ast_to_ir(parse_source(base_text))
        left_ir = ast_to_ir(parse_source(left_text))
        right_ir = ast_to_ir(parse_source(right_text))
    except Exception as exc:
        return MergeVerifyResult(merge_status="error", conflicts=[], merged_text=None, verification=None, error=str(exc))

    conflicts: list[MergeConflict] = []

    intent_name, c = _merge_scalar(
        "intent.name", base_ir.intent_name, left_ir.intent_name, right_ir.intent_name, "structural_conflict"
    )
    if c:
        conflicts.append(c)
    goal, c = _merge_scalar("intent.goal", base_ir.goal, left_ir.goal, right_ir.goal, "value_conflict")
    if c:
        conflicts.append(c)
    emit_target, c = _merge_scalar("emit.target", base_ir.emit_target, left_ir.emit_target, right_ir.emit_target, "value_conflict")
    if c:
        conflicts.append(c)
    domain_profile, c = _merge_scalar(
        "domain.profile", base_ir.domain_profile, left_ir.domain_profile, right_ir.domain_profile, "structural_conflict"
    )
    if c:
        conflicts.append(c)

    inputs, input_conflicts = _merge_map("input", base_ir.inputs, left_ir.inputs, right_ir.inputs, "structural_conflict")
    outputs, output_conflicts = _merge_map("output", base_ir.outputs, left_ir.outputs, right_ir.outputs, "structural_conflict")
    bridge, bridge_conflicts = _merge_map(
        "bridge", base_ir.bridge_config, left_ir.bridge_config, right_ir.bridge_config, "bridge_param_conflict"
    )
    constraints, constraint_conflicts = _merge_constraints(base_ir.constraints, left_ir.constraints, right_ir.constraints)
    preserve_rules, preserve_conflicts = _merge_preserve(base_ir.preserve_rules, left_ir.preserve_rules, right_ir.preserve_rules)
    conflicts.extend(input_conflicts + output_conflicts + bridge_conflicts + constraint_conflicts + preserve_conflicts)

    if conflicts:
        return MergeVerifyResult(merge_status="conflict", conflicts=conflicts, merged_text=None, verification=None)

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
    )

    verification = _verification_summary(merged_text)
    return MergeVerifyResult(merge_status="merged", conflicts=[], merged_text=merged_text, verification=verification)


def render_merge_verify_json(
    result: MergeVerifyResult,
    *,
    base_spec: str,
    left_spec: str,
    right_spec: str,
) -> str:
    payload = {
        "schema_version": "v1",
        "report_type": "merge_verify",
        "base_spec": base_spec,
        "left_spec": left_spec,
        "right_spec": right_spec,
        "merge_status": result.merge_status,
        "merged_text": result.merged_text,
        "verification": result.verification,
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
    return json.dumps(payload, indent=2, sort_keys=True)


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
    return "\n".join(lines)


def maybe_write_merged(path: Path | None, result: MergeVerifyResult) -> str | None:
    if path is None or result.merge_status != "merged" or result.merged_text is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.merged_text, encoding="utf-8")
    return str(path)
