"""AST node definitions for .vibe source files."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Field:
    """A typed field declaration such as `amount: number`."""

    name: str
    type_name: str


@dataclass(slots=True)
class IntentBlock:
    """Intent declaration block."""

    name: str
    goal: str
    inputs: list[Field] = field(default_factory=list)
    outputs: list[Field] = field(default_factory=list)


@dataclass(slots=True)
class PreserveRule:
    """A preservation rule such as `latency < 200ms`."""

    key: str
    op: str
    value: str


@dataclass(slots=True)
class BridgeSetting:
    """Bridge configuration setting in the bridge block."""

    key: str
    value: str


@dataclass(slots=True)
class Program:
    """Top-level program AST."""

    intent: IntentBlock
    preserve: list[PreserveRule] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    bridge: list[BridgeSetting] = field(default_factory=list)
    emit_target: str = "python"
