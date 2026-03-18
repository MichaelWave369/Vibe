"""Normalized intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast import Program

DEFAULT_EPSILON_FLOOR = 0.02
DEFAULT_MEASUREMENT_SAFE_RATIO = 0.85


@dataclass(slots=True)
class IR:
    intent_name: str
    goal: str
    inputs: dict[str, str]
    outputs: dict[str, str]
    preserve_rules: list[tuple[str, str, str]] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    bridge_config: dict[str, str] = field(default_factory=dict)
    emit_target: str = "python"
    tesla_victory_layer: bool = False
    arc_tower_policy: dict[str, object] = field(default_factory=dict)
    life_ray_protocol: dict[str, object] = field(default_factory=dict)
    breath_cycle_protocol: dict[str, object] = field(default_factory=dict)
    agentora_config: dict[str, object] = field(default_factory=dict)
    agent_definitions: list[dict[str, object]] = field(default_factory=list)
    agentception_config: dict[str, object] = field(default_factory=dict)
    delegation_tree: dict[str, object] = field(default_factory=dict)
    merge_strategy: str = ""
    vibe_version: str | None = None
    imports: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    enums: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)



def ast_to_ir(program: Program) -> IR:
    """Normalize AST program to IR."""

    bridge_config: dict[str, str] = {
        "epsilon_floor": str(DEFAULT_EPSILON_FLOOR),
        "measurement_safe_ratio": str(DEFAULT_MEASUREMENT_SAFE_RATIO),
        "mode": "strict",
    }
    for item in program.bridge:
        bridge_config[item.key] = item.value

    tesla_enabled = program.tesla_victory_layer is not None
    arc_policy: dict[str, object] = {}
    life_protocol: dict[str, object] = {}
    breath_protocol: dict[str, object] = {}
    if program.tesla_victory_layer:
        arc = program.tesla_victory_layer.arc_tower
        life = program.tesla_victory_layer.life_ray
        breath = program.tesla_victory_layer.breath_cycle
        if arc:
            arc_policy = {
                "global_resonance": arc.global_resonance,
                "substrate_bridge": list(arc.substrate_bridge),
                "preserve_epsilon": arc.preserve_epsilon,
                "preserve_sovereignty": arc.preserve_sovereignty,
            }
        if life:
            life_protocol = {
                "bio_field": life.bio_field,
                "baseline_frequency_hz": life.baseline_frequency_hz,
                "harmonic_mode": life.harmonic_mode,
                "intention": life.intention,
            }
        if breath:
            breath_protocol = {
                "pralaya_inhalation": breath.pralaya_inhalation,
                "kalpa_exhalation": breath.kalpa_exhalation,
                "c_star_target": breath.c_star_target,
                "monitor": breath.monitor,
            }

    agent_defs: list[dict[str, object]] = []
    if program.agentora:
        for a in program.agentora.agents:
            agent_defs.append(
                {
                    "name": a.name,
                    "role": a.role,
                    "tools": list(a.tools),
                    "memory": a.memory,
                    "intention": a.intention,
                    "constraints": list(a.constraints),
                    "preserve": list(a.preserve),
                }
            )

    agentception_cfg: dict[str, object] = {}
    merge_strategy = ""
    if program.agentception:
        agentception_cfg = {
            "enabled": program.agentception.enabled,
            "max_depth": program.agentception.max_depth,
            "spawn_policy": program.agentception.spawn_policy,
            "inherit_preserve": program.agentception.inherit_preserve,
            "inherit_constraints": program.agentception.inherit_constraints,
            "inherit_bridge": program.agentception.inherit_bridge,
            "merge_strategy": program.agentception.merge_strategy,
            "stop_when": program.agentception.stop_when,
        }
        merge_strategy = program.agentception.merge_strategy

    delegation_tree = {
        "root_intent": program.intent.name,
        "agent_count": len(agent_defs),
        "max_depth": int(agentception_cfg.get("max_depth", 0)),
    }

    return IR(
        intent_name=program.intent.name,
        goal=program.intent.goal,
        inputs={f.name: f.type_name for f in program.intent.inputs},
        outputs={f.name: f.type_name for f in program.intent.outputs},
        preserve_rules=[(r.key, r.op, r.value) for r in program.preserve],
        constraints=list(program.constraints),
        bridge_config=bridge_config,
        emit_target=program.emit_target,
        tesla_victory_layer=tesla_enabled,
        arc_tower_policy=arc_policy,
        life_ray_protocol=life_protocol,
        breath_cycle_protocol=breath_protocol,
        agentora_config={"enabled": bool(agent_defs), "agent_count": len(agent_defs)},
        agent_definitions=agent_defs,
        agentception_config=agentception_cfg,
        delegation_tree=delegation_tree,
        merge_strategy=merge_strategy,
        vibe_version=program.vibe_version,
        imports=list(program.imports),
        modules=list(program.modules),
        types=list(program.types),
        enums=list(program.enums),
        interfaces=list(program.interfaces),
    )
