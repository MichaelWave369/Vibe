"""Target plugin scaffolding for cross-domain emit targets (Phase 7A)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class TargetPlugin:
    target: str
    extension: str
    implemented: bool
    domain_hint: str
    notes: str


_TARGETS: dict[str, TargetPlugin] = {
    "python": TargetPlugin("python", ".py", True, "general", "fully implemented"),
    "typescript": TargetPlugin("typescript", ".ts", True, "general", "fully implemented"),
    "vhdl": TargetPlugin("vhdl", ".vhd", True, "hardware", "phase-7.1 deterministic rtl emitter"),
    "systemverilog": TargetPlugin("systemverilog", ".sv", True, "hardware", "phase-7.1 deterministic rtl emitter"),
    "julia": TargetPlugin("julia", ".jl", True, "scientific_simulation", "phase-7.2 deterministic simulation emitter"),
    "compliance_report": TargetPlugin("compliance_report", ".md", False, "legal_compliance", "phase-7 scaffold emitter"),
    "snakemake": TargetPlugin("snakemake", ".smk", False, "genomics", "phase-7 scaffold emitter"),
    "nextflow": TargetPlugin("nextflow", ".nf", False, "genomics", "phase-7 scaffold emitter"),
}



def register_target_plugin(plugin: TargetPlugin) -> None:
    _TARGETS[plugin.target] = plugin



def get_target_plugin(target: str) -> TargetPlugin | None:
    return _TARGETS.get(target.strip().lower())



def list_target_plugins() -> list[dict[str, object]]:
    return [asdict(_TARGETS[k]) for k in sorted(_TARGETS.keys())]



def target_plugins_json() -> str:
    return json.dumps({"targets": list_target_plugins()}, sort_keys=True, indent=2)
