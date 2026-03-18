"""Parser for .vibe sources."""

from __future__ import annotations

import re

from .ast import (
    AgentDefinition,
    AgentceptionBlock,
    AgentoraBlock,
    BridgeSetting,
    Field,
    IntentBlock,
    PreserveRule,
    Program,
    TeslaArcTower,
    TeslaBreathCycle,
    TeslaLifeRay,
    TeslaVictoryLayer,
)
from .lexer import Token, lex

COMPARISON_OPS = ("<=", ">=", "<", ">", "=")


class ParseError(ValueError):
    """Parser error for malformed .vibe programs."""


def _expect_line(tokens: list[Token], i: int) -> Token:
    if i >= len(tokens):
        raise ParseError("Unexpected end of file")
    return tokens[i]


def _parse_field(line: str, line_no: int) -> Field:
    if ":" not in line:
        raise ParseError(f"Line {line_no}: expected `name: type`")
    name, type_name = [x.strip() for x in line.split(":", 1)]
    if not name or not type_name:
        raise ParseError(f"Line {line_no}: invalid field declaration")
    return Field(name=name, type_name=type_name)


def _parse_rule(line: str, line_no: int) -> PreserveRule:
    for op in COMPARISON_OPS:
        if op in line:
            key, value = [x.strip() for x in line.split(op, 1)]
            if not key or not value:
                break
            return PreserveRule(key=key, op=op, value=value)
    raise ParseError(f"Line {line_no}: invalid preserve rule `{line}`")


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"true", "yes", "1"}


def _extract_block(source: str, name: str) -> tuple[str | None, str]:
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
        raise ParseError(f"Malformed block for {name}: unbalanced braces")

    inner = source[start + len(marker) : i - 1]
    stripped = source[:start] + "\n" + source[i:]
    return inner, stripped


def _parse_kv_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" not in line:
            raise ParseError(f"Malformed experimental line: `{line}`")
        k, v = [x.strip() for x in line.split(":", 1)]
        out[k] = v
    return out


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


def _parse_tesla(inner: str) -> TeslaVictoryLayer:
    arc_raw, rem = _extract_block(inner, "arc.tower.coherence")
    life_raw, rem = _extract_block(rem, "life.ray.vitalize")
    breath_raw, rem = _extract_block(rem, "breath.cycle")
    if not arc_raw or not life_raw or not breath_raw:
        raise ParseError("Tesla Victory Layer requires arc.tower.coherence, life.ray.vitalize, and breath.cycle")

    arc_kv = _parse_kv_lines(arc_raw)
    life_kv = _parse_kv_lines(life_raw)
    breath_kv = _parse_kv_lines(breath_raw)

    arc = TeslaArcTower(
        global_resonance=_parse_bool(arc_kv.get("global.resonance", "false")),
        substrate_bridge=_parse_list(arc_kv.get("substrate.bridge", "[]")),
        preserve_epsilon=_parse_bool(arc_kv.get("preserve.epsilon", "false")),
        preserve_sovereignty=_parse_bool(arc_kv.get("preserve.sovereignty", "false")),
    )
    life = TeslaLifeRay(
        bio_field=life_kv.get("bio.field", "human"),
        baseline_frequency_hz=_parse_frequency(life_kv.get("baseline.frequency", "0")),
        harmonic_mode=life_kv.get("harmonic.mode", ""),
        intention=life_kv.get("intention", ""),
    )
    breath = TeslaBreathCycle(
        pralaya_inhalation=breath_kv.get("pralaya.inhalation", ""),
        kalpa_exhalation=breath_kv.get("kalpa.exhalation", ""),
        c_star_target=breath_kv.get("c_star.target", ""),
        monitor=breath_kv.get("monitor", ""),
    )
    return TeslaVictoryLayer(arc_tower=arc, life_ray=life, breath_cycle=breath)


def _parse_agentora(inner: str) -> AgentoraBlock:
    agents: list[AgentDefinition] = []
    remaining = inner
    while True:
        match = re.search(r"agent\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", remaining)
        if not match:
            break
        name = match.group(1)
        start = match.start()
        block, stripped = _extract_block(remaining[start:], f"agent {name}")
        if block is None:
            raise ParseError("Malformed agent block")
        kv = _parse_kv_lines(block)
        if "role" not in kv or "intention" not in kv:
            raise ParseError(f"agent {name} requires role and intention")
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
        remaining = remaining[:start] + stripped
    if not agents:
        raise ParseError("agentora requires at least one agent block")
    return AgentoraBlock(agents=agents)


def _parse_agentception(inner: str) -> AgentceptionBlock:
    kv = _parse_kv_lines(inner)
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
    """Parse raw source text into an AST Program."""

    tesla_raw, trimmed = _extract_block(source, "experimental.tesla.victory.layer")
    agentora_raw, trimmed = _extract_block(trimmed, "agentora")
    agentception_raw, trimmed = _extract_block(trimmed, "agentception")

    program = parse_tokens(lex(trimmed))
    if tesla_raw is not None:
        program.tesla_victory_layer = _parse_tesla(tesla_raw)
    if agentora_raw is not None:
        program.agentora = _parse_agentora(agentora_raw)
    if agentception_raw is not None:
        program.agentception = _parse_agentception(agentception_raw)
    return program


def parse_tokens(tokens: list[Token]) -> Program:
    i = 0
    intent: IntentBlock | None = None
    preserve: list[PreserveRule] = []
    constraints: list[str] = []
    bridge: list[BridgeSetting] = []
    emit_target = "python"

    while i < len(tokens):
        tk = tokens[i]
        if tk.indent != 0:
            raise ParseError(f"Line {tk.line}: top-level block must not be indented")

        if tk.kind == "BLOCK" and tk.value.startswith("intent "):
            if intent is not None:
                raise ParseError(f"Line {tk.line}: duplicate intent block")
            intent_name = tk.value.removeprefix("intent ").strip()
            i += 1
            goal = ""
            inputs: list[Field] = []
            outputs: list[Field] = []
            section: str | None = None
            while i < len(tokens) and tokens[i].indent > 0:
                cur = tokens[i]
                if cur.indent != 2 and section in {"inputs", "outputs"} and cur.indent != 4:
                    raise ParseError(f"Line {cur.line}: invalid indentation in intent block")
                if cur.indent == 2 and cur.kind == "BLOCK" and cur.value in {"inputs", "outputs"}:
                    section = cur.value
                    i += 1
                    continue
                if cur.indent == 2 and cur.kind == "LINE" and cur.value.startswith("goal:"):
                    goal = cur.value.split(":", 1)[1].strip().strip('"')
                    i += 1
                    continue
                if cur.indent == 4 and cur.kind == "LINE" and section in {"inputs", "outputs"}:
                    fld = _parse_field(cur.value, cur.line)
                    (inputs if section == "inputs" else outputs).append(fld)
                    i += 1
                    continue
                raise ParseError(f"Line {cur.line}: malformed intent block")

            if not goal:
                raise ParseError(f"Line {tk.line}: intent missing goal")
            intent = IntentBlock(name=intent_name, goal=goal, inputs=inputs, outputs=outputs)
            continue

        if tk.kind == "BLOCK" and tk.value == "preserve":
            i += 1
            while i < len(tokens) and tokens[i].indent > 0:
                cur = _expect_line(tokens, i)
                if cur.indent != 2 or cur.kind != "LINE":
                    raise ParseError(f"Line {cur.line}: malformed preserve rule")
                preserve.append(_parse_rule(cur.value, cur.line))
                i += 1
            continue

        if tk.kind == "BLOCK" and tk.value == "constraint":
            i += 1
            while i < len(tokens) and tokens[i].indent > 0:
                cur = _expect_line(tokens, i)
                if cur.indent != 2 or cur.kind != "LINE":
                    raise ParseError(f"Line {cur.line}: malformed constraint")
                constraints.append(cur.value)
                i += 1
            continue

        if tk.kind == "BLOCK" and tk.value == "bridge":
            i += 1
            while i < len(tokens) and tokens[i].indent > 0:
                cur = _expect_line(tokens, i)
                if cur.indent != 2 or cur.kind != "LINE" or "=" not in cur.value:
                    raise ParseError(f"Line {cur.line}: malformed bridge setting")
                key, value = [x.strip() for x in cur.value.split("=", 1)]
                bridge.append(BridgeSetting(key=key, value=value))
                i += 1
            continue

        if tk.kind == "LINE" and tk.value.startswith("emit "):
            emit_target = tk.value.split(maxsplit=1)[1].strip()
            i += 1
            continue

        raise ParseError(f"Line {tk.line}: unknown top-level block `{tk.value}`")

    if intent is None:
        raise ParseError("Program missing required intent block")

    return Program(intent=intent, preserve=preserve, constraints=constraints, bridge=bridge, emit_target=emit_target)
