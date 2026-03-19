"""Semantic intent diff between two Vibe source specifications (Phase 3.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json

from .ir import IR


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


def render_intent_diff_json(result: IntentDiffResult) -> str:
    payload = {
        "summary": result.summary,
        "changes": [asdict(c) for c in result.changes],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
