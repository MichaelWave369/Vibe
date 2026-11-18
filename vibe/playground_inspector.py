"""Best-effort VibeWeb declaration-to-generated-markup inspector.

This is a navigation aid built only after parsing/compiling succeeds.
It is explicitly NOT a complete source map for all compiler instructions.
"""
from __future__ import annotations

from html import escape as html_escape
import re


def build_outline(source: str, html: str) -> list[dict[str, object]]:
    """Return bounded source declaration anchors and first generated HTML matches."""
    result: list[dict[str, object]] = []
    html_lines = html.splitlines()
    anchors = {
        "page": "<main",
        "title": "<title>",
        "heading": "<h1>",
        "layout": 'class="vibe-layout',
        "components": 'class="vibe-component"',
        "view": 'class="vibe-layout',
        "typing": '<section id="vibe-typing"',
        "submit": '<button type="submit"',
        "state": 'id="vibe-config"',
        "text_state": 'id="vibe-config"',
        "bounds": 'id="vibe-config"',
    }
    allowed = set(anchors) | {"intent", "component", "lesson"}
    for index, raw in enumerate(source.splitlines(), 1):
        if len(result) >= 80:
            break
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        keyword = line.split(maxsplit=1)[0].rstrip(":")
        if keyword not in allowed:
            continue
        if keyword == "intent":
            match = re.fullmatch(r"intent\s+([A-Za-z_][A-Za-z0-9_]*):", line)
            if not match:
                continue
            label = match.group(1)
            anchor = None
        elif keyword == "page":
            match = re.fullmatch(r"page\s+([A-Za-z_][A-Za-z0-9_]*):", line)
            if not match:
                continue
            label = match.group(1)
            anchor = anchors["page"]
        elif keyword == "component":
            match = re.fullmatch(r"component\s+([A-Za-z_][A-Za-z0-9_]*):", line)
            if not match:
                continue
            label = match.group(1)
            anchor = f'aria-label="{html_escape(label, quote=True)}"'
        elif keyword == "lesson":
            match = re.match(r'lesson\s+"([A-Za-z0-9][A-Za-z0-9 ._-]{1,39})"', line)
            if not match:
                continue
            label = match.group(1)
            anchor = f'>{html_escape(label)} ('
        else:
            # Strict form ensures this is a declaration, not a string literal.
            if not line.startswith(keyword + ":"):
                continue
            label = keyword.replace("_", " ")
            anchor = anchors.get(keyword)
        found = html.find(anchor) if anchor else -1
        generated_line = html.count("\n", 0, found) + 1 if found >= 0 else None
        excerpt = (
            html_lines[generated_line - 1].strip()[:150]
            if generated_line is not None and generated_line <= len(html_lines)
            else None
        )
        result.append({
            "kind": keyword,
            "name": label,
            "source_line": index,
            "html_line": generated_line,
            "html_excerpt": excerpt,
        })
    return result
