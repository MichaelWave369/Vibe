from pathlib import Path

from vibe.generator_python import generate_python
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.verifier import verify


EXAMPLE = Path("vibe/examples/payment_router.vibe")


def test_verifier_passes_example() -> None:
    ir = ast_to_ir(parse_source(EXAMPLE.read_text(encoding="utf-8")))
    result = verify(ir, generate_python(ir))
    assert result.passed is True
    assert result.measurement_ratio >= 0.85


def test_verifier_fails_when_thresholds_are_impossible() -> None:
    src = """
intent HardMode:
  goal: "Tiny"
  inputs:
    x: number
  outputs:
    y: number
bridge:
  epsilon_floor = 0.7
  measurement_safe_ratio = 0.99
emit python
"""
    ir = ast_to_ir(parse_source(src))
    result = verify(ir, "def hardmode(x: float) -> float:\n    return x\n")
    assert result.passed is False
