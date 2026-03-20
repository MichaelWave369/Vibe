import json
from pathlib import Path

from vibe.cli import main
from vibe.ir import ast_to_ir
from vibe.lexer import lex
from vibe.parser import ParseError, parse_source
from vibe.proof import build_proof_artifact
from vibe.verifier import verify


def test_lexer_emits_sigil_tokens() -> None:
    tokens = lex("sigil:\n  pulse: ⟨Φ⟩⟢⟨∇⟩⟢⟨Ω⟩\n")
    assert [t.kind for t in tokens] == ["BLOCK", "SIGIL"]


def test_parser_accepts_sigil_blocks() -> None:
    src = Path("vibe/examples/sigil_temporal.vibe").read_text(encoding="utf-8")
    program = parse_source(src)
    assert len(program.sigils) == 2
    assert len(program.sigil_sequences) == 1


def test_parser_rejects_bad_sigil_expression() -> None:
    src = """
intent BadSigil:
  goal: "x"
  inputs:
    a: symbol
  outputs:
    b: symbol
sigil:
  broken: Φ->Ω
emit python
"""
    try:
        parse_source(src)
    except ParseError as exc:
        assert "Invalid sigil expression" in str(exc)
    else:
        raise AssertionError("expected ParseError")


def test_ir_contains_canonical_sigil_graph() -> None:
    src = Path("vibe/examples/sigil_collective.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    assert ir.module.sigil_graph["kind"] == "SigilGraph"
    assert ir.module.sigil_graph["edges"]


def test_verifier_surfaces_sigil_obligations() -> None:
    src = Path("vibe/examples/sigil_temporal.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    result = verify(ir, "def sigil_temporal(signal):\n    return signal\n")
    obligation_ids = {row["obligation_id"] for row in result.sigil_obligations}
    assert "sigil.temporal.sequence.coherent" in obligation_ids
    assert "sigil.bridge.threshold.passed" in obligation_ids


def test_cli_sigil_validate_and_inspect_json(capsys, tmp_path) -> None:
    src = Path("vibe/examples/sigil_basic.vibe")
    case = tmp_path / "sigil_basic.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["sigil-validate", str(case), "--report", "json"]) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is True

    assert main(["sigil-inspect", str(case), "--report", "json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["sigil_graph"]["kind"] == "SigilGraph"


def test_proof_artifact_includes_sigil_evidence() -> None:
    source_path = Path("vibe/examples/sigil_basic.vibe")
    source_text = source_path.read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(source_text))
    result = verify(ir, "def sigil_basic(source):\n    return source\n")
    artifact = build_proof_artifact(source_path, source_text, ir, result, emitted_blocked=not result.passed)
    assert "sigils" in artifact
    assert artifact["sigils"]["summary"]["sigil_count"] >= 1
