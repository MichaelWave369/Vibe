from __future__ import annotations

import re


TOKEN_TYPES = [
    "keyword",
    "type",
    "namespace",
    "class",
    "interface",
    "enum",
    "property",
    "variable",
]

_TOKEN_TYPE_IDX = {name: idx for idx, name in enumerate(TOKEN_TYPES)}

_PATTERNS = [
    (re.compile(r"\b(intent|preserve|constraint|bridge|emit|agent|orchestrate|delegate|import|module)\b"), "keyword"),
    (re.compile(r"\b(type)\s+([A-Za-z_][A-Za-z0-9_]*)"), "type"),
    (re.compile(r"\b(interface)\s+([A-Za-z_][A-Za-z0-9_]*)"), "interface"),
    (re.compile(r"\b(enum)\s+([A-Za-z_][A-Za-z0-9_]*)"), "enum"),
    (re.compile(r"\bintent\s+([A-Za-z_][A-Za-z0-9_]*)"), "class"),
    (re.compile(r"\b(agent|orchestrate)\s+([A-Za-z_][A-Za-z0-9_]*)"), "namespace"),
]



def _push(data: list[int], prev_line: int, prev_char: int, line: int, char: int, length: int, token_type: str) -> tuple[int, int]:
    delta_line = line - prev_line
    delta_char = char - prev_char if delta_line == 0 else char
    data.extend([delta_line, delta_char, length, _TOKEN_TYPE_IDX[token_type], 0])
    return line, char



def semantic_tokens_full(source: str) -> dict[str, object]:
    encoded: list[int] = []
    prev_line = 0
    prev_char = 0
    matches: list[tuple[int, int, int, str]] = []
    for line_no, line in enumerate(source.splitlines()):
        for pat, token_type in _PATTERNS:
            for m in pat.finditer(line):
                if m.lastindex and m.lastindex >= 2:
                    start, end = m.span(2)
                else:
                    start, end = m.span(1) if m.lastindex else m.span(0)
                matches.append((line_no, start, end - start, token_type))
    for line, char, length, token_type in sorted(matches, key=lambda x: (x[0], x[1], x[3])):
        prev_line, prev_char = _push(encoded, prev_line, prev_char, line, char, length, token_type)
    return {"data": encoded, "legend": {"tokenTypes": TOKEN_TYPES, "tokenModifiers": []}}
