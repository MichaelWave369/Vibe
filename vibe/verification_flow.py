"""Verification input loading seam for path and in-memory sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ir import IR, ast_to_ir
from .manifest import VibeManifest
from .package_manager import apply_package_defaults_to_source, package_context_for_path
from .parser import parse_source


@dataclass(frozen=True, slots=True)
class VerificationInput:
    source_text: str
    ir: IR
    spec_path: str
    package_context: dict[str, object]


@dataclass(frozen=True, slots=True)
class SnapshotVerificationInput:
    snapshot_hash: str
    source_text: str


# TODO(issue-34): Wire SnapshotVerificationInput into a real snapshot/object store.
def prepare_verification_input(*, path: Path | None = None, source_text: str | None = None, source_name: str = "<memory>") -> VerificationInput:
    """Build verification input from either a file path or in-memory source text."""

    if path is None and source_text is None:
        raise ValueError("prepare_verification_input requires either `path` or `source_text`")

    package_context: dict[str, object] = {}
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        resolved_text = path.read_text(encoding="utf-8")
        package_context = package_context_for_path(path) or {}
        spec_path = str(path)
    else:
        resolved_text = str(source_text)
        spec_path = source_name

    if package_context:
        resolved_text = apply_package_defaults_to_source(
            resolved_text,
            VibeManifest(
                package_name=str(package_context.get("package_name", "")),
                package_version=str(package_context.get("package_version", "")),
                description="",
                dependencies=dict(package_context.get("dependencies", {})),
                bridge_defaults=dict(package_context.get("bridge_defaults", {})),
                emit_defaults=dict(package_context.get("emit_defaults", {})),
            ),
        )

    ir = ast_to_ir(parse_source(resolved_text))
    return VerificationInput(
        source_text=resolved_text,
        ir=ir,
        spec_path=spec_path,
        package_context=dict(package_context),
    )
