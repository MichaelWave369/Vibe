from __future__ import annotations

import re

from ..ir import ast_to_ir
from ..parser import ParseError, parse_source
from ..phipython import explanation_for_keyword, get_snippet


_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")


def _word_at_line(line: str, character: int) -> str | None:
    for m in _WORD.finditer(line):
        if m.start() <= character <= m.end():
            return m.group(0)
    return None


def hover_content(source: str, line: int, character: int) -> dict[str, object] | None:
    lines = source.splitlines()
    if line < 0 or line >= len(lines):
        return None
    token = _word_at_line(lines[line], character)
    if not token:
        return None

    try:
        ir = ast_to_ir(parse_source(source))
    except ParseError:
        return {
            "contents": {"kind": "markdown", "value": f"`{token}`\n\nParse errors prevent semantic hover."}
        }

    detail: list[str] = [f"### `{token}`"]

    if token == ir.intent_name:
        detail.append(f"- goal: {ir.goal}")
        detail.append(f"- emit: `{ir.emit_target}`")
        detail.append(f"- bridge: `{ir.bridge_config}`")
    if token in ir.inputs:
        detail.append(f"- declared input type: `{ir.inputs[token]}`")
    if token in ir.outputs:
        detail.append(f"- declared output type: `{ir.outputs[token]}`")

    sem = ir.module.semantic_summary
    eff = ir.module.effect_summary
    res = ir.module.resource_summary
    inf = ir.module.inference_summary

    if sem:
        detail.append(f"- semantic qualifiers: `{sem}`")
    if eff:
        detail.append(f"- effect profile: `{eff}`")
    if res:
        detail.append(f"- resource profile: `{res}`")
    if inf:
        detail.append(f"- inference summary: `{inf}`")

    if ir.module.agent_graph_summary:
        detail.append(f"- agent graph: `{ir.module.agent_graph_summary}`")
    if ir.module.delegation_summary:
        detail.append(f"- delegation: `{ir.module.delegation_summary}`")

    return {
        "contents": {
            "kind": "markdown",
            "value": "\n".join(detail),
        }
    }


def python_hover_content(source: str, line: int, character: int) -> dict[str, object] | None:
    """Bounded hover help for Python documents (keywords + PhiPython snippets)."""

    lines = source.splitlines()
    if line < 0 or line >= len(lines):
        return None
    token = _word_at_line(lines[line], character)
    if not token:
        return None

    keyword_help = explanation_for_keyword(token)
    if keyword_help is not None:
        return {"contents": {"kind": "markdown", "value": f"### `{token}`\n\n{keyword_help}"}}

    snippet = get_snippet(token)
    if snippet is not None:
        return {
            "contents": {
                "kind": "markdown",
                "value": (
                    f"### PhiPython snippet `{snippet.trigger}`\n\n"
                    f"- category: `{snippet.category}`\n"
                    f"- description: {snippet.description}\n"
                    f"- tags: {', '.join(snippet.tags) if snippet.tags else 'none'}"
                ),
            }
        }

    return None
