"""Local-first intent package manager primitives (Phase 6.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from .ast import Program
from .emitter import emit_code
from .ir import ast_to_ir
from .manifest import ManifestIssue, VibeManifest, load_manifest, validate_manifest
from .parser import parse_source
from .verifier import verify


@dataclass(slots=True)
class ResolvedPackage:
    name: str
    version: str
    root: str
    dependencies: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PackageGraph:
    root_package: str
    packages: list[ResolvedPackage] = field(default_factory=list)
    edges: list[dict[str, str]] = field(default_factory=list)
    issues: list[dict[str, object]] = field(default_factory=list)


def _dep_is_local(spec: str) -> bool:
    return spec.startswith("path:") or spec.startswith("./") or spec.startswith("../") or spec.startswith("/")


def _dep_path(base: Path, spec: str) -> Path:
    if spec.startswith("path:"):
        spec = spec[len("path:") :]
    p = Path(spec)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def resolve_package_graph(manifest_path: Path) -> PackageGraph:
    root_manifest = load_manifest(manifest_path)
    root_name = root_manifest.package_name or "<unknown>"
    packages: dict[str, ResolvedPackage] = {}
    edges: list[dict[str, str]] = []
    issues: list[dict[str, object]] = []

    visiting: set[str] = set()
    visited: set[str] = set()

    def _walk(path: Path) -> None:
        m = load_manifest(path)
        key = f"{m.package_name}@{m.package_version}"
        if key in visiting:
            issues.append({"issue_id": "package_graph.cycle", "severity": "critical", "message": f"dependency cycle detected at {key}"})
            return
        if key in visited:
            return
        visiting.add(key)
        pkg = ResolvedPackage(name=m.package_name, version=m.package_version, root=str(path.parent), dependencies=dict(m.dependencies))
        packages[key] = pkg
        for dep_name, dep_spec in sorted(m.dependencies.items()):
            if _dep_is_local(dep_spec):
                dep_root = _dep_path(path.parent, dep_spec)
                dep_manifest = dep_root / "vibe.toml"
                if not dep_manifest.exists():
                    issues.append(
                        {
                            "issue_id": f"dependency.unresolved.{dep_name}",
                            "severity": "critical",
                            "message": "local dependency manifest not found",
                            "evidence": str(dep_manifest),
                        }
                    )
                    continue
                dep_obj = load_manifest(dep_manifest)
                edges.append({"from": m.package_name, "to": dep_obj.package_name, "spec": dep_spec})
                _walk(dep_manifest)
            else:
                edges.append({"from": m.package_name, "to": dep_name, "spec": dep_spec})
                issues.append(
                    {
                        "issue_id": f"dependency.remote_placeholder.{dep_name}",
                        "severity": "medium",
                        "message": "remote dependency spec recorded but registry resolution is not implemented in this phase",
                    }
                )
        visiting.remove(key)
        visited.add(key)

    _walk(manifest_path.resolve())
    resolved_packages = sorted(packages.values(), key=lambda p: (p.name, p.version))
    versions_by_name: dict[str, set[str]] = {}
    for pkg in resolved_packages:
        versions_by_name.setdefault(pkg.name, set()).add(pkg.version)
    for name, versions in sorted(versions_by_name.items()):
        if len(versions) > 1:
            issues.append(
                {
                    "issue_id": f"dependency.version_conflict.{name}",
                    "severity": "high",
                    "message": f"multiple versions resolved for package `{name}`: {sorted(versions)}",
                }
            )
    return PackageGraph(root_package=root_name, packages=resolved_packages, edges=edges, issues=issues)


def apply_package_defaults_to_source(source: str, manifest: VibeManifest) -> str:
    lines = source.splitlines()
    has_bridge = any(line.strip() == "bridge:" for line in lines)
    has_emit = any(line.strip().startswith("emit ") for line in lines)

    bridge_defaults = dict(manifest.bridge_defaults)
    emit_default = str(manifest.emit_defaults.get("default_target", "")).strip()

    if not has_bridge and bridge_defaults:
        lines.extend(["", "bridge:"])
        for key, value in sorted(bridge_defaults.items()):
            lines.append(f"  {key} = {value}")
    elif has_bridge and bridge_defaults:
        bridge_idx = next(i for i, line in enumerate(lines) if line.strip() == "bridge:")
        block_end = bridge_idx + 1
        while block_end < len(lines) and (lines[block_end].startswith("  ") or not lines[block_end].strip()):
            block_end += 1
        existing = {lines[i].split("=", 1)[0].strip() for i in range(bridge_idx + 1, block_end) if "=" in lines[i]}
        inserts = [f"  {k} = {v}" for k, v in sorted(bridge_defaults.items()) if k not in existing]
        if inserts:
            lines[block_end:block_end] = inserts

    if not has_emit and emit_default:
        lines.extend(["", f"emit {emit_default}"])

    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")


def discover_package_modules(package_root: Path) -> list[Path]:
    src = package_root / "src"
    if src.exists():
        files = sorted(p for p in src.glob("**/*.vibe") if p.is_file())
        if files:
            return files
    return sorted(p for p in package_root.glob("*.vibe") if p.is_file())


def _resolve_import_to_module(package_root: Path, module_name: str) -> Path | None:
    parts = [p for p in module_name.split(".") if p]
    if not parts:
        return None
    candidates = [
        package_root / "src" / Path(*parts).with_suffix(".vibe"),
        package_root / Path(*parts).with_suffix(".vibe"),
        package_root / "src" / f"{parts[-1]}.vibe",
    ]
    for cand in candidates:
        if cand.exists():
            return cand.resolve()
    return None


def package_context_for_path(path: Path) -> dict[str, object]:
    for parent in [path.parent, *path.parents]:
        manifest_path = parent / "vibe.toml"
        if manifest_path.exists():
            m = load_manifest(manifest_path)
            return {
                "package_name": m.package_name,
                "package_version": m.package_version,
                "bridge_defaults": dict(m.bridge_defaults),
                "emit_defaults": dict(m.emit_defaults),
                "dependencies": dict(m.dependencies),
            }
    return {}


def validate_manifest_and_graph(manifest_path: Path) -> tuple[VibeManifest, list[ManifestIssue], PackageGraph]:
    manifest = load_manifest(manifest_path)
    issues = validate_manifest(manifest)
    graph = resolve_package_graph(manifest_path)
    return manifest, issues, graph


def build_project(manifest_path: Path) -> dict[str, object]:
    manifest, manifest_issues, graph = validate_manifest_and_graph(manifest_path)
    root = manifest_path.parent.resolve()
    root_modules = discover_package_modules(root)
    root_entry = root / "src" / "main.vibe"
    entry_modules = [root_entry] if root_entry.exists() else (root_modules[:1] if root_modules else [])
    dep_map: dict[str, Path] = {}
    for edge in graph.edges:
        if edge.get("from") == manifest.package_name and _dep_is_local(str(edge.get("spec", ""))):
            dep_root = _dep_path(root, str(edge["spec"]))
            dep_map[str(edge["to"])] = dep_root

    package_manifests: dict[str, VibeManifest] = {manifest.package_name: manifest}
    for dep_name, dep_root in sorted(dep_map.items()):
        dep_manifest = dep_root / "vibe.toml"
        if dep_manifest.exists():
            package_manifests[dep_name] = load_manifest(dep_manifest)

    queue: list[tuple[str, Path]] = [(manifest.package_name, m.resolve()) for m in entry_modules]
    seen: set[tuple[str, str]] = set()
    build_edges: list[dict[str, str]] = []
    build_rows: list[dict[str, object]] = []
    build_issues: list[dict[str, object]] = []

    while queue:
        package_name, module = queue.pop(0)
        key = (package_name, str(module))
        if key in seen:
            continue
        seen.add(key)
        if not module.exists():
            build_issues.append(
                {
                    "issue_id": "module.unresolved",
                    "severity": "critical",
                    "message": f"module file not found: {module}",
                    "package": package_name,
                }
            )
            continue
        package_manifest = package_manifests.get(package_name, manifest)
        source = module.read_text(encoding="utf-8")
        source = apply_package_defaults_to_source(source, package_manifest)
        program: Program = parse_source(source)
        ir = ast_to_ir(program)
        emitted_code, _ = emit_code(ir)
        verify_result = verify(ir, emitted_code)
        verify_result.package_context = {
            "package_name": package_manifest.package_name,
            "package_version": package_manifest.package_version,
            "bridge_defaults": dict(package_manifest.bridge_defaults),
            "emit_defaults": dict(package_manifest.emit_defaults),
            "dependencies": dict(package_manifest.dependencies),
        }
        build_rows.append(
            {
                "module": str(module),
                "package": package_name,
                "intent": ir.intent_name,
                "emit_target": ir.emit_target,
                "bridge_config_effective": ir.bridge_config,
                "verification_passed": verify_result.passed,
                "obligation_counts": dict(verify_result.obligation_counts),
                "imports": list(program.imports),
            }
        )
        current_root = root if package_name == manifest.package_name else dep_map.get(package_name, root)
        for imp in sorted(program.imports):
            resolved_package = package_name
            resolved_module: Path | None = None
            parts = [p for p in imp.split(".") if p]
            if parts and parts[0] in dep_map:
                resolved_package = parts[0]
                dep_import = ".".join(parts[1:]) if len(parts) > 1 else "main"
                resolved_module = _resolve_import_to_module(dep_map[resolved_package], dep_import)
            else:
                resolved_module = _resolve_import_to_module(current_root, imp)
            if resolved_module is None:
                build_issues.append(
                    {
                        "issue_id": "import.unresolved",
                        "severity": "high",
                        "message": f"unable to resolve import `{imp}` from `{module}`",
                        "package": package_name,
                    }
                )
                continue
            build_edges.append(
                {
                    "from_module": str(module),
                    "to_module": str(resolved_module),
                    "import": imp,
                    "from_package": package_name,
                    "to_package": resolved_package,
                }
            )
            queue.append((resolved_package, resolved_module))

    blocking = [asdict(i) for i in manifest_issues if i.severity in {"critical", "high"}] + [
        x for x in graph.issues if str(x.get("severity", "")) in {"critical", "high"}
    ] + [x for x in build_issues if str(x.get("severity", "")) in {"critical", "high"}]
    build_rows_sorted = sorted(build_rows, key=lambda r: (str(r["package"]), str(r["module"])))
    dep_summary = {
        "direct_dependencies": sorted(manifest.dependencies.keys()),
        "resolved_local_dependencies": sorted(dep_map.keys()),
        "total_packages": len(graph.packages),
    }
    return {
        "package": {"name": manifest.package_name, "version": manifest.package_version, "description": manifest.description},
        "package_defaults": {
            "bridge_defaults": dict(manifest.bridge_defaults),
            "emit_defaults": dict(manifest.emit_defaults),
        },
        "manifest_issues": [asdict(i) for i in manifest_issues],
        "dependency_summary": dep_summary,
        "dependency_graph": {
            "root_package": graph.root_package,
            "packages": [asdict(p) for p in graph.packages],
            "edges": list(graph.edges),
            "issues": list(graph.issues),
        },
        "build_graph": {
            "entry_modules": [str(m) for m in entry_modules],
            "reachable_modules": len(build_rows_sorted),
            "import_edges": sorted(build_edges, key=lambda e: (e["from_module"], e["to_module"], e["import"])),
        },
        "build_modules": build_rows_sorted,
        "build_issues": sorted(build_issues, key=lambda x: (str(x.get("severity", "")), str(x.get("message", "")))),
        "blocking_issues": blocking,
    }


def package_summary_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2)
