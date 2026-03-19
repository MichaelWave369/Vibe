from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(slots=True)
class Symbol:
    name: str
    kind: str
    line: int
    character: int
    length: int


_DECL_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("intent", re.compile(r"^intent\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$"), "class"),
    ("module", re.compile(r"^module\s+(.+)$"), "module"),
    ("type", re.compile(r"^type\s+(.+)$"), "class"),
    ("enum", re.compile(r"^enum\s+(.+)$"), "enum"),
    ("interface", re.compile(r"^interface\s+(.+)$"), "interface"),
    ("agent", re.compile(r"^agent\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$"), "class"),
    ("orchestrate", re.compile(r"^orchestrate\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$"), "function"),
]


_LSP_SYMBOL_KIND = {
    "file": 1,
    "module": 2,
    "namespace": 3,
    "class": 5,
    "method": 6,
    "property": 7,
    "field": 8,
    "function": 12,
    "variable": 13,
    "enum": 10,
    "interface": 11,
}


def _line_leading_char(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def collect_symbols(source: str) -> list[Symbol]:
    out: list[Symbol] = []
    for idx, raw in enumerate(source.splitlines()):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for _, pat, kind in _DECL_PATTERNS:
            m = pat.match(line)
            if m:
                name = m.group(1).strip()
                out.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        line=idx,
                        character=_line_leading_char(raw),
                        length=max(1, len(name)),
                    )
                )
                break
    return sorted(out, key=lambda s: (s.line, s.character, s.name))


def document_symbols(source: str) -> list[dict[str, object]]:
    items = collect_symbols(source)
    return [
        {
            "name": s.name,
            "kind": _LSP_SYMBOL_KIND.get(s.kind, 13),
            "range": {
                "start": {"line": s.line, "character": s.character},
                "end": {"line": s.line, "character": s.character + s.length},
            },
            "selectionRange": {
                "start": {"line": s.line, "character": s.character},
                "end": {"line": s.line, "character": s.character + s.length},
            },
        }
        for s in items
    ]


def find_definition(source: str, word: str) -> dict[str, int] | None:
    for s in collect_symbols(source):
        if s.name == word:
            return {
                "line": s.line,
                "character": s.character,
                "end_character": s.character + s.length,
            }
    return None
