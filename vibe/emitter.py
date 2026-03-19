"""Backend emitter registry for multi-target code generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .generator_compliance_report import generate_compliance_report
from .generator_julia import generate_julia
from .generator_python import generate_python
from .generator_systemverilog import generate_systemverilog
from .generator_typescript import generate_typescript
from .generator_vhdl import generate_vhdl
from .ir import IR
from .target_plugins import get_target_plugin


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


class JuliaEmitter(EmitterBackend):
    def __init__(self) -> None:
        super().__init__(target="julia", extension=".jl")

    def emit(self, ir: IR) -> str:
        return generate_julia(ir)


class ComplianceReportEmitter(EmitterBackend):
    def __init__(self) -> None:
        super().__init__(target="compliance_report", extension=".compliance.json")

    def emit(self, ir: IR) -> str:
        return generate_compliance_report(ir)


class VHDLEmitter(EmitterBackend):
    def __init__(self) -> None:
        super().__init__(target="vhdl", extension=".vhd")

    def emit(self, ir: IR) -> str:
        return generate_vhdl(ir)


class SystemVerilogEmitter(EmitterBackend):
    def __init__(self) -> None:
        super().__init__(target="systemverilog", extension=".sv")

    def emit(self, ir: IR) -> str:
        return generate_systemverilog(ir)


class StubEmitter(EmitterBackend):
    def __init__(self, target: str, extension: str) -> None:
        super().__init__(target=target, extension=extension)

    def emit(self, ir: IR) -> str:
        return (
            f"# Vibe scaffold emitter for target `{self.target}`\\n"
            f"# domain_profile: {ir.domain_profile}\\n"
            "# This target is a Phase 7A scaffold and is not a full backend yet.\\n"
            "artifact = {\n"
            f"  \"intent\": \"{ir.intent_name}\",\n"
            f"  \"emit_target\": \"{self.target}\",\n"
            f"  \"domain_profile\": \"{ir.domain_profile}\",\n"
            "  \"scaffold\": true\n"
            "}\n"
        )


_BACKENDS = {
    "python": PythonEmitter(),
    "typescript": TypeScriptEmitter(),
    "julia": JuliaEmitter(),
    "compliance_report": ComplianceReportEmitter(),
    "vhdl": VHDLEmitter(),
    "systemverilog": SystemVerilogEmitter(),
}


def resolve_backend(target: str) -> EmitterBackend:
    normalized = target.strip().lower()
    if normalized not in _BACKENDS:
        plugin = get_target_plugin(normalized)
        if plugin is None:
            raise ValueError(f"Unsupported emit target: {target}")
        return StubEmitter(target=plugin.target, extension=plugin.extension)
    return _BACKENDS[normalized]


def emit_code(ir: IR, target_override: str | None = None) -> tuple[str, EmitterBackend]:
    backend = resolve_backend(target_override or ir.emit_target)
    return backend.emit(ir), backend


def output_path_for(source_path: Path, backend: EmitterBackend) -> Path:
    return source_path.with_suffix(backend.extension)
