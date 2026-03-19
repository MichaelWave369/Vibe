import json
import os
from pathlib import Path
import subprocess
import sys

from vibe.ci import CICheckConfig, discover_vibe_files, parse_fail_on, render_markdown_summary, run_ci_check
from vibe.cli import main


def _write_vibe(path: Path, name: str = "A") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""intent {name}:
  goal: \"g\"
  inputs:
    x: number
  outputs:
    y: number

emit python
""",
        encoding="utf-8",
    )


def test_parse_fail_on_and_discovery(tmp_path: Path) -> None:
    _write_vibe(tmp_path / "a.vibe")
    _write_vibe(tmp_path / "src" / "b.vibe")
    rules = parse_fail_on("ENTROPY_NOISE, bridge_score_below_threshold:0.9, ENTROPY_NOISE")
    assert rules == ["ENTROPY_NOISE", "bridge_score_below_threshold:0.9"]
    files = discover_vibe_files("**/*.vibe", root=tmp_path)
    assert [p.name for p in files] == ["a.vibe", "b.vibe"]


def test_ci_check_deterministic_json_and_markdown(tmp_path: Path) -> None:
    _write_vibe(tmp_path / "main.vibe", "Main")
    cfg = CICheckConfig(files_glob="**/*.vibe", report_json_path=".vibe_ci/report.json")
    report1, code1 = run_ci_check(cfg, root=tmp_path)
    report2, code2 = run_ci_check(cfg, root=tmp_path)

    assert code1 == 0 == code2
    assert report1["files_checked"] == 1
    assert report1["files_failed"] == 0
    assert json.dumps(report1, sort_keys=True) == json.dumps(report2, sort_keys=True)

    report_path = Path(report1["report_json_path"])
    assert report_path.exists()
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["files_checked"] == 1

    summary_path = Path(report1["summary_markdown_path"])
    md = summary_path.read_text(encoding="utf-8")
    assert "Vibe Bridge Check Summary" in md
    assert "main.vibe" in md


def test_ci_fail_on_gating_and_threshold(tmp_path: Path) -> None:
    _write_vibe(tmp_path / "main.vibe")

    cfg_verdict = CICheckConfig(files_glob="**/*.vibe", fail_on="MULTIMODAL_BRIDGE_STABLE", report_json_path=".vibe_ci/r1.json")
    report_v, code_v = run_ci_check(cfg_verdict, root=tmp_path)
    assert code_v == 1
    assert report_v["files_failed"] == 1

    cfg_threshold = CICheckConfig(files_glob="**/*.vibe", fail_on="bridge_score_below_threshold:1.1", report_json_path=".vibe_ci/r2.json")
    report_t, code_t = run_ci_check(cfg_threshold, root=tmp_path)
    assert code_t == 1
    assert report_t["files_failed"] == 1


def test_ci_with_proofs_and_cli_helper(tmp_path: Path, capsys) -> None:
    _write_vibe(tmp_path / "main.vibe")

    cfg = CICheckConfig(files_glob="**/*.vibe", with_proofs=True, report_json_path=".vibe_ci/proofs.json")
    report, code = run_ci_check(cfg, root=tmp_path)
    assert code == 0
    assert report["proof_paths"]
    assert all(Path(p).exists() for p in report["proof_paths"])

    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        rc = main([
            "ci-check",
            "--files",
            "**/*.vibe",
            "--report",
            "json",
            "--report-json-path",
            ".vibe_ci/cli_report.json",
        ])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["files_checked"] == 1
        assert Path(payload["summary_markdown_path"]).exists()
    finally:
        os.chdir(cwd)


def test_markdown_renderer_is_stable() -> None:
    report = {
        "overall_passed": False,
        "files_checked": 2,
        "files_failed": 1,
        "worst_bridge_score": 0.5,
        "results": [
            {
                "file_path": "a.vibe",
                "passed": True,
                "bridge_score": 0.9,
                "measurement_ratio": 0.9,
                "verdict": "MULTIMODAL_BRIDGE_STABLE",
                "fail_on_hits": [],
            },
            {
                "file_path": "b.vibe",
                "passed": False,
                "bridge_score": 0.5,
                "measurement_ratio": 0.5,
                "verdict": "ENTROPY_NOISE",
                "fail_on_hits": ["ENTROPY_NOISE"],
            },
        ],
    }
    md1 = render_markdown_summary(report)
    md2 = render_markdown_summary(report)
    assert md1 == md2
    assert "ENTROPY_NOISE" in md1


def test_action_script_writes_outputs_and_summary(tmp_path: Path) -> None:
    _write_vibe(tmp_path / "ci.vibe")
    repo_root = Path(__file__).resolve().parents[1]
    output_file = tmp_path / "github_output.txt"
    summary_file = tmp_path / "github_summary.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    env["INPUT_FILES"] = "**/*.vibe"
    env["INPUT_FAIL_ON"] = ""
    env["INPUT_REPORT_JSON_PATH"] = ".vibe_ci/action_report.json"
    env["GITHUB_OUTPUT"] = str(output_file)
    env["GITHUB_STEP_SUMMARY"] = str(summary_file)
    script = repo_root / ".github" / "actions" / "bridge-check" / "run_bridge_check.py"
    proc = subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert proc.returncode == 0
    assert output_file.exists()
    assert "files_checked=1" in output_file.read_text(encoding="utf-8")
    assert summary_file.exists()
    assert "Vibe Bridge Check Summary" in summary_file.read_text(encoding="utf-8")


def test_example_workflow_sanity() -> None:
    pr_workflow = Path(".github/workflows/bridge-check-pr.yml").read_text(encoding="utf-8")
    push_workflow = Path(".github/workflows/bridge-check-push.yml").read_text(encoding="utf-8")
    assert "uses: ./" in pr_workflow
    assert "fail-on: 'ENTROPY_NOISE'" in pr_workflow
    assert "upload-artifact@v4" in pr_workflow
    assert "uses: ./" in push_workflow
    assert "bridge_score_below_threshold:0.85" in push_workflow
