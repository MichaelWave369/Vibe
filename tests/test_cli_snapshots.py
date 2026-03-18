from pathlib import Path

from vibe.cli import main


def test_explain_snapshot_includes_experimental_sections(capsys, tmp_path) -> None:
    src = Path("vibe/examples/sovereign_bridge.vibe")
    case = tmp_path / "sovereign_bridge.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    code = main(["explain", str(case)])
    assert code == 0

    out = capsys.readouterr().out
    assert "AST:" in out
    assert "Normalized IR:" in out
    assert '"tesla_layer"' in out
    assert '"agentora"' in out
    assert "tesla_enabled: True" in out
    assert "agent metrics:" in out
    assert "equivalence/drift:" in out


def test_verify_json_snapshot_contains_bridge_and_agent_metrics(capsys, tmp_path) -> None:
    src = Path("vibe/examples/agentora_agentception.vibe")
    case = tmp_path / "agentora_agentception.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    code = main(["verify", str(case), "--report", "json"])
    assert code == 0

    out = capsys.readouterr().out
    assert '"agent_count": 3' in out
    assert '"spawn_depth": 3' in out
    assert '"delegation_integrity"' in out
    assert '"bridge_score"' in out
    assert '"passed": true' in out
    assert '"verification_backend": "heuristic"' in out
    assert '"intent_equivalence_score"' in out


def test_verify_symbolic_backend_fails_gracefully(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    code = main(["verify", str(case), "--backend", "symbolic"])
    assert code == 1

    out = capsys.readouterr().out
    assert "not implemented yet" in out


def test_verify_smt_backend_reports_solver_metadata(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    code = main(["verify", str(case), "--backend", "smt", "--report", "json"])
    assert code == 0

    out = capsys.readouterr().out
    assert '"verification_backend": "smt"' in out
    assert '"solver_evaluated"' in out
