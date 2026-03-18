from pathlib import Path

from vibe.generator_python import generate_python
from vibe.ir import ast_to_ir
from vibe.parser import parse_source


EXAMPLE = Path("vibe/examples/payment_router.vibe")


def test_generation_is_deterministic() -> None:
    ir = ast_to_ir(parse_source(EXAMPLE.read_text(encoding="utf-8")))
    g1 = generate_python(ir)
    g2 = generate_python(ir)
    assert g1 == g2
    assert "def payment_router(" in g1
    assert "fallback_processor" in g1
