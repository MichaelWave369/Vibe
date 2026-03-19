from pathlib import Path

from vibe.generator_python import generate_python
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.verifier import verify


EXAMPLES = [
    Path("vibe/examples/payment_router.vibe"),
    Path("vibe/examples/csv_api.vibe"),
]


def test_examples_compile_semantically() -> None:
    for path in EXAMPLES:
        ast = parse_source(path.read_text(encoding="utf-8"))
        ir = ast_to_ir(ast)
        code = generate_python(ir)
        result = verify(ir, code)
        assert ir.emit_target == "python"
        assert result.passed is True
