from __future__ import annotations

from pathlib import Path

from ..manifest import load_manifest
from ..phipython import snippet_completion_items


_KEYWORDS = [
    "intent",
    "preserve:",
    "constraint:",
    "bridge:",
    "emit python",
    "emit typescript",
    "import",
    "module",
    "type",
    "enum",
    "interface",
    "agent",
    "orchestrate",
    "delegate",
]

_BRIDGE_KEYS = ["epsilon_floor", "measurement_safe_ratio", "mode"]
_PRESERVE_HINTS = ["latency < 200ms", "failure_rate < 0.01", "compliance = strict"]


def _import_completions(path: Path | None) -> list[str]:
    if path is None:
        return []
    roots = [path.parent, *path.parents]
    manifest_path = next((p / "vibe.toml" for p in roots if (p / "vibe.toml").exists()), None)
    if manifest_path is None:
        return []

    manifest = load_manifest(manifest_path)
    items = []
    src = manifest_path.parent / "src"
    if src.exists():
        for vibe_file in sorted(src.glob("**/*.vibe")):
            rel = vibe_file.relative_to(src).with_suffix("")
            items.append(".".join(rel.parts))
    items.extend(sorted(manifest.dependencies.keys()))
    return sorted(set(items))


def completions(prefix: str, path: Path | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    prefix_norm = prefix.strip().lower()

    for item in _KEYWORDS + _BRIDGE_KEYS + _PRESERVE_HINTS:
        if not prefix_norm or item.lower().startswith(prefix_norm) or prefix_norm in item.lower():
            rows.append({"label": item, "kind": 14, "detail": "Vibe keyword/snippet"})

    for imp in _import_completions(path):
        if not prefix_norm or imp.lower().startswith(prefix_norm):
            rows.append({"label": imp, "kind": 9, "detail": "package-local import"})

    if path is not None and path.suffix == ".py":
        rows.extend(snippet_completion_items(prefix_norm))

    return sorted(rows, key=lambda r: (str(r["label"]), str(r.get("detail", ""))))
