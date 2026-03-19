"""Simple hand-written lexer for indentation-based .vibe files."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Token:
    kind: str
    value: str
    line: int
    indent: int


def lex(source: str) -> list[Token]:
    """Convert source text into line-oriented tokens.

    The lexer intentionally remains lightweight for v0.1 and emits one logical
    token per non-empty, non-comment line with indentation preserved.
    """

    tokens: list[Token] = []
    for line_no, raw in enumerate(source.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"Line {line_no}: indentation must use multiples of 2 spaces")
        stripped = raw.strip()
        if stripped.endswith(":"):
            tokens.append(Token("BLOCK", stripped[:-1], line_no, indent))
        else:
            tokens.append(Token("LINE", stripped, line_no, indent))
    return tokens
