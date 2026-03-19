from __future__ import annotations

from ..ir import ast_to_ir
from ..parser import ParseError, parse_source


def intent_lenses(source: str) -> list[dict[str, object]]:
    try:
        ir = ast_to_ir(parse_source(source))
    except ParseError:
        return []

    bridge = ir.bridge_config
    lenses = [
        {
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
            "command": {
                "title": f"bridge safe_ratio={bridge.get('measurement_safe_ratio')} epsilon_floor={bridge.get('epsilon_floor')}",
                "command": "vibe.lens.bridge",
                "arguments": [bridge],
            },
        }
    ]
    if ir.module.semantic_summary:
        lenses.append(
            {
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
                "command": {
                    "title": f"semantic summary: {ir.module.semantic_summary}",
                    "command": "vibe.lens.semantic",
                    "arguments": [ir.module.semantic_summary],
                },
            }
        )
    if ir.module.agent_boundary_summary:
        lenses.append(
            {
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
                "command": {
                    "title": f"agent boundary: {ir.module.agent_boundary_summary}",
                    "command": "vibe.lens.agent_boundary",
                    "arguments": [ir.module.agent_boundary_summary],
                },
            }
        )
    return lenses
