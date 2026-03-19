"""Phase 8.3 intent negotiation protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

from .ir import IR


@dataclass(slots=True)
class NegotiationParticipant:
    path: str
    intent_name: str
    emit_target: str
    domain_profile: str


@dataclass(slots=True)
class ClauseRecord:
    category: str
    key: str
    detail: str
    participants: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NegotiatedContract:
    intent_name: str
    participants: list[NegotiationParticipant]
    inputs: dict[str, str]
    outputs: dict[str, str]
    preserve_rules: list[tuple[str, str, str]]
    constraints: list[str]
    bridge_config: dict[str, str]
    emit_target: str
    domain_profile: str
    compatible_clauses: list[ClauseRecord] = field(default_factory=list)
    strengthened_clauses: list[ClauseRecord] = field(default_factory=list)
    conflicts: list[ClauseRecord] = field(default_factory=list)
    ambiguous_clauses: list[ClauseRecord] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.conflicts and not self.ambiguous_clauses

    def to_dict(self) -> dict[str, object]:
        return {
            "intent_name": self.intent_name,
            "participants": [asdict(p) for p in self.participants],
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "preserve_rules": [list(r) for r in self.preserve_rules],
            "constraints": list(self.constraints),
            "bridge_config": dict(self.bridge_config),
            "emit_target": self.emit_target,
            "domain_profile": self.domain_profile,
            "compatible_clauses": [asdict(c) for c in self.compatible_clauses],
            "strengthened_clauses": [asdict(c) for c in self.strengthened_clauses],
            "conflicts": [asdict(c) for c in self.conflicts],
            "ambiguous_clauses": [asdict(c) for c in self.ambiguous_clauses],
            "success": self.success,
            "summary": {
                "participant_count": len(self.participants),
                "compatible_count": len(self.compatible_clauses),
                "strengthened_count": len(self.strengthened_clauses),
                "conflict_count": len(self.conflicts),
                "ambiguous_count": len(self.ambiguous_clauses),
            },
        }


def _rule_map(rules: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
    return {k: (op, v) for k, op, v in rules}


def _parse_float(text: str) -> float | None:
    try:
        return float(text)
    except Exception:
        return None


def _stronger_preserve(
    key: str,
    current: tuple[str, str],
    incoming: tuple[str, str],
) -> tuple[tuple[str, str] | None, str]:
    cur_op, cur_v = current
    inc_op, inc_v = incoming
    cur_f = _parse_float(cur_v)
    inc_f = _parse_float(inc_v)

    if cur_op == inc_op and cur_f is not None and inc_f is not None:
        if cur_op in {"<", "<="}:
            return ((inc_op, inc_v), "strengthened") if inc_f < cur_f else ((cur_op, cur_v), "compatible")
        if cur_op in {">", ">="}:
            return ((inc_op, inc_v), "strengthened") if inc_f > cur_f else ((cur_op, cur_v), "compatible")
        if cur_op == "==":
            if cur_v == inc_v:
                return ((cur_op, cur_v), "compatible")
            return (None, "conflict")
    if current == incoming:
        return (current, "compatible")
    return (None, "ambiguous")


def _constraints_conflict(a: str, b: str) -> bool:
    aa = a.lower().strip()
    bb = b.lower().strip()
    pairs = [
        ("no pii in logs", "raw debug logs required"),
        ("no patient-identifiable metadata in outputs", "raw patient metadata required"),
        ("deterministic", "nondeterministic"),
    ]
    return any((x in aa and y in bb) or (x in bb and y in aa) for x, y in pairs)


def _merge_bridge(
    key: str,
    existing: str | None,
    incoming: str,
) -> tuple[str | None, str]:
    if existing is None:
        return (incoming, "compatible")
    if existing == incoming:
        return (existing, "compatible")
    if key == "measurement_safe_ratio":
        e, i = _parse_float(existing), _parse_float(incoming)
        if e is None or i is None:
            return (None, "ambiguous")
        return (str(max(e, i)), "strengthened")
    if key == "epsilon_floor":
        e, i = _parse_float(existing), _parse_float(incoming)
        if e is None or i is None:
            return (None, "ambiguous")
        return (str(min(e, i)), "strengthened")
    if key == "mode":
        if "strict" in {existing, incoming}:
            return ("strict", "strengthened")
        return (None, "ambiguous")
    return (None, "ambiguous")


def negotiate_intents(irs: list[IR], paths: list[str]) -> NegotiatedContract:
    if len(irs) < 2:
        raise ValueError("negotiation requires at least two intent specs")
    if len(irs) != len(paths):
        raise ValueError("paths and irs length mismatch")

    participants = [
        NegotiationParticipant(path=paths[i], intent_name=ir.intent_name, emit_target=ir.emit_target, domain_profile=ir.domain_profile)
        for i, ir in enumerate(irs)
    ]
    compatible: list[ClauseRecord] = []
    strengthened: list[ClauseRecord] = []
    conflicts: list[ClauseRecord] = []
    ambiguous: list[ClauseRecord] = []

    merged_inputs: dict[str, str] = {}
    merged_outputs: dict[str, str] = {}
    merged_preserve: dict[str, tuple[str, str]] = {}
    merged_constraints: set[str] = set()
    merged_bridge: dict[str, str] = {}

    domain_profile = irs[0].domain_profile
    emit_target = irs[0].emit_target

    for idx, ir in enumerate(irs):
        label = paths[idx]
        if ir.domain_profile != domain_profile:
            conflicts.append(
                ClauseRecord("domain", "domain_profile", f"incompatible domain profiles: {domain_profile} vs {ir.domain_profile}", [paths[0], label])
            )
        if ir.emit_target != emit_target:
            conflicts.append(
                ClauseRecord("emit", "emit_target", f"incompatible emit targets: {emit_target} vs {ir.emit_target}", [paths[0], label])
            )

        for key, typ in sorted(ir.inputs.items()):
            if key not in merged_inputs:
                merged_inputs[key] = typ
            elif merged_inputs[key] != typ:
                conflicts.append(ClauseRecord("input", key, f"type conflict: {merged_inputs[key]} vs {typ}", [label]))

        for key, typ in sorted(ir.outputs.items()):
            if key not in merged_outputs:
                merged_outputs[key] = typ
            elif merged_outputs[key] != typ:
                conflicts.append(ClauseRecord("output", key, f"type conflict: {merged_outputs[key]} vs {typ}", [label]))

        for c in sorted({x.strip() for x in ir.constraints}):
            for existing in list(merged_constraints):
                if _constraints_conflict(existing, c):
                    conflicts.append(ClauseRecord("constraint", c, f"direct contradiction with `{existing}`", [label]))
            if c in merged_constraints:
                compatible.append(ClauseRecord("constraint", c, "compatible", [label]))
            else:
                merged_constraints.add(c)
                strengthened.append(ClauseRecord("constraint", c, "added (meet union)", [label]))

        pmap = _rule_map(ir.preserve_rules)
        for key, rule in sorted(pmap.items()):
            if key not in merged_preserve:
                merged_preserve[key] = rule
                compatible.append(ClauseRecord("preserve", key, "seeded", [label]))
                continue
            chosen, status = _stronger_preserve(key, merged_preserve[key], rule)
            if status == "compatible":
                compatible.append(ClauseRecord("preserve", key, "compatible", [label]))
            elif status == "strengthened" and chosen is not None:
                merged_preserve[key] = chosen
                strengthened.append(ClauseRecord("preserve", key, f"strengthened to `{chosen[0]} {chosen[1]}`", [label]))
            elif status == "conflict":
                conflicts.append(ClauseRecord("preserve", key, "irreconcilable preserve contradiction", [label]))
            else:
                ambiguous.append(ClauseRecord("preserve", key, "ambiguous preserve merge; conservative failure", [label]))

        for key, val in sorted(ir.bridge_config.items()):
            merged, status = _merge_bridge(key, merged_bridge.get(key), str(val))
            if status == "compatible" and merged is not None:
                merged_bridge[key] = merged
                compatible.append(ClauseRecord("bridge", key, "compatible", [label]))
            elif status == "strengthened" and merged is not None:
                merged_bridge[key] = merged
                strengthened.append(ClauseRecord("bridge", key, f"strengthened to `{merged}`", [label]))
            else:
                ambiguous.append(ClauseRecord("bridge", key, "ambiguous bridge merge; conservative failure", [label]))

    merged_rules = sorted([(k, op, v) for k, (op, v) in merged_preserve.items()], key=lambda r: r[0])
    return NegotiatedContract(
        intent_name="NegotiatedIntentContract",
        participants=participants,
        inputs=dict(sorted(merged_inputs.items())),
        outputs=dict(sorted(merged_outputs.items())),
        preserve_rules=merged_rules,
        constraints=sorted(merged_constraints),
        bridge_config=dict(sorted(merged_bridge.items())),
        emit_target=emit_target,
        domain_profile=domain_profile,
        compatible_clauses=sorted(compatible, key=lambda c: (c.category, c.key, c.detail)),
        strengthened_clauses=sorted(strengthened, key=lambda c: (c.category, c.key, c.detail)),
        conflicts=sorted(conflicts, key=lambda c: (c.category, c.key, c.detail)),
        ambiguous_clauses=sorted(ambiguous, key=lambda c: (c.category, c.key, c.detail)),
    )


def render_negotiated_vibe(contract: NegotiatedContract) -> str:
    lines = [
        f"domain {contract.domain_profile}" if contract.domain_profile != "general" else "",
        "",
        f"intent {contract.intent_name}:",
        '  goal: "Negotiated contract derived from multi-party intent meet"',
        "  inputs:",
    ]
    lines.extend([f"    {k}: {v}" for k, v in sorted(contract.inputs.items())] or ["    _none: string"])
    lines.append("  outputs:")
    lines.extend([f"    {k}: {v}" for k, v in sorted(contract.outputs.items())] or ["    _none: string"])
    lines.extend(["", "preserve:"])
    lines.extend([f"  {k} {op} {v}".rstrip() for k, op, v in contract.preserve_rules] or ["  negotiated_contract_integrity >= 1"])
    lines.extend(["", "constraint:"])
    lines.extend([f"  {c}" for c in contract.constraints] or ["  deterministic outputs"])
    if contract.bridge_config:
        lines.extend(["", "bridge:"])
        lines.extend([f"  {k} = {v}" for k, v in sorted(contract.bridge_config.items())])
    lines.extend(["", f"emit {contract.emit_target}"])
    return "\n".join([ln for ln in lines if ln != ""]) + "\n"


def render_negotiation_human(contract: NegotiatedContract, *, show_conflicts: bool = True, show_strengthening: bool = True) -> str:
    lines = [
        "=== Vibe Intent Negotiation (Phase 8.3) ===",
        f"participants: {[p.path for p in contract.participants]}",
        f"success: {contract.success}",
        f"emit_target: {contract.emit_target}",
        f"domain_profile: {contract.domain_profile}",
        f"summary: {contract.to_dict()['summary']}",
    ]
    if show_strengthening:
        lines.append("strengthened_clauses:")
        lines.extend([f"- {c.category}:{c.key} :: {c.detail}" for c in contract.strengthened_clauses] or ["- none"])
    if show_conflicts:
        lines.append("conflicts:")
        lines.extend([f"- {c.category}:{c.key} :: {c.detail}" for c in contract.conflicts] or ["- none"])
        lines.append("ambiguous_clauses:")
        lines.extend([f"- {c.category}:{c.key} :: {c.detail}" for c in contract.ambiguous_clauses] or ["- none"])
    lines.append("truthfulness: irreconcilable or ambiguous clauses block negotiated compile source generation.")
    return "\n".join(lines)


def render_negotiation_json(contract: NegotiatedContract) -> str:
    return json.dumps(contract.to_dict(), indent=2, sort_keys=True)


def write_negotiation_artifact(path: Path, contract: NegotiatedContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_negotiation_json(contract), encoding="utf-8")
