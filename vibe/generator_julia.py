"""Deterministic Julia emitter (Phase 7.2 scientific simulation slice)."""

from __future__ import annotations

from .ir import IR


_TYPE_MAP = {
    "number": "Float64",
    "boolean": "Bool",
    "string": "String",
}


def _julia_type(vibe_type: str) -> str:
    return _TYPE_MAP.get(vibe_type.strip().lower(), "Any")


def _julia_literal(vibe_type: str) -> str:
    jt = _julia_type(vibe_type)
    if jt == "Float64":
        return "0.0"
    if jt == "Bool":
        return "false"
    if jt == "String":
        return '""'
    return "nothing"


def generate_julia(ir: IR) -> str:
    module_name = ir.intent_name
    inputs = sorted(ir.inputs.items(), key=lambda x: x[0])
    outputs = sorted(ir.outputs.items(), key=lambda x: x[0])

    preserve_lines = [f"# preserve: {k} {op} {v}".strip() for k, op, v in ir.preserve_rules]
    constraint_lines = [f"# constraint: {c}" for c in ir.constraints]
    simulation_lines = [
        f"# simulation_profile: {ir.domain_profile}",
        f"# scientific_simulation_summary: {ir.module.scientific_simulation_summary}",
        f"# scientific_target_metadata: {ir.module.scientific_target_metadata}",
    ]

    signature_parts = [f"{name}::{_julia_type(tp)}" for name, tp in inputs]
    has_seeded_rng = any("seeded_rng" in c.lower() for c in ir.constraints)
    if has_seeded_rng:
        signature_parts.append("seed::Int=42")
    signature_parts.append("dt::Float64=1.0")

    result_pairs = [f"{name}={_julia_literal(tp)}" for name, tp in outputs]

    lines: list[str] = [
        f"module {module_name}",
        "",
        f"# intent: {ir.intent_name}",
        f"# goal: {ir.goal}",
        *simulation_lines,
        *preserve_lines,
        *constraint_lines,
        "# NOTE: Phase 7.2 structured simulation scaffold. Manual numerical model completion required.",
        "",
        f"function evolve_step({', '.join(signature_parts)})",
    ]

    if has_seeded_rng:
        lines.extend([
            "    rng = MersenneTwister(seed)  # seeded RNG for reproducibility contracts",
            "    _noise = rand(rng)",
        ])
    else:
        lines.append("    # rng wiring can be added if seeded reproducibility is required")

    lines.extend(
        [
            "    # deterministic_fp contract expects stable operation order across runs",
            "    # stable_time_step preserve should map to dt policy in completed model",
            "    # bounded_error preserve should map to explicit error norm checks",
            "    # conservation preserves (energy/mass) should be enforced in update equations",
            "    # TODO: implement integrator/model equations for this intent",
            f"    return ({', '.join(result_pairs)})",
            "end",
            "",
            f"end # module {module_name}",
            "",
        ]
    )

    return "\n".join(lines)
