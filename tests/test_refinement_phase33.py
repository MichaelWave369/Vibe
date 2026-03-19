import json
from pathlib import Path

from vibe.cli import main
from vibe.proof import load_proof_artifact
from vibe.verifier import VerificationObligation, VerificationResult


def _result(*, passed: bool, code: str) -> VerificationResult:
    obligation = VerificationObligation(
        obligation_id="preserve.latency",
        category="preserve",
        description="latency budget",
        source_location=None,
        status="satisfied" if passed else "violated",
        evidence="marker" if passed else "missing marker",
        critical=True,
    )
    return VerificationResult(
        c_bar=1.0,
        epsilon_pre=0.9,
        epsilon_post=0.9,
        measurement_ratio=1.0 if passed else 0.7,
        q_persistence=1.0,
        q_spatial_consistency=1.0,
        q_cohesion=1.0,
        q_alignment=1.0,
        q_intent_constant=1.0,
        petra_alignment=1.0,
        multimodal_resonance=1.0,
        bridge_score=1.0 if passed else 0.6,
        verdict="PASS" if passed else "FAIL",
        passed=passed,
        obligations=[obligation],
        obligation_counts={"satisfied": 1 if passed else 0, "violated": 0 if passed else 1, "unknown": 0, "not_applicable": 0},
        intent_items_total=1,
        intent_items_matched=1 if passed else 0,
        intent_items_missing=0 if passed else 1,
        intent_items_extra=0,
        mapping_notes=[f"len={len(code)}"],
    )


def test_refinement_stops_when_later_iteration_passes(monkeypatch, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    def fake_verify(ir, code, backend="heuristic", fallback_backend=None, use_calibration=True):
        return _result(passed=("refinement_round_2" in code), code=code)

    monkeypatch.setattr("vibe.cli.verify", fake_verify)

    rc = main(["compile", str(case), "--refine", "--max-iters", "3", "--write-proof"])
    assert rc == 0

    emitted = case.with_suffix(".py")
    assert emitted.exists()
    assert "refinement_round_2" in emitted.read_text(encoding="utf-8")

    proof = load_proof_artifact(case.with_suffix(".vibe.proof.json"))
    ref = proof["refinement"]
    assert ref["refinement_enabled"] is True
    assert ref["refinement_success"] is True
    assert ref["refinement_iterations_run"] == 2


def test_refinement_honestly_fails_on_max_iteration(monkeypatch, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("vibe.cli.verify", lambda *args, **kwargs: _result(passed=False, code=args[1]))

    rc = main(["compile", str(case), "--refine", "--max-iters", "2", "--write-proof"])
    assert rc == 1
    assert not case.with_suffix(".py").exists()

    proof = load_proof_artifact(case.with_suffix(".vibe.proof.json"))
    ref = proof["refinement"]
    assert ref["hit_max_iterations"] is True
    assert ref["refinement_success"] is False


def test_refinement_history_is_deterministic(monkeypatch, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("vibe.cli.verify", lambda *args, **kwargs: _result(passed=("refinement_round_2" in args[1]), code=args[1]))

    main(["compile", str(case), "--refine", "--max-iters", "3", "--write-proof"])
    first = load_proof_artifact(case.with_suffix(".vibe.proof.json"))["refinement"]["refinement_history"]
    main(["compile", str(case), "--refine", "--max-iters", "3", "--write-proof"])
    second = load_proof_artifact(case.with_suffix(".vibe.proof.json"))["refinement"]["refinement_history"]
    assert first == second


def test_compile_report_json_includes_refinement_metadata(monkeypatch, capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("vibe.cli.verify", lambda *args, **kwargs: _result(passed=True, code=args[1]))

    rc = main(["compile", str(case), "--refine", "--max-iters", "4", "--report", "json"])
    assert rc == 0

    out = capsys.readouterr().out
    json_block = out[out.find("{") : out.rfind("}") + 1]
    payload = json.loads(json_block)
    assert payload["refinement_enabled"] is True
    assert payload["refinement_iterations_run"] == 1
    assert payload["refinement_max_iterations"] == 4
    assert "refinement_history" in payload


def test_refinement_typescript_path(monkeypatch, tmp_path) -> None:
    src = Path("vibe/examples/edge_contract_ts.vibe")
    case = tmp_path / "edge_contract_ts.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("vibe.cli.verify", lambda *args, **kwargs: _result(passed=("refinement_round_2" in args[1]), code=args[1]))

    rc = main(["compile", str(case), "--refine", "--max-iters", "3"])
    assert rc == 0
    assert case.with_suffix(".ts").exists()
