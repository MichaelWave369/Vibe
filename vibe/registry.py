"""Local-first intent registry primitives (Phase 6.2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os

from .manifest import load_manifest
from .package_manager import build_project
from .proof import load_proof_artifact


REGISTRY_FORMAT_VERSION = "v1"


@dataclass(slots=True)
class PackageRef:
    name: str
    version: str | None = None



def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))



def _sha256_json(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()



def _parse_semver(version: str) -> tuple[int, int, int] | None:
    parts = version.split(".")
    if len(parts) < 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return None



def _version_sort_key(version: str) -> tuple[int, int, int, str]:
    parsed = _parse_semver(version)
    if parsed is None:
        return (-1, -1, -1, version)
    return (*parsed, version)



def parse_package_ref(raw: str) -> PackageRef:
    if "@" in raw:
        name, version = raw.rsplit("@", 1)
        return PackageRef(name=name.strip(), version=version.strip())
    return PackageRef(name=raw.strip(), version=None)



def resolve_registry_root(registry_root: Path | None = None) -> Path:
    if registry_root is not None:
        return registry_root.resolve()
    env = os.environ.get("VIBE_REGISTRY_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / ".vibe_registry").resolve()



def _entry_paths(registry_root: Path, package: str, version: str) -> tuple[Path, Path]:
    entry_dir = registry_root / "entries" / package / version
    return entry_dir, entry_dir / "entry.json"



def _entry_id(package: str, version: str) -> str:
    return f"{package}@{version}"



def _proof_summary_for_modules(modules: list[dict[str, object]]) -> dict[str, object]:
    module_rows: list[dict[str, object]] = []
    artifacts_present = 0
    artifact_versions: set[str] = set()
    invalid_artifacts: list[str] = []
    verification_passed = 0
    verification_failed = 0

    for module in sorted(modules, key=lambda row: str(row.get("module", ""))):
        module_path = Path(str(module.get("module", "")))
        proof_path = module_path.with_suffix(".vibe.proof.json")
        module_proof: dict[str, object] = {
            "module": str(module_path),
            "proof_path": str(proof_path),
            "proof_present": False,
            "proof_valid": False,
        }
        if proof_path.exists():
            module_proof["proof_present"] = True
            artifacts_present += 1
            try:
                payload = load_proof_artifact(proof_path)
                module_proof["proof_valid"] = True
                module_proof["artifact_version"] = payload.get("artifact_version")
                module_proof["result_passed"] = bool(payload.get("result", {}).get("passed", False))
                artifact_versions.add(str(payload.get("artifact_version", "")))
                if module_proof["result_passed"]:
                    verification_passed += 1
                else:
                    verification_failed += 1
            except Exception as exc:
                invalid_artifacts.append(f"{proof_path}: {exc}")
                module_proof["error"] = str(exc)
        module_rows.append(module_proof)

    proof_status = "complete"
    if not modules:
        proof_status = "absent"
    elif artifacts_present == 0:
        proof_status = "absent"
    elif invalid_artifacts or artifacts_present < len(modules):
        proof_status = "partial"

    return {
        "proof_status": proof_status,
        "proof_artifacts_present": artifacts_present,
        "total_modules": len(modules),
        "proof_artifact_versions": sorted(v for v in artifact_versions if v),
        "verification_passed_modules": verification_passed,
        "verification_failed_modules": verification_failed,
        "invalid_artifacts": sorted(invalid_artifacts),
        "module_proofs": module_rows,
    }



def _build_summary(build_payload: dict[str, object]) -> dict[str, object]:
    build_graph = dict(build_payload.get("build_graph", {}))
    return {
        "entry_modules": sorted(build_graph.get("entry_modules", [])),
        "reachable_modules": int(build_graph.get("reachable_modules", 0)),
        "import_edges": len(build_graph.get("import_edges", [])),
        "blocking_issues": len(build_payload.get("blocking_issues", [])),
        "build_issues": len(build_payload.get("build_issues", [])),
    }



def _extract_tags_domain(manifest_metadata: dict[str, object]) -> tuple[list[str], str | None]:
    tags_raw = manifest_metadata.get("tags", [])
    if isinstance(tags_raw, list):
        tags = sorted({str(t).strip() for t in tags_raw if str(t).strip()})
    else:
        tags = []
    domain_raw = manifest_metadata.get("domain")
    domain = str(domain_raw).strip() if domain_raw is not None else ""
    return tags, (domain if domain else None)



def create_registry_entry(project_dir: Path) -> dict[str, object]:
    manifest_path = (project_dir / "vibe.toml").resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"vibe.toml not found: {manifest_path}")

    manifest = load_manifest(manifest_path)
    build_payload = build_project(manifest_path)
    if build_payload.get("blocking_issues"):
        raise ValueError("cannot publish package with blocking build/manifest issues")

    tags, domain = _extract_tags_domain(manifest.metadata)
    modules = sorted(build_payload.get("build_modules", []), key=lambda row: str(row.get("module", "")))
    module_summary = [
        {
            "module": str(row.get("module", "")),
            "intent": str(row.get("intent", "")),
            "emit_target": str(row.get("emit_target", "")),
            "verification_passed": bool(row.get("verification_passed", False)),
            "imports": sorted([str(x) for x in row.get("imports", [])]),
        }
        for row in modules
    ]
    proof_summary = _proof_summary_for_modules(modules)
    deps = dict(build_payload.get("dependency_summary", {}))

    entry_without_hash: dict[str, object] = {
        "registry_format_version": REGISTRY_FORMAT_VERSION,
        "entry_id": _entry_id(manifest.package_name, manifest.package_version),
        "package": {
            "name": manifest.package_name,
            "version": manifest.package_version,
            "description": manifest.description,
            "dependencies": dict(manifest.dependencies),
            "dependency_summary": {
                "direct_dependencies": sorted([str(x) for x in deps.get("direct_dependencies", [])]),
                "resolved_local_dependencies": sorted([str(x) for x in deps.get("resolved_local_dependencies", [])]),
                "total_packages": int(deps.get("total_packages", 0)),
            },
            "bridge_defaults": dict(manifest.bridge_defaults),
            "emit_defaults": dict(manifest.emit_defaults),
            "modules": module_summary,
            "tags": tags,
            "domain": domain,
        },
        "manifest_metadata": {
            "metadata": manifest.metadata,
            "manifest_issues": sorted(build_payload.get("manifest_issues", []), key=lambda row: str(row.get("issue_id", ""))),
        },
        "proof": proof_summary,
        "build": _build_summary(build_payload),
        "compatibility": {
            "compatibility_hints_version": "phase-6.2",
            "major": _parse_semver(manifest.package_version)[0] if _parse_semver(manifest.package_version) else None,
            "minor": _parse_semver(manifest.package_version)[1] if _parse_semver(manifest.package_version) else None,
            "proof_status": proof_summary["proof_status"],
        },
        "publication": {
            "local_only": True,
            "note": "Published into local filesystem registry. Hosted registry is a future phase.",
        },
    }
    entry = dict(entry_without_hash)
    entry["entry_hash"] = _sha256_json(entry_without_hash)
    return entry



def _load_index(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"registry_format_version": REGISTRY_FORMAT_VERSION, "entries": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "entries" not in payload:
        payload["entries"] = []
    return payload



def _write_index(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["entries"] = sorted(
        payload.get("entries", []),
        key=lambda row: (str(row.get("name", "")), _version_sort_key(str(row.get("version", "")))),
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")



def publish_to_local_registry(project_dir: Path, registry_root: Path | None = None) -> dict[str, object]:
    root = resolve_registry_root(registry_root)
    entry = create_registry_entry(project_dir)
    package = str(entry["package"]["name"])
    version = str(entry["package"]["version"])
    entry_dir, entry_path = _entry_paths(root, package, version)
    entry_dir.mkdir(parents=True, exist_ok=True)
    entry_path.write_text(json.dumps(entry, indent=2, sort_keys=True), encoding="utf-8")

    index_path = root / "index.json"
    index = _load_index(index_path)
    rows = [
        row
        for row in index.get("entries", [])
        if not (str(row.get("name", "")) == package and str(row.get("version", "")) == version)
    ]
    rows.append(
        {
            "name": package,
            "version": version,
            "description": str(entry["package"].get("description", "")),
            "tags": list(entry["package"].get("tags", [])),
            "domain": entry["package"].get("domain"),
            "entry_id": entry["entry_id"],
            "entry_hash": entry["entry_hash"],
            "entry_path": str(entry_path),
            "proof_status": entry["proof"].get("proof_status", "absent"),
        }
    )
    index["registry_format_version"] = REGISTRY_FORMAT_VERSION
    index["entries"] = rows
    _write_index(index_path, index)

    return {
        "entry_id": entry["entry_id"],
        "entry_path": str(entry_path),
        "entry_hash": entry["entry_hash"],
        "registry_root": str(root),
        "proof_status": entry["proof"].get("proof_status", "absent"),
    }



def _load_entry_from_row(row: dict[str, object]) -> dict[str, object]:
    entry_path = Path(str(row.get("entry_path", "")))
    return json.loads(entry_path.read_text(encoding="utf-8"))



def search_local_registry(
    query: str,
    *,
    tag_filters: list[str] | None = None,
    domain_filter: str | None = None,
    registry_root: Path | None = None,
) -> dict[str, object]:
    root = resolve_registry_root(registry_root)
    index = _load_index(root / "index.json")
    query_tokens = [t for t in query.lower().split() if t]
    tag_filters = sorted({t.strip().lower() for t in (tag_filters or []) if t.strip()})
    domain_filter = (domain_filter or "").strip().lower()

    scored: list[dict[str, object]] = []
    for row in index.get("entries", []):
        name = str(row.get("name", ""))
        description = str(row.get("description", ""))
        tags = [str(t).lower() for t in row.get("tags", [])]
        domain = str(row.get("domain", "") or "").lower()

        if tag_filters and not set(tag_filters).issubset(set(tags)):
            continue
        if domain_filter and domain != domain_filter:
            continue

        text = f"{name} {description} {' '.join(tags)} {domain}".lower()
        score = 0
        if not query_tokens:
            score = 1
        else:
            for tok in query_tokens:
                if tok in name.lower():
                    score += 5
                if tok in description.lower():
                    score += 3
                if tok in tags:
                    score += 2
                if tok and tok in text:
                    score += 1
        if score <= 0:
            continue
        scored.append(
            {
                "name": name,
                "version": str(row.get("version", "")),
                "description": description,
                "tags": sorted([str(t) for t in row.get("tags", [])]),
                "domain": row.get("domain"),
                "entry_id": row.get("entry_id"),
                "entry_hash": row.get("entry_hash"),
                "proof_status": row.get("proof_status"),
                "score": score,
            }
        )

    scored = sorted(scored, key=lambda r: (-int(r["score"]), str(r["name"]), _version_sort_key(str(r["version"]))))
    return {
        "registry_root": str(root),
        "query": query,
        "tag_filters": tag_filters,
        "domain_filter": domain_filter or None,
        "result_count": len(scored),
        "results": scored,
    }



def _find_entry(ref: PackageRef, registry_root: Path | None = None) -> dict[str, object]:
    root = resolve_registry_root(registry_root)
    index = _load_index(root / "index.json")
    matches = [row for row in index.get("entries", []) if str(row.get("name", "")) == ref.name]
    if not matches:
        raise KeyError(f"package not found in local registry: {ref.name}")
    if ref.version:
        chosen = [row for row in matches if str(row.get("version", "")) == ref.version]
        if not chosen:
            raise KeyError(f"package version not found in local registry: {ref.name}@{ref.version}")
        return _load_entry_from_row(chosen[0])
    matches_sorted = sorted(matches, key=lambda row: _version_sort_key(str(row.get("version", ""))), reverse=True)
    return _load_entry_from_row(matches_sorted[0])



def inspect_registry_entry(package_ref: str, registry_root: Path | None = None) -> dict[str, object]:
    ref = parse_package_ref(package_ref)
    entry = _find_entry(ref, registry_root=registry_root)
    return {
        "entry_id": entry.get("entry_id"),
        "entry_hash": entry.get("entry_hash"),
        "package": entry.get("package", {}),
        "manifest_metadata": entry.get("manifest_metadata", {}),
        "build": entry.get("build", {}),
        "proof": entry.get("proof", {}),
        "compatibility": entry.get("compatibility", {}),
        "publication": entry.get("publication", {}),
    }



def compatibility_summary(package_ref_a: str, package_ref_b: str, registry_root: Path | None = None) -> dict[str, object]:
    entry_a = _find_entry(parse_package_ref(package_ref_a), registry_root=registry_root)
    entry_b = _find_entry(parse_package_ref(package_ref_b), registry_root=registry_root)

    pkg_a = dict(entry_a.get("package", {}))
    pkg_b = dict(entry_b.get("package", {}))
    ver_a = str(pkg_a.get("version", ""))
    ver_b = str(pkg_b.get("version", ""))
    sem_a = _parse_semver(ver_a)
    sem_b = _parse_semver(ver_b)

    major_compatible = bool(sem_a and sem_b and sem_a[0] == sem_b[0])
    minor_relation = "unknown"
    if sem_a and sem_b:
        if sem_a[1] == sem_b[1]:
            minor_relation = "same-minor"
        elif sem_a[1] < sem_b[1]:
            minor_relation = "a-older-minor"
        else:
            minor_relation = "a-newer-minor"

    deps_a = dict(pkg_a.get("dependencies", {}))
    deps_b = dict(pkg_b.get("dependencies", {}))
    shared = sorted(set(deps_a.keys()) & set(deps_b.keys()))
    dep_mismatches = [
        {"dependency": dep, "a": deps_a[dep], "b": deps_b[dep]}
        for dep in shared
        if str(deps_a[dep]) != str(deps_b[dep])
    ]

    bridge_a = dict(pkg_a.get("bridge_defaults", {}))
    bridge_b = dict(pkg_b.get("bridge_defaults", {}))
    bridge_keys = sorted(set(bridge_a.keys()) | set(bridge_b.keys()))
    bridge_diff = [
        {"key": key, "a": bridge_a.get(key), "b": bridge_b.get(key)}
        for key in bridge_keys
        if bridge_a.get(key) != bridge_b.get(key)
    ]

    emit_a = dict(pkg_a.get("emit_defaults", {}))
    emit_b = dict(pkg_b.get("emit_defaults", {}))
    proof_a = dict(entry_a.get("proof", {}))
    proof_b = dict(entry_b.get("proof", {}))

    proof_status_a = str(proof_a.get("proof_status", "absent"))
    proof_status_b = str(proof_b.get("proof_status", "absent"))
    proof_versions_a = set([str(v) for v in proof_a.get("proof_artifact_versions", [])])
    proof_versions_b = set([str(v) for v in proof_b.get("proof_artifact_versions", [])])
    proof_versions_overlap = sorted(proof_versions_a & proof_versions_b)

    status = "review-required"
    if not major_compatible and sem_a and sem_b:
        status = "incompatible-major"
    elif proof_status_a != "complete" or proof_status_b != "complete":
        status = "insufficient-proof"
    elif not dep_mismatches and not bridge_diff and emit_a == emit_b:
        status = "likely-compatible"

    return {
        "analysis_type": "phase-6.2 compatibility hints",
        "disclaimer": "Deterministic compatibility hints only, not a formal proof of interchangeability.",
        "packages": [
            {
                "entry_id": entry_a.get("entry_id"),
                "name": pkg_a.get("name"),
                "version": ver_a,
                "proof_status": proof_status_a,
            },
            {
                "entry_id": entry_b.get("entry_id"),
                "name": pkg_b.get("name"),
                "version": ver_b,
                "proof_status": proof_status_b,
            },
        ],
        "semver": {
            "major_compatible": major_compatible,
            "minor_relation": minor_relation,
        },
        "dependency_comparison": {
            "shared_dependencies": shared,
            "mismatches": dep_mismatches,
        },
        "bridge_defaults_diff": bridge_diff,
        "emit_defaults_equal": emit_a == emit_b,
        "proof_compatibility": {
            "a_status": proof_status_a,
            "b_status": proof_status_b,
            "artifact_versions_overlap": proof_versions_overlap,
        },
        "compatibility_status": status,
    }
