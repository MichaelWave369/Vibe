"""Backend emitter registry for multi-target code generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .generator_python import generate_python
from .generator_typescript import generate_typescript
from .ir import IR


@dataclass(frozen=True)
class EmitterBackend:
    target: str
    extension: str

    def emit(self, ir: IR) -> str:  # pragma: no cover - protocol-like
        raise NotImplementedError


class PythonEmitter(EmitterBackend):
    def __init__(self) -> None:
        super().__init__(target="python", extension=".py")

    def emit(self, ir: IR) -> str:
        return generate_python(ir)


class TypeScriptEmitter(EmitterBackend):
    def __init__(self) -> None:
        super().__init__(target="typescript", extension=".ts")

    def emit(self, ir: IR) -> str:
        return generate_typescript(ir)


_BACKENDS = {
    "python": PythonEmitter(),
    "typescript": TypeScriptEmitter(),
}


def resolve_backend(target: str) -> EmitterBackend:
    normalized = target.strip().lower()
    if normalized not in _BACKENDS:
        raise ValueError(f"Unsupported emit target: {target}")
    return _BACKENDS[normalized]


def emit_code(ir: IR, target_override: str | None = None) -> tuple[str, EmitterBackend]:
    backend = resolve_backend(target_override or ir.emit_target)
    return backend.emit(ir), backend


def output_path_for(source_path: Path, backend: EmitterBackend) -> Path:
    return source_path.with_suffix(backend.extension)
