from pathlib import Path

from vibe.ir import ast_to_ir, serialize_ir
from vibe.parser import parse_source


EXAMPLE = Path("vibe/examples/sovereign_bridge.vibe")


def test_ssa_value_ids_are_unique() -> None:
    ir = ast_to_ir(parse_source(EXAMPLE.read_text(encoding="utf-8")))
    ids = list(ir.module.values.keys())
    assert len(ids) == len(set(ids))


def test_def_use_references_are_valid() -> None:
    ir = ast_to_ir(parse_source(EXAMPLE.read_text(encoding="utf-8")))
    refs = [b.value_id for b in ir.module.bindings]
    refs += [r.key_ref for r in ir.module.preserve_rules]
    refs += [r.value_ref for r in ir.module.preserve_rules]
    refs += [c.text_ref for c in ir.module.constraints]
    refs += [s.key_ref for s in ir.module.bridge_settings]
    refs += [s.value_ref for s in ir.module.bridge_settings]
    refs += [ir.module.emit_target_ref]
    assert all(r in ir.module.values for r in refs)


def test_typed_nodes_present() -> None:
    ir = ast_to_ir(parse_source(EXAMPLE.read_text(encoding="utf-8")))
    assert any(v.vtype == "frequency" for v in ir.module.values.values())
    assert any(v.vtype == "list" for v in ir.module.values.values())
    assert ir.module.tesla_layer is not None


def test_ir_serialization_is_deterministic() -> None:
    ir = ast_to_ir(parse_source(EXAMPLE.read_text(encoding="utf-8")))
    s1 = serialize_ir(ir)
    s2 = serialize_ir(ir)
    assert s1 == s2
    assert '"module_name": "SovereignBridge"' in s1
