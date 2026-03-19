"""vibe.toml parsing/validation utilities (Phase 6.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as tomllib


@dataclass(slots=True)
class ManifestIssue:
    issue_id: str
    severity: str
    message: str


@dataclass(slots=True)
class VibeManifest:
    package_name: str
    package_version: str
    description: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    bridge_defaults: dict[str, object] = field(default_factory=dict)
    emit_defaults: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


def _as_float_if_numeric(raw: object) -> object:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except Exception:
            return raw
    return raw


def load_manifest(path: Path) -> VibeManifest:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    package = dict(payload.get("package", {}))
    bridge = {str(k): _as_float_if_numeric(v) for k, v in dict(payload.get("bridge", {})).items()}
    emit = {str(k): v for k, v in dict(payload.get("emit", {})).items()}
    deps = {str(k): str(v) for k, v in dict(payload.get("dependencies", {})).items()}
    metadata = dict(payload.get("metadata", {}))
    return VibeManifest(
        package_name=str(package.get("name", "")).strip(),
        package_version=str(package.get("version", "")).strip(),
        description=str(package.get("description", "")).strip(),
        dependencies=deps,
        bridge_defaults=bridge,
        emit_defaults=emit,
        metadata=metadata,
    )


def validate_manifest(manifest: VibeManifest) -> list[ManifestIssue]:
    issues: list[ManifestIssue] = []
    if not manifest.package_name:
        issues.append(ManifestIssue("manifest.package.name.missing", "critical", "package.name is required"))
    if not manifest.package_version:
        issues.append(ManifestIssue("manifest.package.version.missing", "critical", "package.version is required"))
    if "measurement_safe_ratio" in manifest.bridge_defaults:
        try:
            value = float(manifest.bridge_defaults["measurement_safe_ratio"])
            if not (0.0 < value <= 1.0):
                issues.append(
                    ManifestIssue(
                        "manifest.bridge.measurement_safe_ratio.range",
                        "high",
                        "bridge.measurement_safe_ratio should be in (0, 1]",
                    )
                )
        except Exception:
            issues.append(
                ManifestIssue(
                    "manifest.bridge.measurement_safe_ratio.type",
                    "high",
                    "bridge.measurement_safe_ratio must be numeric",
                )
            )
    return issues


def manifest_to_json(manifest: VibeManifest) -> str:
    return json.dumps(asdict(manifest), sort_keys=True, indent=2)
