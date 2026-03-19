"""Typed SSA intermediate representation for Vibe (Phase 1.2)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from typing import Literal

from .ast import Program

DEFAULT_EPSILON_FLOOR = 0.02
DEFAULT_MEASUREMENT_SAFE_RATIO = 0.85

VType = Literal[
    "string",
    "number",
    "boolean",
    "duration",
    "frequency",
    "symbol",
    "list",
    "map",
    "variant",
    "named",
]


@dataclass(slots=True)
class SSAValue:
    value_id: str
    vtype: VType
    kind: str
    data: str | float | bool | list[str] | dict[str, str]
    uses: list[str] = field(default_factory=list)
    semantic_qualifiers: list[str] = field(default_factory=list)
    effect_tags: list[str] = field(default_factory=list)
    resource_tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SymbolBinding:
    name: str
    value_id: str
    vtype: VType


@dataclass(slots=True)
class IRPreserveRule:
    key_ref: str
    op: str
    value_ref: str


@dataclass(slots=True)
class IRConstraint:
    text_ref: str


@dataclass(slots=True)
class IRBridgeSetting:
    key_ref: str
    value_ref: str


@dataclass(slots=True)
class IRTeslaLayer:
    global_resonance_ref: str
    substrate_bridge_ref: str
    preserve_epsilon_ref: str
    preserve_sovereignty_ref: str
    bio_field_ref: str
    baseline_frequency_ref: str
    harmonic_mode_ref: str
    intention_ref: str
    pralaya_inhalation_ref: str
    kalpa_exhalation_ref: str
    c_star_target_ref: str
    monitor_ref: str


@dataclass(slots=True)
class IRAgentDefinition:
    name_ref: str
    role_ref: str
    tools_ref: str
    memory_ref: str
    intention_ref: str
    constraints_ref: str
    preserve_ref: str


@dataclass(slots=True)
class IRAgentora:
    agents: list[IRAgentDefinition] = field(default_factory=list)


@dataclass(slots=True)
class IRAgentception:
    enabled_ref: str
    max_depth_ref: str
    spawn_policy_ref: str
    inherit_preserve_ref: str
    inherit_constraints_ref: str
    inherit_bridge_ref: str
    merge_strategy_ref: str
    stop_when_ref: str


@dataclass(slots=True)
class IRModule:
    module_name: str
    vibe_version_ref: str | None
    imports_refs: list[str]
    modules_refs: list[str]
    types_refs: list[str]
    enums_refs: list[str]
    interfaces_refs: list[str]
    values: dict[str, SSAValue]
    bindings: list[SymbolBinding]
    preserve_rules: list[IRPreserveRule]
    constraints: list[IRConstraint]
    bridge_settings: list[IRBridgeSetting]
    emit_target_ref: str
    tesla_layer: IRTeslaLayer | None
    agentora: IRAgentora | None
    agentception: IRAgentception | None
    semantic_summary: dict[str, object] = field(default_factory=dict)
    semantic_issues: list[dict[str, object]] = field(default_factory=list)
    effect_summary: dict[str, object] = field(default_factory=dict)
    effect_issues: list[dict[str, object]] = field(default_factory=list)
    resource_summary: dict[str, object] = field(default_factory=dict)
    resource_issues: list[dict[str, object]] = field(default_factory=list)
    inference_summary: dict[str, object] = field(default_factory=dict)
    inference_issues: list[dict[str, object]] = field(default_factory=list)
    agent_graph: dict[str, object] = field(default_factory=dict)
    agent_graph_summary: dict[str, object] = field(default_factory=dict)
    agent_graph_issues: list[dict[str, object]] = field(default_factory=list)
    agent_boundary_summary: dict[str, object] = field(default_factory=dict)
    agent_boundary_issues: list[dict[str, object]] = field(default_factory=list)
    delegation_tree: dict[str, object] = field(default_factory=dict)
    delegation_summary: dict[str, object] = field(default_factory=dict)
    delegation_issues: list[dict[str, object]] = field(default_factory=list)
    runtime_monitor: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IR:
    """Public IR object used by verifier/generator/report."""

    module: IRModule

    @property
    def intent_name(self) -> str:
        return self.module.module_name

    @property
    def goal(self) -> str:
        for b in self.module.bindings:
            if b.name == "intent.goal":
                return str(self._value(b.value_id).data)
        return ""

    @property
    def inputs(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for b in self.module.bindings:
            if b.name.startswith("intent.input."):
                out[b.name.split(".", 2)[2]] = str(self._value(b.value_id).data)
        return out

    @property
    def outputs(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for b in self.module.bindings:
            if b.name.startswith("intent.output."):
                out[b.name.split(".", 2)[2]] = str(self._value(b.value_id).data)
        return out

    @property
    def preserve_rules(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        for r in self.module.preserve_rules:
            rows.append((str(self._value(r.key_ref).data), r.op, str(self._value(r.value_ref).data)))
        return rows

    @property
    def constraints(self) -> list[str]:
        return [str(self._value(c.text_ref).data) for c in self.module.constraints]

    @property
    def bridge_config(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for b in self.module.bridge_settings:
            out[str(self._value(b.key_ref).data)] = str(self._value(b.value_ref).data)
        if "epsilon_floor" not in out:
            out["epsilon_floor"] = str(DEFAULT_EPSILON_FLOOR)
        if "measurement_safe_ratio" not in out:
            out["measurement_safe_ratio"] = str(DEFAULT_MEASUREMENT_SAFE_RATIO)
        if "mode" not in out:
            out["mode"] = "strict"
        return out

    @property
    def emit_target(self) -> str:
        return str(self._value(self.module.emit_target_ref).data)

    @property
    def tesla_victory_layer(self) -> bool:
        return self.module.tesla_layer is not None

    @property
    def arc_tower_policy(self) -> dict[str, object]:
        if not self.module.tesla_layer:
            return {}
        t = self.module.tesla_layer
        return {
            "global_resonance": bool(self._value(t.global_resonance_ref).data),
            "substrate_bridge": list(self._value(t.substrate_bridge_ref).data),
            "preserve_epsilon": bool(self._value(t.preserve_epsilon_ref).data),
            "preserve_sovereignty": bool(self._value(t.preserve_sovereignty_ref).data),
        }

    @property
    def life_ray_protocol(self) -> dict[str, object]:
        if not self.module.tesla_layer:
            return {}
        t = self.module.tesla_layer
        return {
            "bio_field": str(self._value(t.bio_field_ref).data),
            "baseline_frequency_hz": float(self._value(t.baseline_frequency_ref).data),
            "harmonic_mode": str(self._value(t.harmonic_mode_ref).data),
            "intention": str(self._value(t.intention_ref).data),
        }

    @property
    def breath_cycle_protocol(self) -> dict[str, object]:
        if not self.module.tesla_layer:
            return {}
        t = self.module.tesla_layer
        return {
            "pralaya_inhalation": str(self._value(t.pralaya_inhalation_ref).data),
            "kalpa_exhalation": str(self._value(t.kalpa_exhalation_ref).data),
            "c_star_target": str(self._value(t.c_star_target_ref).data),
            "monitor": str(self._value(t.monitor_ref).data),
        }

    @property
    def agent_definitions(self) -> list[dict[str, object]]:
        if not self.module.agentora:
            return []
        out: list[dict[str, object]] = []
        for a in self.module.agentora.agents:
            out.append(
                {
                    "name": str(self._value(a.name_ref).data),
                    "role": str(self._value(a.role_ref).data),
                    "tools": list(self._value(a.tools_ref).data),
                    "memory": str(self._value(a.memory_ref).data),
                    "intention": str(self._value(a.intention_ref).data),
                    "constraints": list(self._value(a.constraints_ref).data),
                    "preserve": list(self._value(a.preserve_ref).data),
                }
            )
        return out

    @property
    def agentora_config(self) -> dict[str, object]:
        return {"enabled": bool(self.agent_definitions), "agent_count": len(self.agent_definitions)}

    @property
    def agentception_config(self) -> dict[str, object]:
        if not self.module.agentception:
            return {}
        a = self.module.agentception
        return {
            "enabled": bool(self._value(a.enabled_ref).data),
            "max_depth": int(float(self._value(a.max_depth_ref).data)),
            "spawn_policy": str(self._value(a.spawn_policy_ref).data),
            "inherit_preserve": bool(self._value(a.inherit_preserve_ref).data),
            "inherit_constraints": bool(self._value(a.inherit_constraints_ref).data),
            "inherit_bridge": bool(self._value(a.inherit_bridge_ref).data),
            "merge_strategy": str(self._value(a.merge_strategy_ref).data),
            "stop_when": str(self._value(a.stop_when_ref).data),
        }

    @property
    def delegation_tree(self) -> dict[str, object]:
        return {
            "root_intent": self.intent_name,
            "agent_count": len(self.agent_definitions),
            "max_depth": int(self.agentception_config.get("max_depth", 0)),
        }

    @property
    def merge_strategy(self) -> str:
        return str(self.agentception_config.get("merge_strategy", ""))

    @property
    def vibe_version(self) -> str | None:
        return str(self._value(self.module.vibe_version_ref).data) if self.module.vibe_version_ref else None

    @property
    def imports(self) -> list[str]:
        return [str(self._value(r).data) for r in self.module.imports_refs]

    @property
    def modules(self) -> list[str]:
        return [str(self._value(r).data) for r in self.module.modules_refs]

    @property
    def types(self) -> list[str]:
        return [str(self._value(r).data) for r in self.module.types_refs]

    @property
    def enums(self) -> list[str]:
        return [str(self._value(r).data) for r in self.module.enums_refs]

    @property
    def interfaces(self) -> list[str]:
        return [str(self._value(r).data) for r in self.module.interfaces_refs]

    @property
    def agent_graph(self) -> dict[str, object]:
        return dict(self.module.agent_graph)

    def _value(self, ref: str) -> SSAValue:
        return self.module.values[ref]




def _obj_dict(obj: object) -> dict[str, object]:
    return {f.name: getattr(obj, f.name) for f in fields(obj)}

class IRBuilder:
    def __init__(self) -> None:
        self.next_id = 1
        self.values: dict[str, SSAValue] = {}

    def const(self, vtype: VType, kind: str, data: str | float | bool | list[str] | dict[str, str]) -> str:
        value_id = f"v{self.next_id}"
        self.next_id += 1
        self.values[value_id] = SSAValue(value_id=value_id, vtype=vtype, kind=kind, data=data, uses=[])
        return value_id

    def use(self, ref: str, by: str) -> None:
        if ref in self.values:
            self.values[ref].uses.append(by)


def ast_to_ir(program: Program) -> IR:
    """Lower AST Program into typed SSA IR."""

    b = IRBuilder()
    bindings: list[SymbolBinding] = []

    goal_ref = b.const("string", "literal", program.intent.goal)
    bindings.append(SymbolBinding(name="intent.goal", value_id=goal_ref, vtype="string"))

    for f in program.intent.inputs:
        ref = b.const("named", "type_ref", f.type_name)
        bindings.append(SymbolBinding(name=f"intent.input.{f.name}", value_id=ref, vtype="named"))
    for f in program.intent.outputs:
        ref = b.const("named", "type_ref", f.type_name)
        bindings.append(SymbolBinding(name=f"intent.output.{f.name}", value_id=ref, vtype="named"))

    preserve_rules: list[IRPreserveRule] = []
    for i, r in enumerate(program.preserve, start=1):
        k = b.const("symbol", "identifier", r.key)
        vtype: VType = "number" if re.match(r"^[0-9.]+$", r.value) else ("duration" if r.value.endswith("ms") else "string")
        v = b.const(vtype, "literal", r.value)
        b.use(k, f"preserve.{i}.key")
        b.use(v, f"preserve.{i}.value")
        preserve_rules.append(IRPreserveRule(key_ref=k, op=r.op, value_ref=v))

    constraints: list[IRConstraint] = []
    for i, c in enumerate(program.constraints, start=1):
        r = b.const("string", "literal", c)
        b.use(r, f"constraint.{i}")
        constraints.append(IRConstraint(text_ref=r))

    bridge_settings: list[IRBridgeSetting] = []
    bridge_map = {x.key: x.value for x in program.bridge}
    bridge_map.setdefault("epsilon_floor", str(DEFAULT_EPSILON_FLOOR))
    bridge_map.setdefault("measurement_safe_ratio", str(DEFAULT_MEASUREMENT_SAFE_RATIO))
    bridge_map.setdefault("mode", "strict")
    for i, (k_raw, v_raw) in enumerate(bridge_map.items(), start=1):
        k = b.const("symbol", "identifier", k_raw)
        vtype: VType = "number" if re.match(r"^[0-9.]+$", v_raw) else "string"
        v = b.const(vtype, "literal", v_raw)
        b.use(k, f"bridge.{i}.key")
        b.use(v, f"bridge.{i}.value")
        bridge_settings.append(IRBridgeSetting(key_ref=k, value_ref=v))

    emit_ref = b.const("symbol", "identifier", program.emit_target)

    tesla_layer: IRTeslaLayer | None = None
    if program.tesla_victory_layer and program.tesla_victory_layer.arc_tower and program.tesla_victory_layer.life_ray and program.tesla_victory_layer.breath_cycle:
        arc = program.tesla_victory_layer.arc_tower
        life = program.tesla_victory_layer.life_ray
        breath = program.tesla_victory_layer.breath_cycle
        tesla_layer = IRTeslaLayer(
            global_resonance_ref=b.const("boolean", "literal", arc.global_resonance),
            substrate_bridge_ref=b.const("list", "literal", list(arc.substrate_bridge)),
            preserve_epsilon_ref=b.const("boolean", "literal", arc.preserve_epsilon),
            preserve_sovereignty_ref=b.const("boolean", "literal", arc.preserve_sovereignty),
            bio_field_ref=b.const("variant", "literal", life.bio_field),
            baseline_frequency_ref=b.const("frequency", "literal", life.baseline_frequency_hz),
            harmonic_mode_ref=b.const("symbol", "identifier", life.harmonic_mode),
            intention_ref=b.const("symbol", "identifier", life.intention),
            pralaya_inhalation_ref=b.const("symbol", "identifier", breath.pralaya_inhalation),
            kalpa_exhalation_ref=b.const("symbol", "identifier", breath.kalpa_exhalation),
            c_star_target_ref=b.const("variant", "literal", breath.c_star_target),
            monitor_ref=b.const("symbol", "identifier", breath.monitor),
        )

    agentora: IRAgentora | None = None
    if program.agentora:
        defs: list[IRAgentDefinition] = []
        for a in program.agentora.agents:
            defs.append(
                IRAgentDefinition(
                    name_ref=b.const("symbol", "identifier", a.name),
                    role_ref=b.const("symbol", "identifier", a.role),
                    tools_ref=b.const("list", "literal", list(a.tools)),
                    memory_ref=b.const("symbol", "identifier", a.memory),
                    intention_ref=b.const("symbol", "identifier", a.intention),
                    constraints_ref=b.const("list", "literal", list(a.constraints)),
                    preserve_ref=b.const("list", "literal", list(a.preserve)),
                )
            )
        agentora = IRAgentora(agents=defs)

    agentception: IRAgentception | None = None
    if program.agentception:
        a = program.agentception
        agentception = IRAgentception(
            enabled_ref=b.const("boolean", "literal", a.enabled),
            max_depth_ref=b.const("number", "literal", float(a.max_depth)),
            spawn_policy_ref=b.const("symbol", "identifier", a.spawn_policy),
            inherit_preserve_ref=b.const("boolean", "literal", a.inherit_preserve),
            inherit_constraints_ref=b.const("boolean", "literal", a.inherit_constraints),
            inherit_bridge_ref=b.const("boolean", "literal", a.inherit_bridge),
            merge_strategy_ref=b.const("symbol", "identifier", a.merge_strategy),
            stop_when_ref=b.const("variant", "literal", a.stop_when),
        )

    vibe_version_ref = b.const("string", "literal", program.vibe_version) if program.vibe_version else None
    imports_refs = [b.const("symbol", "identifier", v) for v in program.imports]
    modules_refs = [b.const("symbol", "identifier", v) for v in program.modules]
    types_refs = [b.const("named", "type_ref", v) for v in program.types]
    enums_refs = [b.const("named", "type_ref", v) for v in program.enums]
    interfaces_refs = [b.const("named", "type_ref", v) for v in program.interfaces]

    module = IRModule(
        module_name=program.intent.name,
        vibe_version_ref=vibe_version_ref,
        imports_refs=imports_refs,
        modules_refs=modules_refs,
        types_refs=types_refs,
        enums_refs=enums_refs,
        interfaces_refs=interfaces_refs,
        values=b.values,
        bindings=bindings,
        preserve_rules=preserve_rules,
        constraints=constraints,
        bridge_settings=bridge_settings,
        emit_target_ref=emit_ref,
        tesla_layer=tesla_layer,
        agentora=agentora,
        agentception=agentception,
        agent_graph={
            "agents": [
                {
                    "name": a.name,
                    "role": a.role,
                    "receives": a.receives,
                    "emits": a.emits,
                    "preserve": list(a.preserve),
                    "constraints": list(a.constraints),
                }
                for a in program.agents
            ],
            "orchestrations": [
                {
                    "name": o.name,
                    "edges": [{"source": e.source, "target": e.target} for e in o.edges],
                    "on_error": o.on_error,
                }
                for o in program.orchestrations
            ],
        },
        delegation_tree={
            "edges": [
                {
                    "parent": d.parent,
                    "child": d.child,
                    "inherits": list(d.inherits),
                    "max_depth": d.max_depth,
                    "stop_when": d.stop_when,
                }
                for d in program.delegations
            ]
        },
    )
    ir = IR(module=module)
    from .semantic_types import annotate_semantic_types

    typing = annotate_semantic_types(ir)
    ir.module.semantic_summary = {
        "qualifier_counts": typing.summary.qualifier_counts,
        "binding_qualifiers": typing.summary.binding_qualifiers,
        "propagation_notes": typing.summary.propagation_notes,
    }
    from .effects import annotate_effects

    effects = annotate_effects(ir)
    ir.module.effect_summary = {
        "inferred_effects": effects.summary.inferred_effects,
        "required_effects": effects.summary.required_effects,
        "forbidden_effects": effects.summary.forbidden_effects,
        "value_effects": effects.summary.value_effects,
        "propagation_notes": effects.summary.propagation_notes,
    }
    from .resources import annotate_resources

    resources = annotate_resources(ir)
    ir.module.resource_summary = {
        "inferred_resources": resources.summary.inferred_resources,
        "declared_bounds": resources.summary.declared_bounds,
        "module_profile": resources.summary.module_profile,
        "value_resources": resources.summary.value_resources,
        "propagation_notes": resources.summary.propagation_notes,
    }
    from .type_inference import annotate_type_inference

    inference = annotate_type_inference(ir)
    ir.module.inference_summary = {
        "declared_types": inference.summary.declared_types,
        "inferred_bindings": inference.summary.inferred_bindings,
        "helper_profiles": ir.module.inference_summary.get("helper_profiles", []),
        "agent_boundary_hints": ir.module.inference_summary.get("agent_boundary_hints", []),
        "unresolved_points": inference.summary.unresolved_points,
        "contradiction_count": inference.summary.contradiction_count,
        "unresolved_count": inference.summary.unresolved_count,
        "propagation_notes": inference.summary.propagation_notes,
    }
    from .agents import annotate_agent_graph

    agent_graph = annotate_agent_graph(ir)
    ir.module.agent_graph_summary = {
        "graph_name": agent_graph.summary.graph_name,
        "agent_count": agent_graph.summary.agent_count,
        "edge_count": agent_graph.summary.edge_count,
        "agents": agent_graph.summary.agents,
        "edges": agent_graph.summary.edges,
        "fallback_routes": agent_graph.summary.fallback_routes,
        "disconnected_agents": agent_graph.summary.disconnected_agents,
        "propagation_notes": agent_graph.summary.propagation_notes,
    }
    from .agent_bridge import annotate_agent_bridges

    boundary = annotate_agent_bridges(ir)
    ir.module.agent_boundary_summary = {
        "edge_summaries": boundary.summary.edge_summaries,
        "pipeline_bridge_score": boundary.summary.pipeline_bridge_score,
        "critical_boundary_failures": boundary.summary.critical_boundary_failures,
        "aggregation_rule": boundary.summary.aggregation_rule,
        "propagation_notes": boundary.summary.propagation_notes,
    }
    from .delegation import annotate_delegation

    delegation = annotate_delegation(ir)
    ir.module.delegation_summary = {
        "delegation_tree": delegation.summary.delegation_tree,
        "inherited_contract_summary": delegation.summary.inherited_contract_summary,
        "recursion_metadata": delegation.summary.recursion_metadata,
        "propagation_notes": delegation.summary.propagation_notes,
    }
    from .runtime_monitor import monitor_config_payload

    ir.module.runtime_monitor = monitor_config_payload(ir)
    validate_ir(ir)
    return ir


def validate_ir(ir: IR) -> None:
    """Validate SSA integrity and root well-formedness."""

    if not ir.module.module_name:
        raise ValueError("IR validation error: module_name is required")
    if not ir.module.values:
        raise ValueError("IR validation error: no SSA values defined")

    seen: set[str] = set()
    for vid, val in ir.module.values.items():
        if vid in seen:
            raise ValueError(f"IR validation error: duplicate SSA definition `{vid}`")
        seen.add(vid)
        if not val.vtype:
            raise ValueError(f"IR validation error: value `{vid}` missing type")

    refs: list[str] = [
        b.value_id for b in ir.module.bindings
    ] + [
        r.key_ref for r in ir.module.preserve_rules
    ] + [
        r.value_ref for r in ir.module.preserve_rules
    ] + [
        c.text_ref for c in ir.module.constraints
    ] + [
        s.key_ref for s in ir.module.bridge_settings
    ] + [
        s.value_ref for s in ir.module.bridge_settings
    ] + [ir.module.emit_target_ref]

    if ir.module.vibe_version_ref:
        refs.append(ir.module.vibe_version_ref)
    refs.extend(ir.module.imports_refs)
    refs.extend(ir.module.modules_refs)
    refs.extend(ir.module.types_refs)
    refs.extend(ir.module.enums_refs)
    refs.extend(ir.module.interfaces_refs)

    if ir.module.tesla_layer:
        refs.extend(_obj_dict(ir.module.tesla_layer).values())
    if ir.module.agentora:
        for a in ir.module.agentora.agents:
            refs.extend(_obj_dict(a).values())
    if ir.module.agentception:
        refs.extend(_obj_dict(ir.module.agentception).values())

    for ref in refs:
        if ref not in ir.module.values:
            raise ValueError(f"IR validation error: undefined SSA reference `{ref}`")


def serialize_ir(ir: IR) -> str:
    """Deterministic JSON serialization for typed SSA IR."""

    payload = {
        "module_name": ir.module.module_name,
        "vibe_version": ir.vibe_version,
        "imports": ir.imports,
        "modules": ir.modules,
        "types": ir.types,
        "enums": ir.enums,
        "interfaces": ir.interfaces,
        "bindings": [_obj_dict(b) for b in ir.module.bindings],
        "values": {k: _obj_dict(v) for k, v in sorted(ir.module.values.items())},
        "preserve_rules": [_obj_dict(r) for r in ir.module.preserve_rules],
        "constraints": [_obj_dict(c) for c in ir.module.constraints],
        "bridge_settings": [_obj_dict(b) for b in ir.module.bridge_settings],
        "emit_target_ref": ir.module.emit_target_ref,
        "tesla_layer": _obj_dict(ir.module.tesla_layer) if ir.module.tesla_layer else None,
        "agentora": (
            {"agents": [_obj_dict(a) for a in ir.module.agentora.agents]} if ir.module.agentora else None
        ),
        "agentception": _obj_dict(ir.module.agentception) if ir.module.agentception else None,
        "semantic_summary": dict(ir.module.semantic_summary),
        "semantic_issues": list(ir.module.semantic_issues),
        "effect_summary": dict(ir.module.effect_summary),
        "effect_issues": list(ir.module.effect_issues),
        "resource_summary": dict(ir.module.resource_summary),
        "resource_issues": list(ir.module.resource_issues),
        "inference_summary": dict(ir.module.inference_summary),
        "inference_issues": list(ir.module.inference_issues),
        "agent_graph": dict(ir.module.agent_graph),
        "agent_graph_summary": dict(ir.module.agent_graph_summary),
        "agent_graph_issues": list(ir.module.agent_graph_issues),
        "agent_boundary_summary": dict(ir.module.agent_boundary_summary),
        "agent_boundary_issues": list(ir.module.agent_boundary_issues),
        "delegation_tree": dict(ir.module.delegation_tree),
        "delegation_summary": dict(ir.module.delegation_summary),
        "delegation_issues": list(ir.module.delegation_issues),
        "runtime_monitor": dict(ir.module.runtime_monitor),
    }
    return json.dumps(payload, indent=2, sort_keys=True)
