"""Grammar-backed parser for .vibe sources (Phase 1.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ast import (
    AgentGraphAgent,
    AgentDefinition,
    AgentceptionBlock,
    AgentoraBlock,
    BridgeSetting,
    Field,
    DelegationDecl,
    OrchestrateBlock,
    OrchestrationEdge,
    IntentBlock,
    PreserveRule,
    Program,
    TeslaArcTower,
    TeslaBreathCycle,
    TeslaLifeRay,
    TeslaVictoryLayer,
)
from .grammar import GRAMMAR

COMPARISON_OPS = ("<=", ">=", "<", ">", "=")
PRELUDE_PREFIXES = ("vibe_version ", "import ", "module ", "type ", "enum ", "interface ")


class ParseError(ValueError):
    """Parser error for malformed .vibe programs with location diagnostics."""

    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        self.line = line
        self.column = column
        if line is not None and column is not None:
            super().__init__(f"Line {line}, Col {column}: {message}")
        else:
            super().__init__(message)


@dataclass(slots=True)
class LineToken:
    text: str
    line: int
    indent: int


def _line_col_from_index(source: str, idx: int) -> tuple[int, int]:
    line = source.count("\n", 0, idx) + 1
    last_nl = source.rfind("\n", 0, idx)
    col = idx + 1 if last_nl == -1 else idx - last_nl
    return line, col


def _extract_brace_block(source: str, name: str) -> tuple[str | None, str]:
    marker = f"{name} {{"
    start = source.find(marker)
    if start == -1:
        return None, source

    i = start + len(marker)
    depth = 1
    while i < len(source) and depth > 0:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1

    if depth != 0:
        line, col = _line_col_from_index(source, start)
        raise ParseError(f"Malformed `{name}` block: missing closing `}}`", line, col)

    inner = source[start + len(marker) : i - 1]
    stripped = source[:start] + "\n" + source[i:]
    return inner, stripped


def _tokenize_lines(source: str) -> list[LineToken]:
    out: list[LineToken] = []
    for ln, raw in enumerate(source.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ParseError("Indentation must be multiples of 2 spaces", ln, indent + 1)
        out.append(LineToken(text=raw.strip(), line=ln, indent=indent))
    return out


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"true", "yes", "1"}


def _parse_list(raw: str) -> list[str]:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [x.strip() for x in inner.split(",")]
    return [x.strip() for x in value.split(",") if x.strip()]


def _parse_frequency(raw: str) -> float:
    nums = re.findall(r"\d+(?:\.\d+)?", raw)
    return float(nums[0]) if nums else 0.0


def _parse_rule(line: str, line_no: int) -> PreserveRule:
    for op in COMPARISON_OPS:
        if op in line:
            key, value = [x.strip() for x in line.split(op, 1)]
            if key and value:
                return PreserveRule(key=key, op=op, value=value)
    raise ParseError(f"Invalid preserve rule `{line}`. Expected `<key> <op> <value>`", line_no, 1)


def _parse_field(line: str, line_no: int) -> Field:
    if ":" not in line:
        raise ParseError("Expected field declaration `name: type`", line_no, 1)
    name, type_name = [x.strip() for x in line.split(":", 1)]
    if not name or not type_name:
        raise ParseError("Invalid field declaration; both name and type are required", line_no, 1)
    return Field(name=name, type_name=type_name)


def _parse_kv_lines(text: str, context: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if ":" not in line:
            raise ParseError(f"Malformed line in {context}: `{line}`. Expected `key: value`", i, 1)
        key, value = [x.strip() for x in line.split(":", 1)]
        out[key] = value
    return out


def _parse_tesla(inner: str) -> TeslaVictoryLayer:
    arc_raw, rem = _extract_brace_block(inner, "arc.tower.coherence")
    life_raw, rem = _extract_brace_block(rem, "life.ray.vitalize")
    breath_raw, _ = _extract_brace_block(rem, "breath.cycle")
    if not arc_raw or not life_raw or not breath_raw:
        raise ParseError(
            "experimental.tesla.victory.layer requires arc.tower.coherence, life.ray.vitalize, and breath.cycle"
        )

    arc_kv = _parse_kv_lines(arc_raw, "arc.tower.coherence")
    life_kv = _parse_kv_lines(life_raw, "life.ray.vitalize")
    breath_kv = _parse_kv_lines(breath_raw, "breath.cycle")

    return TeslaVictoryLayer(
        arc_tower=TeslaArcTower(
            global_resonance=_parse_bool(arc_kv.get("global.resonance", "false")),
            substrate_bridge=_parse_list(arc_kv.get("substrate.bridge", "[]")),
            preserve_epsilon=_parse_bool(arc_kv.get("preserve.epsilon", "false")),
            preserve_sovereignty=_parse_bool(arc_kv.get("preserve.sovereignty", "false")),
        ),
        life_ray=TeslaLifeRay(
            bio_field=life_kv.get("bio.field", "human"),
            baseline_frequency_hz=_parse_frequency(life_kv.get("baseline.frequency", "0")),
            harmonic_mode=life_kv.get("harmonic.mode", ""),
            intention=life_kv.get("intention", ""),
        ),
        breath_cycle=TeslaBreathCycle(
            pralaya_inhalation=breath_kv.get("pralaya.inhalation", ""),
            kalpa_exhalation=breath_kv.get("kalpa.exhalation", ""),
            c_star_target=breath_kv.get("c_star.target", ""),
            monitor=breath_kv.get("monitor", ""),
        ),
    )


def _parse_agentora(inner: str) -> AgentoraBlock:
    agents: list[AgentDefinition] = []
    remaining = inner
    while True:
        m = re.search(r"agent\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", remaining)
        if not m:
            break
        name = m.group(1)
        block, stripped = _extract_brace_block(remaining[m.start() :], f"agent {name}")
        if block is None:
            raise ParseError(f"Malformed agent block for `{name}`")
        kv = _parse_kv_lines(block, f"agent {name}")
        if "role" not in kv or "intention" not in kv:
            raise ParseError(f"agent {name} requires `role` and `intention`")
        agents.append(
            AgentDefinition(
                name=name,
                role=kv["role"],
                tools=_parse_list(kv.get("tools", "[]")),
                memory=kv.get("memory", "session"),
                intention=kv["intention"],
                constraints=_parse_list(kv.get("constraints", "[]")),
                preserve=_parse_list(kv.get("preserve", "[]")),
            )
        )
        remaining = remaining[: m.start()] + stripped

    if not agents:
        raise ParseError("agentora requires at least one `agent <Name> { ... }` block")
    return AgentoraBlock(agents=agents)


def _parse_agentception(inner: str) -> AgentceptionBlock:
    kv = _parse_kv_lines(inner, "agentception")
    return AgentceptionBlock(
        enabled=_parse_bool(kv.get("enabled", "false")),
        max_depth=int(float(kv.get("max.depth", "0"))),
        spawn_policy=kv.get("spawn.policy", ""),
        inherit_preserve=_parse_bool(kv.get("inherit.preserve", "false")),
        inherit_constraints=_parse_bool(kv.get("inherit.constraints", "false")),
        inherit_bridge=_parse_bool(kv.get("inherit.bridge", "false")),
        merge_strategy=kv.get("merge.strategy", ""),
        stop_when=kv.get("stop.when", ""),
    )


def parse_source(source: str) -> Program:
    """Parse raw source text into an AST Program using the formal grammar."""

    # Grammar source of truth is kept in vibe.grammar.GRAMMAR.
    tesla_raw, trimmed = _extract_brace_block(source, "experimental.tesla.victory.layer")
    agentora_raw, trimmed = _extract_brace_block(trimmed, "agentora")
    agentception_raw, trimmed = _extract_brace_block(trimmed, "agentception")

    tokens = _tokenize_lines(trimmed)
    if not tokens:
        raise ParseError("Empty file; expected at least an intent block", 1, 1)

    i = 0
    vibe_version: str | None = None
    imports: list[str] = []
    modules: list[str] = []
    types: list[str] = []
    enums: list[str] = []
    interfaces: list[str] = []

    while i < len(tokens) and tokens[i].text.startswith(PRELUDE_PREFIXES):
        tk = tokens[i]
        if tk.indent != 0:
            raise ParseError("Top-level declarations cannot be indented", tk.line, tk.indent + 1)
        if tk.text.startswith("vibe_version "):
            vibe_version = tk.text.split(maxsplit=1)[1].strip()
        elif tk.text.startswith("import "):
            imports.append(tk.text.split(maxsplit=1)[1].strip())
        elif tk.text.startswith("module "):
            modules.append(tk.text.split(maxsplit=1)[1].strip())
        elif tk.text.startswith("type "):
            types.append(tk.text.split(maxsplit=1)[1].strip())
        elif tk.text.startswith("enum "):
            enums.append(tk.text.split(maxsplit=1)[1].strip())
        elif tk.text.startswith("interface "):
            interfaces.append(tk.text.split(maxsplit=1)[1].strip())
        i += 1

    intent: IntentBlock | None = None
    preserve: list[PreserveRule] = []
    constraints: list[str] = []
    bridge: list[BridgeSetting] = []
    agents: list[AgentGraphAgent] = []
    orchestrations: list[OrchestrateBlock] = []
    delegations: list[DelegationDecl] = []
    emit_target = "python"

    while i < len(tokens):
        tk = tokens[i]
        if tk.indent != 0:
            raise ParseError("Top-level block must not be indented", tk.line, tk.indent + 1)

        if tk.text.startswith("intent ") and tk.text.endswith(":"):
            if intent is not None:
                raise ParseError("Duplicate intent block", tk.line, 1)
            intent_name = tk.text[len("intent ") : -1].strip()
            i += 1
            goal = ""
            inputs: list[Field] = []
            outputs: list[Field] = []
            section: str | None = None
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent == 2 and cur.text in {"inputs:", "outputs:"}:
                    section = cur.text[:-1]
                    i += 1
                    continue
                if cur.indent == 2 and cur.text.startswith("goal:"):
                    goal = cur.text.split(":", 1)[1].strip().strip('"')
                    i += 1
                    continue
                if cur.indent == 4 and section in {"inputs", "outputs"}:
                    fld = _parse_field(cur.text, cur.line)
                    (inputs if section == "inputs" else outputs).append(fld)
                    i += 1
                    continue
                raise ParseError("Malformed intent block item", cur.line, cur.indent + 1)
            if not goal:
                raise ParseError("Intent missing `goal:`", tk.line, 1)
            intent = IntentBlock(name=intent_name, goal=goal, inputs=inputs, outputs=outputs)
            continue

        if tk.text == "preserve:":
            i += 1
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2:
                    raise ParseError("Malformed preserve rule indentation", cur.line, cur.indent + 1)
                preserve.append(_parse_rule(cur.text, cur.line))
                i += 1
            continue

        if tk.text == "constraint:":
            i += 1
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2:
                    raise ParseError("Malformed constraint indentation", cur.line, cur.indent + 1)
                constraints.append(cur.text)
                i += 1
            continue

        if tk.text == "bridge:":
            i += 1
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2 or "=" not in cur.text:
                    raise ParseError("Malformed bridge setting; expected `key = value`", cur.line, cur.indent + 1)
                key, value = [x.strip() for x in cur.text.split("=", 1)]
                bridge.append(BridgeSetting(key=key, value=value))
                i += 1
            continue

        if tk.text.startswith("agent ") and tk.text.endswith(":"):
            agent_name = tk.text[len("agent ") : -1].strip()
            i += 1
            role = ""
            receives = ""
            emits = ""
            agent_preserve: list[str] = []
            agent_constraints: list[str] = []
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2:
                    raise ParseError("Malformed agent block indentation", cur.line, cur.indent + 1)
                if cur.text.startswith("role:"):
                    role = cur.text.split(":", 1)[1].strip().strip('"')
                elif cur.text.startswith("receives:"):
                    receives = cur.text.split(":", 1)[1].strip()
                elif cur.text.startswith("emits:"):
                    emits = cur.text.split(":", 1)[1].strip()
                elif cur.text.startswith("preserve:"):
                    agent_preserve.append(cur.text.split(":", 1)[1].strip())
                elif cur.text.startswith("constraint:"):
                    agent_constraints.append(cur.text.split(":", 1)[1].strip())
                else:
                    raise ParseError("Malformed agent block item", cur.line, cur.indent + 1)
                i += 1
            if not role or not receives or not emits:
                raise ParseError("agent block requires role/receives/emits", tk.line, 1)
            agents.append(
                AgentGraphAgent(
                    name=agent_name,
                    role=role,
                    receives=receives,
                    emits=emits,
                    preserve=agent_preserve,
                    constraints=agent_constraints,
                )
            )
            continue

        if tk.text.startswith("orchestrate ") and tk.text.endswith(":"):
            orch_name = tk.text[len("orchestrate ") : -1].strip()
            i += 1
            edges: list[OrchestrationEdge] = []
            on_error: str | None = None
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2:
                    raise ParseError("Malformed orchestrate block indentation", cur.line, cur.indent + 1)
                if cur.text.startswith("on_error:"):
                    on_error = cur.text.split(":", 1)[1].strip()
                    i += 1
                    continue
                if "->" not in cur.text:
                    raise ParseError("Malformed orchestrate edge; expected `AgentA -> AgentB`", cur.line, cur.indent + 1)
                src, dst = [x.strip() for x in cur.text.split("->", 1)]
                if not src or not dst:
                    raise ParseError("Malformed orchestrate edge; both source and target required", cur.line, cur.indent + 1)
                edges.append(OrchestrationEdge(source=src, target=dst))
                i += 1
            orchestrations.append(OrchestrateBlock(name=orch_name, edges=edges, on_error=on_error))
            continue

        if tk.text.startswith("delegate ") and tk.text.endswith(":"):
            head = tk.text[len("delegate ") : -1].strip()
            if "->" not in head:
                raise ParseError("Malformed delegate header; expected `delegate Parent -> Child:`", tk.line, 1)
            parent, child = [x.strip() for x in head.split("->", 1)]
            if not parent or not child:
                raise ParseError("Malformed delegate header; both parent and child required", tk.line, 1)
            i += 1
            inherits: list[str] = ["preserve", "constraint", "bridge"]
            max_depth: int | None = None
            stop_when: str | None = None
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2:
                    raise ParseError("Malformed delegate block indentation", cur.line, cur.indent + 1)
                if cur.text.startswith("inherits:"):
                    inherits = _parse_list(cur.text.split(":", 1)[1].strip())
                elif cur.text.startswith("max_depth:"):
                    max_depth = int(float(cur.text.split(":", 1)[1].strip()))
                elif cur.text.startswith("stop_when:"):
                    stop_when = cur.text.split(":", 1)[1].strip()
                else:
                    raise ParseError("Malformed delegate block item", cur.line, cur.indent + 1)
                i += 1
            delegations.append(
                DelegationDecl(parent=parent, child=child, inherits=[x.strip() for x in inherits], max_depth=max_depth, stop_when=stop_when)
            )
            continue

        if tk.text.startswith("emit "):
            emit_target = tk.text.split(maxsplit=1)[1].strip()
            i += 1
            continue

        raise ParseError(f"Unknown top-level statement `{tk.text}`", tk.line, 1)

    if intent is None:
        raise ParseError("Program missing required intent block", 1, 1)

    program = Program(
        intent=intent,
        preserve=preserve,
        constraints=constraints,
        bridge=bridge,
        emit_target=emit_target,
        vibe_version=vibe_version,
        imports=imports,
        modules=modules,
        types=types,
        enums=enums,
        interfaces=interfaces,
        agents=agents,
        orchestrations=orchestrations,
        delegations=delegations,
    )

    if tesla_raw is not None:
        program.tesla_victory_layer = _parse_tesla(tesla_raw)
    if agentora_raw is not None:
        program.agentora = _parse_agentora(agentora_raw)
    if agentception_raw is not None:
        program.agentception = _parse_agentception(agentception_raw)

    return program
