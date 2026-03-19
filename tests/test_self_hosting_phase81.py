import json
from pathlib import Path

from vibe.cli import main
from vibe.proof import load_proof_artifact
from vibe.self_hosting import SelfCheckConfig, run_self_check


def test_self_spec_verify_and_compile_flow() -> None:
    spec = Path("self_hosting/vibec_core.vibe")
    assert main(["verify", str(spec), "--report", "json"]) == 0
    assert main(["compile", str(spec), "--no-cache"]) == 0


def test_self_check_deterministic_output_without_baseline(tmp_path: Path) -> None:
    spec = Path("self_hosting/vibec_core.vibe")
    baseline = tmp_path / "baseline.json"
    r1 = run_self_check(SelfCheckConfig(spec_path=spec, baseline_path=baseline, write_proof=False))
    r2 = run_self_check(SelfCheckConfig(spec_path=spec, baseline_path=baseline, write_proof=False))
    assert r1.summary == r2.summary
    assert r1.summary["self_regression_status"] == "no_baseline"
    assert r1.exit_code == 0


def test_self_check_regression_surface_and_fail_mode(tmp_path: Path) -> None:
    spec = Path("self_hosting/vibec_core.vibe")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "compiler_spec_path": str(spec),
                "self_bridge_score": 1.0,
                "measurement_ratio": 1.0,
                "passed": True,
                "proof_artifact_paths": [],
                "key_obligations": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    checked = run_self_check(
        SelfCheckConfig(
            spec_path=spec,
            baseline_path=baseline,
            fail_on_regression=True,
            max_bridge_drop=0.0,
            write_proof=False,
        )
    )
    assert checked.summary["baseline_available"] is True
    assert checked.summary["self_regression_status"] in {"stable", "improved", "regressed"}
    if checked.summary["regressed"]:
        assert checked.exit_code == 1


def test_self_check_writes_and_exposes_proof_metadata(tmp_path: Path) -> None:
    spec = tmp_path / "spec.vibe"
    spec.write_text(Path("self_hosting/vibec_core.vibe").read_text(encoding="utf-8"), encoding="utf-8")
    checked = run_self_check(SelfCheckConfig(spec_path=spec, write_proof=True))
    assert checked.summary["proof_artifact_paths"]
    proof = load_proof_artifact(spec.with_suffix(".vibe.proof.json"))
    assert "self_hosting" in proof
    assert proof["self_hosting"]["self_hosting_enabled"] is True
    assert proof["self_hosting"]["compiler_spec_path"] == str(spec)


def test_cli_self_check_json_and_baseline_update(tmp_path: Path, capsys) -> None:
    spec = Path("self_hosting/vibec_core.vibe")
    baseline = tmp_path / "compiler_self_bridge_baseline.json"

    rc = main(
        [
            "self-check",
            "--spec",
            str(spec),
            "--baseline-path",
            str(baseline),
            "--update-baseline",
            "--report",
            "json",
        ]
    )
    assert rc == 0
    payload1 = json.loads(capsys.readouterr().out)
    assert payload1["self_hosting"]["self_hosting_enabled"] is True
    assert baseline.exists()

    rc = main(
        [
            "self-check",
            "--spec",
            str(spec),
            "--baseline-path",
            str(baseline),
            "--report",
            "json",
        ]
    )
    assert rc == 0
    payload2 = json.loads(capsys.readouterr().out)
    assert payload2["self_hosting"]["baseline_available"] is True
