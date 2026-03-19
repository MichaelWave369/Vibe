"""Deterministic SystemVerilog emitter (Phase 7.1 hardware slice)."""

from __future__ import annotations

from .ir import IR


_TYPE_MAP = {
    "number": "logic [31:0]",
    "string": "logic [255:0]",
    "boolean": "logic",
}


def _port_type(vibe_type: str) -> str:
    return _TYPE_MAP.get(vibe_type.strip().lower(), "logic [31:0]")



def generate_systemverilog(ir: IR) -> str:
    module_name = ir.intent_name
    inputs = sorted(ir.inputs.items(), key=lambda x: x[0])
    outputs = sorted(ir.outputs.items(), key=lambda x: x[0])

    ports: list[str] = ["input logic clk", "input logic rst_n"]
    ports.extend([f"input {_port_type(tp)} {name}" for name, tp in inputs])
    ports.extend([f"output {_port_type(tp)} {name}" for name, tp in outputs])

    preserve_lines = [f"// preserve: {k} {op} {v}" for k, op, v in ir.preserve_rules]
    constraint_lines = [f"// constraint: {c}" for c in ir.constraints]
    hardware_lines = [
        f"// hardware_profile: {ir.domain_profile}",
        f"// hardware_summary: {ir.module.hardware_summary}",
        f"// hardware_target_metadata: {ir.module.hardware_target_metadata}",
    ]

    reset_assign = []
    for name, tp in outputs:
        t = _port_type(tp)
        if t == "logic":
            reset_assign.append(f"      {name} <= 1'b0;")
        else:
            reset_assign.append(f"      {name} <= '0;")
    if not reset_assign:
        reset_assign = ["      ;"]

    lines: list[str] = [
        f"// intent: {ir.intent_name}",
        f"// goal: {ir.goal}",
        *hardware_lines,
        *preserve_lines,
        *constraint_lines,
        "// NOTE: Phase 7.1 structured RTL scaffold. Manual logic completion required.",
        "",
        f"module {module_name}(",
        "  " + ",\n  ".join(ports),
        ");",
        "",
        "  always_ff @(posedge clk or negedge rst_n) begin",
        "    if (!rst_n) begin",
        *reset_assign,
        "    end else begin",
        "      // deterministic synchronous update region",
        "      // no combinational loops should be introduced in manual completion",
        "    end",
        "  end",
        "",
        f"endmodule : {module_name}",
        "",
    ]
    return "\n".join(lines)
