from __future__ import annotations

from pathlib import Path

from ..ir import ast_to_ir
from ..manifest import load_manifest
from ..package_manager import package_context_for_path
from ..parser import ParseError, parse_source


def _diag(line: int, col: int, message: str, severity: int = 2, code: str | None = None) -> dict[str, object]:
    d: dict[str, object] = {
        "range": {
            "start": {"line": max(0, line), "character": max(0, col)},
            "end": {"line": max(0, line), "character": max(0, col + 1)},
        },
        "severity": severity,
        "source": "vibe-lsp",
        "message": message,
    }
    if code:
        d["code"] = code
    return d


def _resolve_import(package_root: Path, import_name: str, dependencies: dict[str, str]) -> Path | None:
    parts = [p for p in import_name.split(".") if p]
    if not parts:
        return None

    def _local_candidates(root: Path, segs: list[str]) -> list[Path]:
        return [
            root / "src" / Path(*segs).with_suffix(".vibe"),
            root / Path(*segs).with_suffix(".vibe"),
            root / "src" / f"{segs[-1]}.vibe",
        ]

    if parts[0] in dependencies:
        dep_spec = dependencies[parts[0]]
        dep_root = Path(dep_spec.replace("path:", "")).expanduser()
        if not dep_root.is_absolute():
            dep_root = (package_root / dep_root).resolve()
        segs = parts[1:] if len(parts) > 1 else ["main"]
        for cand in _local_candidates(dep_root, segs):
            if cand.exists():
                return cand
        return None

    for cand in _local_candidates(package_root, parts):
        if cand.exists():
            return cand
    return None


def collect_diagnostics(source: str, path: Path | None = None, include_deep: bool = False) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    try:
        program = parse_source(source)
    except ParseError as exc:
        line = (exc.line or 1) - 1
        col = (exc.column or 1) - 1
        return [_diag(line, col, str(exc), severity=1, code="parse.error")]

    ir = ast_to_ir(program)

    for group, code in [
        (ir.module.semantic_issues, "semantic.issue"),
        (ir.module.effect_issues, "effect.issue"),
        (ir.module.resource_issues, "resource.issue"),
        (ir.module.inference_issues, "inference.issue"),
        (ir.module.agent_graph_issues, "agent_graph.issue"),
        (ir.module.agent_boundary_issues, "agent_boundary.issue"),
        (ir.module.delegation_issues, "delegation.issue"),
        (ir.module.domain_issues, "domain.issue"),
        (ir.module.hardware_issues, "hardware.issue"),
    ]:
        for row in group:
            message = str(row.get("message") or row.get("issue") or row.get("issue_id") or "analysis issue")
            severity = 1 if str(row.get("severity", "")).lower() in {"critical", "high"} else 2
            issues.append(_diag(0, 0, message, severity=severity, code=code))

    if path is not None:
        pkg_ctx = package_context_for_path(path)
        package_root = path.parent
        dependencies: dict[str, str] = {}
        if pkg_ctx:
            dependencies = {str(k): str(v) for k, v in dict(pkg_ctx.get("dependencies", {})).items()}
        else:
            manifest_path = next((p / "vibe.toml" for p in [path.parent, *path.parents] if (p / "vibe.toml").exists()), None)
            if manifest_path:
                manifest = load_manifest(manifest_path)
                dependencies = dict(manifest.dependencies)
                package_root = manifest_path.parent

        for imp in sorted(program.imports):
            resolved = _resolve_import(package_root, imp, dependencies)
            if resolved is None:
                issues.append(_diag(0, 0, f"unresolved import `{imp}`", severity=1, code="import.unresolved"))

    if include_deep:
        bridge = ir.bridge_config
        safe_ratio = float(bridge.get("measurement_safe_ratio", 0.85))
        if not (0.0 < safe_ratio <= 1.0):
            issues.append(_diag(0, 0, "bridge.measurement_safe_ratio should be in (0,1]", severity=2, code="bridge.range"))

    return sorted(issues, key=lambda d: (d["range"]["start"]["line"], d["code"] or ""))
