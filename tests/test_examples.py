from pathlib import Path

from vibe.cli import main
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.verifier import verify


EXAMPLES = [
    Path("vibe/examples/payment_router.vibe"),
    Path("vibe/examples/csv_api.vibe"),
    Path("vibe/examples/tesla_victory_layer.vibe"),
    Path("vibe/examples/agentora_agentception.vibe"),
    Path("vibe/examples/sovereign_bridge.vibe"),
    Path("vibe/examples/edge_contract_ts.vibe"),
    Path("vibe/examples/shared_intent_ts.vibe"),
]


def test_examples_compile_semantically() -> None:
    for path in EXAMPLES:
        ast = parse_source(path.read_text(encoding="utf-8"))
        ir = ast_to_ir(ast)
        code, _ = emit_code(ir)
        result = verify(ir, code)
        assert ir.emit_target in {"python", "typescript"}
        assert result.passed is True


def test_cli_smoke_report_modes(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    path = tmp_path / "payment_router.vibe"
    path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    explain_code = main(["explain", str(path)])
    assert explain_code == 0

    verify_code = main(["verify", str(path), "--report", "json"])
    assert verify_code == 0

    compile_code = main(["compile", str(path), "--report", "json"])
    assert compile_code == 0

    out = capsys.readouterr().out
    assert "Normalized IR" in out
    assert '"bridge_score"' in out
    assert "emitted:" in out
