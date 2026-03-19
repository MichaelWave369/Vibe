from __future__ import annotations

from pathlib import Path

from .symbols import find_definition


def _word_at(text: str, line: int, character: int) -> str | None:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    raw = lines[line]
    if not raw:
        return None
    start = character
    while start > 0 and (raw[start - 1].isalnum() or raw[start - 1] in {"_", "."}):
        start -= 1
    end = character
    while end < len(raw) and (raw[end].isalnum() or raw[end] in {"_", "."}):
        end += 1
    word = raw[start:end].strip()
    return word or None


def definition_location(uri: str, source: str, line: int, character: int, path: Path | None = None) -> dict[str, object] | None:
    word = _word_at(source, line, character)
    if not word:
        return None

    local = find_definition(source, word)
    if local is not None:
        return {
            "uri": uri,
            "range": {
                "start": {"line": local["line"], "character": local["character"]},
                "end": {"line": local["line"], "character": local["end_character"]},
            },
        }

    if path is not None:
        parts = [p for p in word.split(".") if p]
        if parts:
            for root in [path.parent, *path.parents]:
                candidates = [root / "src" / Path(*parts).with_suffix(".vibe")]
                if len(parts) == 1:
                    candidates.append(root / "src" / f"{parts[0]}.vibe")
                for src in candidates:
                    if src.exists():
                        return {
                            "uri": src.as_uri(),
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 1},
                            },
                        }

    return None
