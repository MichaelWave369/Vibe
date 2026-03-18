from pathlib import Path

from vibe.cli import main
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source


def test_backend_selection_from_emit_target() -> None:
    src = Path("vibe/examples/edge_contract_ts.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    code, backend = emit_code(ir)
    assert backend.target == "typescript"
    assert "export function" in code


def test_typescript_generation_is_deterministic() -> None:
    src = Path("vibe/examples/edge_contract_ts.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    c1, _ = emit_code(ir)
    c2, _ = emit_code(ir)
    assert c1 == c2


def test_compile_typescript_example_success(tmp_path) -> None:
    src = Path("vibe/examples/edge_contract_ts.vibe")
    case = tmp_path / "edge_contract_ts.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    rc = main(["compile", str(case)])
    assert rc == 0
    assert case.with_suffix(".ts").exists()


def test_compile_blocked_on_preservation_failure(tmp_path) -> None:
    src = """
intent HardFailTs:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.7
  measurement_safe_ratio = 0.99
emit typescript
"""
    case = tmp_path / "hard_fail_ts.vibe"
    case.write_text(src, encoding="utf-8")
    rc = main(["compile", str(case)])
    assert rc == 1
    assert not case.with_suffix(".ts").exists()
