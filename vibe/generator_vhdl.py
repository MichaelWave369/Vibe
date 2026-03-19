"""Deterministic VHDL emitter (Phase 7.1 hardware slice)."""

from __future__ import annotations

from .ir import IR


_TYPE_MAP = {
    "number": "integer",
    "string": "std_logic_vector(31 downto 0)",
    "boolean": "std_logic",
}


def _port_type(vibe_type: str) -> str:
    return _TYPE_MAP.get(vibe_type.strip().lower(), "std_logic_vector(31 downto 0)")



def generate_vhdl(ir: IR) -> str:
    entity_name = ir.intent_name
    inputs = sorted(ir.inputs.items(), key=lambda x: x[0])
    outputs = sorted(ir.outputs.items(), key=lambda x: x[0])
    ports: list[str] = ["clk : in std_logic", "rst_n : in std_logic"]
    ports.extend([f"{name} : in {_port_type(tp)}" for name, tp in inputs])
    ports.extend([f"{name} : out {_port_type(tp)}" for name, tp in outputs])

    preserve_lines = [f"-- preserve: {k} {op} {v}".rstrip() for k, op, v in ir.preserve_rules]
    constraint_lines = [f"-- constraint: {c}" for c in ir.constraints]
    hardware_lines = [
        f"-- hardware_profile: {ir.domain_profile}",
        f"-- hardware_summary: {ir.module.hardware_summary}",
        f"-- hardware_target_metadata: {ir.module.hardware_target_metadata}",
    ]

    assignments = [f"      {name} <= (others => '0');" if _port_type(tp).startswith("std_logic_vector") else f"      {name} <= '0';" if _port_type(tp)=="std_logic" else f"      {name} <= 0;" for name, tp in outputs]
    if not assignments:
        assignments = ["      null;"]

    lines: list[str] = [
        "library IEEE;",
        "use IEEE.STD_LOGIC_1164.ALL;",
        "use IEEE.NUMERIC_STD.ALL;",
        "",
        f"-- intent: {ir.intent_name}",
        f"-- goal: {ir.goal}",
        *hardware_lines,
        *preserve_lines,
        *constraint_lines,
        "-- NOTE: Phase 7.1 structured RTL scaffold. Manual logic completion required.",
        "",
        f"entity {entity_name} is",
        "  port (",
        "    " + ";\n    ".join(ports),
        "  );",
        f"end entity {entity_name};",
        "",
        f"architecture rtl of {entity_name} is",
        "begin",
        "  process(clk, rst_n)",
        "  begin",
        "    if rst_n = '0' then",
        *assignments,
        "    elsif rising_edge(clk) then",
        "      -- deterministic synchronous update region",
        "      -- no combinational loops should be introduced in manual completion",
        "      null;",
        "    end if;",
        "  end process;",
        "end architecture rtl;",
        "",
    ]
    return "\n".join(lines)
