"""Parser for .vibe sources."""

from __future__ import annotations

from .ast import BridgeSetting, Field, IntentBlock, PreserveRule, Program
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


def parse_source(source: str) -> Program:
    """Parse raw source text into an AST Program."""

    return parse_tokens(lex(source))


def parse_tokens(tokens: list[Token]) -> Program:
    """Parse lexed tokens into a program AST."""

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
                if cur.indent != 2 and section in {"inputs", "outputs"}:
                    if cur.indent != 4:
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
                    if section == "inputs":
                        inputs.append(fld)
                    else:
                        outputs.append(fld)
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

    return Program(
        intent=intent,
        preserve=preserve,
        constraints=constraints,
        bridge=bridge,
        emit_target=emit_target,
    )
