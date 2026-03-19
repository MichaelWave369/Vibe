"""AST node definitions for .vibe source files."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Field:
    name: str
    type_name: str


@dataclass(slots=True)
class IntentBlock:
    name: str
    goal: str
    inputs: list[Field] = field(default_factory=list)
    outputs: list[Field] = field(default_factory=list)


@dataclass(slots=True)
class PreserveRule:
    key: str
    op: str
    value: str


@dataclass(slots=True)
class BridgeSetting:
    key: str
    value: str


@dataclass(slots=True)
class TeslaArcTower:
    global_resonance: bool = False
    substrate_bridge: list[str] = field(default_factory=list)
    preserve_epsilon: bool = False
    preserve_sovereignty: bool = False


@dataclass(slots=True)
class TeslaLifeRay:
    bio_field: str = "human"
    baseline_frequency_hz: float = 0.0
    harmonic_mode: str = ""
    intention: str = ""


@dataclass(slots=True)
class TeslaBreathCycle:
    pralaya_inhalation: str = ""
    kalpa_exhalation: str = ""
    c_star_target: str = ""
    monitor: str = ""


@dataclass(slots=True)
class TeslaVictoryLayer:
    arc_tower: TeslaArcTower | None = None
    life_ray: TeslaLifeRay | None = None
    breath_cycle: TeslaBreathCycle | None = None


@dataclass(slots=True)
class AgentDefinition:
    name: str
    role: str
    tools: list[str] = field(default_factory=list)
    memory: str = "session"
    intention: str = ""
    constraints: list[str] = field(default_factory=list)
    preserve: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentoraBlock:
    agents: list[AgentDefinition] = field(default_factory=list)


@dataclass(slots=True)
class AgentceptionBlock:
    enabled: bool = False
    max_depth: int = 0
    spawn_policy: str = ""
    inherit_preserve: bool = False
    inherit_constraints: bool = False
    inherit_bridge: bool = False
    merge_strategy: str = ""
    stop_when: str = ""


@dataclass(slots=True)
class AgentGraphAgent:
    name: str
    role: str
    receives: str
    emits: str
    preserve: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OrchestrationEdge:
    source: str
    target: str


@dataclass(slots=True)
class OrchestrateBlock:
    name: str
    edges: list[OrchestrationEdge] = field(default_factory=list)
    on_error: str | None = None


@dataclass(slots=True)
class DelegationDecl:
    parent: str
    child: str
    inherits: list[str] = field(default_factory=lambda: ["preserve", "constraint", "bridge"])
    max_depth: int | None = None
    stop_when: str | None = None


@dataclass(slots=True)
class Program:
    intent: IntentBlock
    preserve: list[PreserveRule] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    bridge: list[BridgeSetting] = field(default_factory=list)
    emit_target: str = "python"
    tesla_victory_layer: TeslaVictoryLayer | None = None
    agentora: AgentoraBlock | None = None
    agentception: AgentceptionBlock | None = None
    vibe_version: str | None = None
    imports: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    enums: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)
    agents: list[AgentGraphAgent] = field(default_factory=list)
    orchestrations: list[OrchestrateBlock] = field(default_factory=list)
    delegations: list[DelegationDecl] = field(default_factory=list)
    domain_profile: str | None = None
