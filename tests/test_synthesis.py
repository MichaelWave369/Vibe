from pathlib import Path

from vibe.cli import main
from vibe.synthesis import generate_candidates, rank_candidate, rank_candidates
from vibe.emitter import emit_code
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.verifier import verify


def test_generate_multiple_candidates_deterministic() -> None:
    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    c1 = generate_candidates(ir, 3)
    c2 = generate_candidates(ir, 3)
    assert [c.code for c in c1] == [c.code for c in c2]
    assert len(c1) == 3


def test_compile_with_candidates_selects_passing_winner(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["compile", str(case), "--candidates", "3"])
    assert rc == 0
    assert case.with_suffix(".py").exists()


def test_compile_no_emission_when_all_candidates_fail(tmp_path) -> None:
    src = """
intent HardFail:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.99
  measurement_safe_ratio = 1.4
emit python
"""
    case = tmp_path / "hard_fail.vibe"
    case.write_text(src, encoding="utf-8")
    rc = main(["compile", str(case), "--candidates", "3"])
    assert rc == 1
    assert not case.with_suffix(".py").exists()


def test_ranking_is_deterministic() -> None:
    src = Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(src))
    candidates = generate_candidates(ir, 3)
    evals = []
    for c in candidates:
        r = verify(ir, c.code)
        evals.append(rank_candidate(c.candidate_id, c.strategy, r))
    ranked1 = rank_candidates(evals)
    ranked2 = rank_candidates(evals)
    assert [x.candidate_id for x in ranked1] == [x.candidate_id for x in ranked2]


def test_verify_json_includes_candidate_summary(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--report", "json", "--candidates", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"candidate_count"' in out
    assert '"winning_candidate_id"' in out


def test_proof_includes_candidate_metadata(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--write-proof", "--candidates", "3"])
    assert rc == 0
    proof = case.with_suffix(".vibe.proof.json").read_text(encoding="utf-8")
    assert '"candidates"' in proof
    assert '"candidate_count"' in proof
