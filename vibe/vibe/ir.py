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



def ast_to_ir(program: Program) -> IR:
    """Normalize AST program to IR."""

    bridge_config: dict[str, str] = {
        "epsilon_floor": str(DEFAULT_EPSILON_FLOOR),
        "measurement_safe_ratio": str(DEFAULT_MEASUREMENT_SAFE_RATIO),
        "mode": "strict",
    }
    for item in program.bridge:
        bridge_config[item.key] = item.value

    return IR(
        intent_name=program.intent.name,
        goal=program.intent.goal,
        inputs={f.name: f.type_name for f in program.intent.inputs},
        outputs={f.name: f.type_name for f in program.intent.outputs},
        preserve_rules=[(r.key, r.op, r.value) for r in program.preserve],
        constraints=list(program.constraints),
        bridge_config=bridge_config,
        emit_target=program.emit_target,
    )
