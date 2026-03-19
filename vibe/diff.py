"""Semantic intent diff between two Vibe source specifications (Phase 3.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json

from .ir import IR

DIFF_REPORT_SCHEMA_VERSION = "v1"


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _constraint_is_sovereignty_related(item: str) -> bool:
    lowered = item.lower()
    return any(token in lowered for token in ["sovereign", "sovereignty", "custody", "ownership", "private_key"])


def derive_bridge_impact(change: IntentDiffEntry) -> tuple[float | None, str | None]:
    """Return deterministic bridge-impact delta and source label.

    Positive means stronger bridge guarantees; negative means weakened guarantees.
    None means current Vibe diff cannot honestly infer impact.
    """

    if change.category == "bridge" and change.change_type == "modified":
        old_value = _to_float(change.old_value)
        new_value = _to_float(change.new_value)
        if old_value is None or new_value is None:
            return None, None
        if change.item == "epsilon_floor":
            # Higher epsilon floor strengthens founding-law strictness.
            return round(new_value - old_value, 6), "bridge.threshold.delta"
        if change.item == "measurement_safe_ratio":
            # Higher safe ratio strengthens measurement acceptance threshold.
            return round(new_value - old_value, 6), "bridge.threshold.delta"

    if change.category == "preserve":
        if change.change_type == "added":
            return 0.2, "semantic.preserve.added"
        if change.change_type == "removed":
            return -0.2, "semantic.preserve.removed"
        if change.change_type == "modified":
            if change.semantic_effect == "narrowed":
                return 0.15, "semantic.preserve.modified"
            if change.semantic_effect == "broadened":
                return -0.15, "semantic.preserve.modified"

    if change.category == "constraint":
        if change.change_type == "added":
            return 0.2, "semantic.constraint.added"
        if change.change_type == "removed":
            if _constraint_is_sovereignty_related(change.item):
                return -0.5, "semantic.constraint.removed.sovereignty"
            return -0.2, "semantic.constraint.removed"

    return None, None


def derive_op_severity(change: IntentDiffEntry, bridge_impact: float | None) -> str:
    if bridge_impact is None:
        return "warning" if change.semantic_effect == "broadened" else "info"
    if bridge_impact <= -0.5:
        return "high"
    if bridge_impact < 0:
        return "warning"
    return "info"


@dataclass(slots=True)
class IntentDiffEntry:
    category: str
    item: str
    change_type: str
    semantic_effect: str
    old_value: object
    new_value: object
    explanation: str
    source_location: str | None = None


@dataclass(slots=True)
class IntentDiffResult:
    summary: dict[str, int]
    changes: list[IntentDiffEntry] = field(default_factory=list)


def _effect_for_add_remove(*, category: str, added: bool) -> str:
    if category in {"preserve", "constraint"}:
        return "narrowed" if added else "broadened"
    if category == "input":
        return "narrowed" if added else "broadened"
    if category == "output":
        return "broadened" if added else "narrowed"
    return "unknown"


def _append(entries: list[IntentDiffEntry], entry: IntentDiffEntry) -> None:
    entries.append(entry)


def _diff_named_map(entries: list[IntentDiffEntry], category: str, old: dict[str, str], new: dict[str, str]) -> None:
    for k in sorted(set(old) - set(new)):
        _append(
            entries,
            IntentDiffEntry(
                category=category,
                item=k,
                change_type="removed",
                semantic_effect=_effect_for_add_remove(category=category, added=False),
                old_value=old[k],
                new_value=None,
                explanation=f"{category} `{k}` removed",
            ),
        )
    for k in sorted(set(new) - set(old)):
        _append(
            entries,
            IntentDiffEntry(
                category=category,
                item=k,
                change_type="added",
                semantic_effect=_effect_for_add_remove(category=category, added=True),
                old_value=None,
                new_value=new[k],
                explanation=f"{category} `{k}` added",
            ),
        )
    for k in sorted(set(old) & set(new)):
        if old[k] != new[k]:
            _append(
                entries,
                IntentDiffEntry(
                    category=category,
                    item=k,
                    change_type="modified",
                    semantic_effect="unknown",
                    old_value=old[k],
                    new_value=new[k],
                    explanation=f"{category} `{k}` type/value changed",
                ),
            )


def _rule_map(rules: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
    return {k: (op, v) for k, op, v in rules}


def _diff_preserve(entries: list[IntentDiffEntry], old_rules: list[tuple[str, str, str]], new_rules: list[tuple[str, str, str]]) -> None:
    old = _rule_map(old_rules)
    new = _rule_map(new_rules)
    for k in sorted(set(old) - set(new)):
        _append(entries, IntentDiffEntry("preserve", k, "removed", "broadened", f"{old[k][0]} {old[k][1]}", None, f"preserve rule `{k}` removed"))
    for k in sorted(set(new) - set(old)):
        _append(entries, IntentDiffEntry("preserve", k, "added", "narrowed", None, f"{new[k][0]} {new[k][1]}", f"preserve rule `{k}` added"))
    for k in sorted(set(old) & set(new)):
        if old[k] != new[k]:
            old_rule = f"{old[k][0]} {old[k][1]}"
            new_rule = f"{new[k][0]} {new[k][1]}"
            effect = "unknown"
            if old[k][0] == "<" and new[k][0] == "<":
                effect = "narrowed" if str(new[k][1]) < str(old[k][1]) else "broadened"
            _append(entries, IntentDiffEntry("preserve", k, "modified", effect, old_rule, new_rule, f"preserve rule `{k}` modified"))


def _diff_constraints(entries: list[IntentDiffEntry], old: list[str], new: list[str]) -> None:
    old_set = set(old)
    new_set = set(new)
    for c in sorted(old_set - new_set):
        _append(entries, IntentDiffEntry("constraint", c, "removed", "broadened", c, None, "constraint removed"))
    for c in sorted(new_set - old_set):
        _append(entries, IntentDiffEntry("constraint", c, "added", "narrowed", None, c, "constraint added"))


def _diff_bridge(entries: list[IntentDiffEntry], old: dict[str, str], new: dict[str, str]) -> None:
    for k in sorted(set(old) | set(new)):
        if old.get(k) == new.get(k):
            continue
        old_v = old.get(k)
        new_v = new.get(k)
        if old_v is None:
            _append(entries, IntentDiffEntry("bridge", k, "added", "unknown", None, new_v, f"bridge key `{k}` added"))
            continue
        if new_v is None:
            _append(entries, IntentDiffEntry("bridge", k, "removed", "unknown", old_v, None, f"bridge key `{k}` removed"))
            continue
        effect = "unknown"
        if k == "epsilon_floor":
            effect = "narrowed" if float(new_v) <= float(old_v) else "broadened"
        elif k == "measurement_safe_ratio":
            effect = "narrowed" if float(new_v) >= float(old_v) else "broadened"
        elif k == "mode":
            if old_v == "strict" and new_v != "strict":
                effect = "broadened"
            elif old_v != "strict" and new_v == "strict":
                effect = "narrowed"
        _append(entries, IntentDiffEntry("bridge", k, "modified", effect, old_v, new_v, f"bridge key `{k}` modified"))


def _diff_list_decls(entries: list[IntentDiffEntry], category: str, old: list[str], new: list[str]) -> None:
    for v in sorted(set(old) - set(new)):
        _append(entries, IntentDiffEntry(category, v, "removed", "unknown", v, None, f"{category} declaration removed"))
    for v in sorted(set(new) - set(old)):
        _append(entries, IntentDiffEntry(category, v, "added", "unknown", None, v, f"{category} declaration added"))


def _diff_tesla(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    old_payload = {
        "enabled": old.tesla_victory_layer,
        "arc_tower": old.arc_tower_policy,
        "life_ray": old.life_ray_protocol,
        "breath_cycle": old.breath_cycle_protocol,
    }
    new_payload = {
        "enabled": new.tesla_victory_layer,
        "arc_tower": new.arc_tower_policy,
        "life_ray": new.life_ray_protocol,
        "breath_cycle": new.breath_cycle_protocol,
    }
    if old_payload != new_payload:
        change_type = "modified"
        if not old_payload["enabled"] and new_payload["enabled"]:
            change_type = "added"
        elif old_payload["enabled"] and not new_payload["enabled"]:
            change_type = "removed"
        _append(entries, IntentDiffEntry("tesla_victory_layer", "tesla", change_type, "unknown", old_payload, new_payload, "Tesla Victory Layer changed"))


def _diff_agentora(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    old_agents = {a["name"]: a for a in old.agent_definitions}
    new_agents = {a["name"]: a for a in new.agent_definitions}
    for name in sorted(set(old_agents) - set(new_agents)):
        _append(entries, IntentDiffEntry("agentora", name, "removed", "unknown", old_agents[name], None, f"agent `{name}` removed"))
    for name in sorted(set(new_agents) - set(old_agents)):
        _append(entries, IntentDiffEntry("agentora", name, "added", "unknown", None, new_agents[name], f"agent `{name}` added"))
    for name in sorted(set(old_agents) & set(new_agents)):
        if old_agents[name] != new_agents[name]:
            _append(entries, IntentDiffEntry("agentora", name, "modified", "unknown", old_agents[name], new_agents[name], f"agent `{name}` modified"))


def _diff_agentception(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    if old.agentception_config != new.agentception_config:
        _append(
            entries,
            IntentDiffEntry(
                "agentception",
                "agentception",
                "modified",
                "unknown",
                old.agentception_config,
                new.agentception_config,
                "AgentCeption configuration changed",
            ),
        )


def _diff_hardware(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    if old.module.hardware_summary != new.module.hardware_summary:
        _append(
            entries,
            IntentDiffEntry(
                "hardware",
                "hardware_summary",
                "modified",
                "unknown",
                old.module.hardware_summary,
                new.module.hardware_summary,
                "hardware summary changed",
            ),
        )
    if old.module.hardware_target_metadata != new.module.hardware_target_metadata:
        _append(
            entries,
            IntentDiffEntry(
                "hardware",
                "hardware_target_metadata",
                "modified",
                "unknown",
                old.module.hardware_target_metadata,
                new.module.hardware_target_metadata,
                "hardware target metadata changed",
            ),
        )
    if old.module.hardware_issues != new.module.hardware_issues:
        _append(
            entries,
            IntentDiffEntry(
                "hardware",
                "hardware_issues",
                "modified",
                "unknown",
                old.module.hardware_issues,
                new.module.hardware_issues,
                "hardware issues changed",
            ),
        )


def _diff_scientific_simulation(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    if old.module.scientific_simulation_summary != new.module.scientific_simulation_summary:
        _append(
            entries,
            IntentDiffEntry(
                "scientific_simulation",
                "scientific_simulation_summary",
                "modified",
                "unknown",
                old.module.scientific_simulation_summary,
                new.module.scientific_simulation_summary,
                "scientific simulation summary changed",
            ),
        )
    if old.module.scientific_target_metadata != new.module.scientific_target_metadata:
        _append(
            entries,
            IntentDiffEntry(
                "scientific_simulation",
                "scientific_target_metadata",
                "modified",
                "unknown",
                old.module.scientific_target_metadata,
                new.module.scientific_target_metadata,
                "scientific simulation target metadata changed",
            ),
        )
    if old.module.scientific_simulation_issues != new.module.scientific_simulation_issues:
        _append(
            entries,
            IntentDiffEntry(
                "scientific_simulation",
                "scientific_simulation_issues",
                "modified",
                "unknown",
                old.module.scientific_simulation_issues,
                new.module.scientific_simulation_issues,
                "scientific simulation issues changed",
            ),
        )


def _diff_legal_compliance(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    if old.module.legal_compliance_summary != new.module.legal_compliance_summary:
        _append(
            entries,
            IntentDiffEntry(
                "legal_compliance",
                "legal_compliance_summary",
                "modified",
                "unknown",
                old.module.legal_compliance_summary,
                new.module.legal_compliance_summary,
                "legal compliance summary changed",
            ),
        )
    if old.module.compliance_target_metadata != new.module.compliance_target_metadata:
        _append(
            entries,
            IntentDiffEntry(
                "legal_compliance",
                "compliance_target_metadata",
                "modified",
                "unknown",
                old.module.compliance_target_metadata,
                new.module.compliance_target_metadata,
                "legal compliance target metadata changed",
            ),
        )
    if old.module.legal_compliance_issues != new.module.legal_compliance_issues:
        _append(
            entries,
            IntentDiffEntry(
                "legal_compliance",
                "legal_compliance_issues",
                "modified",
                "unknown",
                old.module.legal_compliance_issues,
                new.module.legal_compliance_issues,
                "legal compliance issues changed",
            ),
        )


def _diff_genomics(entries: list[IntentDiffEntry], old: IR, new: IR) -> None:
    if old.module.genomics_summary != new.module.genomics_summary:
        _append(
            entries,
            IntentDiffEntry(
                "genomics",
                "genomics_summary",
                "modified",
                "unknown",
                old.module.genomics_summary,
                new.module.genomics_summary,
                "genomics summary changed",
            ),
        )
    if old.module.genomics_target_metadata != new.module.genomics_target_metadata:
        _append(
            entries,
            IntentDiffEntry(
                "genomics",
                "genomics_target_metadata",
                "modified",
                "unknown",
                old.module.genomics_target_metadata,
                new.module.genomics_target_metadata,
                "genomics target metadata changed",
            ),
        )
    if old.module.genomics_issues != new.module.genomics_issues:
        _append(
            entries,
            IntentDiffEntry(
                "genomics",
                "genomics_issues",
                "modified",
                "unknown",
                old.module.genomics_issues,
                new.module.genomics_issues,
                "genomics issues changed",
            ),
        )


def compute_intent_diff(old_ir: IR, new_ir: IR) -> IntentDiffResult:
    entries: list[IntentDiffEntry] = []

    if old_ir.goal != new_ir.goal:
        _append(entries, IntentDiffEntry("goal", "intent.goal", "modified", "unknown", old_ir.goal, new_ir.goal, "intent goal changed"))

    _diff_named_map(entries, "input", old_ir.inputs, new_ir.inputs)
    _diff_named_map(entries, "output", old_ir.outputs, new_ir.outputs)
    _diff_preserve(entries, old_ir.preserve_rules, new_ir.preserve_rules)
    _diff_constraints(entries, old_ir.constraints, new_ir.constraints)
    _diff_bridge(entries, old_ir.bridge_config, new_ir.bridge_config)

    if old_ir.emit_target != new_ir.emit_target:
        _append(entries, IntentDiffEntry("emit", "emit_target", "target_changed", "unknown", old_ir.emit_target, new_ir.emit_target, "emit target changed"))

    if old_ir.vibe_version != new_ir.vibe_version:
        _append(entries, IntentDiffEntry("vibe_version", "vibe_version", "modified", "unknown", old_ir.vibe_version, new_ir.vibe_version, "vibe_version changed"))

    _diff_list_decls(entries, "import", old_ir.imports, new_ir.imports)
    _diff_list_decls(entries, "module", old_ir.modules, new_ir.modules)
    _diff_list_decls(entries, "type", old_ir.types, new_ir.types)
    _diff_list_decls(entries, "enum", old_ir.enums, new_ir.enums)
    _diff_list_decls(entries, "interface", old_ir.interfaces, new_ir.interfaces)

    _diff_tesla(entries, old_ir, new_ir)
    _diff_agentora(entries, old_ir, new_ir)
    _diff_agentception(entries, old_ir, new_ir)
    _diff_hardware(entries, old_ir, new_ir)
    _diff_scientific_simulation(entries, old_ir, new_ir)
    _diff_legal_compliance(entries, old_ir, new_ir)
    _diff_genomics(entries, old_ir, new_ir)
    if old_ir.module.semantic_summary != new_ir.module.semantic_summary:
        _append(
            entries,
            IntentDiffEntry(
                "semantic_types",
                "qualifier_summary",
                "modified",
                "unknown",
                old_ir.module.semantic_summary,
                new_ir.module.semantic_summary,
                "semantic type summary changed",
            ),
        )
    if old_ir.module.effect_summary != new_ir.module.effect_summary:
        _append(
            entries,
            IntentDiffEntry(
                "effect_types",
                "effect_summary",
                "modified",
                "unknown",
                old_ir.module.effect_summary,
                new_ir.module.effect_summary,
                "effect type summary changed",
            ),
        )
    if old_ir.module.resource_summary != new_ir.module.resource_summary:
        _append(
            entries,
            IntentDiffEntry(
                "resource_types",
                "resource_summary",
                "modified",
                "unknown",
                old_ir.module.resource_summary,
                new_ir.module.resource_summary,
                "resource type summary changed",
            ),
        )
    if old_ir.module.inference_summary != new_ir.module.inference_summary:
        _append(
            entries,
            IntentDiffEntry(
                "inference_types",
                "inference_summary",
                "modified",
                "unknown",
                old_ir.module.inference_summary,
                new_ir.module.inference_summary,
                "inference type summary changed",
            ),
        )
    if old_ir.module.agent_graph != new_ir.module.agent_graph:
        _append(
            entries,
            IntentDiffEntry(
                "agent_graph",
                "declared_graph",
                "modified",
                "unknown",
                old_ir.module.agent_graph,
                new_ir.module.agent_graph,
                "agent graph declaration changed",
            ),
        )
    if old_ir.module.agent_graph_summary != new_ir.module.agent_graph_summary:
        _append(
            entries,
            IntentDiffEntry(
                "agent_graph",
                "graph_summary",
                "modified",
                "unknown",
                old_ir.module.agent_graph_summary,
                new_ir.module.agent_graph_summary,
                "agent graph summary changed",
            ),
        )
    if old_ir.module.agent_boundary_summary != new_ir.module.agent_boundary_summary:
        _append(
            entries,
            IntentDiffEntry(
                "agent_boundary",
                "boundary_summary",
                "modified",
                "unknown",
                old_ir.module.agent_boundary_summary,
                new_ir.module.agent_boundary_summary,
                "agent boundary bridge summary changed",
            ),
        )
    if old_ir.module.delegation_tree != new_ir.module.delegation_tree:
        _append(
            entries,
            IntentDiffEntry(
                "delegation",
                "declared_delegation",
                "modified",
                "unknown",
                old_ir.module.delegation_tree,
                new_ir.module.delegation_tree,
                "delegation declarations changed",
            ),
        )
    if old_ir.module.delegation_summary != new_ir.module.delegation_summary:
        _append(
            entries,
            IntentDiffEntry(
                "delegation",
                "delegation_summary",
                "modified",
                "unknown",
                old_ir.module.delegation_summary,
                new_ir.module.delegation_summary,
                "delegation summary changed",
            ),
        )
    if old_ir.module.runtime_monitor != new_ir.module.runtime_monitor:
        _append(
            entries,
            IntentDiffEntry(
                "runtime_monitor",
                "monitor_config",
                "modified",
                "unknown",
                old_ir.module.runtime_monitor,
                new_ir.module.runtime_monitor,
                "runtime monitor config changed",
            ),
        )

    summary = {
        "total_changes": len(entries),
        "added": sum(1 for e in entries if e.change_type == "added"),
        "removed": sum(1 for e in entries if e.change_type == "removed"),
        "modified": sum(1 for e in entries if e.change_type == "modified"),
        "broadened": sum(1 for e in entries if e.semantic_effect == "broadened"),
        "narrowed": sum(1 for e in entries if e.semantic_effect == "narrowed"),
        "unknown": sum(1 for e in entries if e.semantic_effect == "unknown"),
        "target_changed": sum(1 for e in entries if e.change_type == "target_changed"),
    }
    entries = sorted(entries, key=lambda e: (e.category, e.item, e.change_type, str(e.old_value), str(e.new_value)))
    return IntentDiffResult(summary=summary, changes=entries)


def render_intent_diff_human(result: IntentDiffResult, *, show_unchanged: bool = False, summary_only: bool = False) -> str:
    lines = [
        "=== Vibe Intent Diff ===",
        f"summary: {result.summary}",
    ]
    if summary_only:
        return "\n".join(lines)
    lines.append("changes:")
    if not result.changes and show_unchanged:
        lines.append("  - no semantic changes detected")
    for e in result.changes:
        lines.append(
            f"  - [{e.change_type}/{e.semantic_effect}] ({e.category}) {e.item}: {e.old_value} -> {e.new_value}"
        )
        lines.append(f"      reason: {e.explanation}")
    return "\n".join(lines)


def render_intent_diff_json(
    result: IntentDiffResult,
    *,
    old_spec: str = "<unknown>",
    new_spec: str = "<unknown>",
    verification_context: dict[str, object] | None = None,
) -> str:
    ops = []
    for c in result.changes:
        bridge_impact, impact_source = derive_bridge_impact(c)
        ops.append(
            {
                "op": c.change_type,
                "address": c.source_location or c.item,
                "field": c.category,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "semantic_polarity": c.semantic_effect,
                "bridge_impact": bridge_impact,
                "bridge_impact_source": impact_source,
                "severity": derive_op_severity(c, bridge_impact),
                "message": c.explanation,
            }
        )
    payload = {
        "schema_version": DIFF_REPORT_SCHEMA_VERSION,
        "report_type": "diff",
        "old_spec": old_spec,
        "new_spec": new_spec,
        "drift_score": float(result.summary.get("broadened", 0)) / max(1, result.summary.get("total_changes", 1)),
        "ops": ops,
        "summary": result.summary,
        "changes": [asdict(c) for c in result.changes],
        "verification_context": verification_context
        if verification_context is not None
        else {
            "verification_requested": False,
            "available": False,
            "reason": "disabled (pass --with-verification-context to vibec diff)",
            "old": None,
            "new": None,
            "bridge_score_delta": None,
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)
