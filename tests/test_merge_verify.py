import json
from pathlib import Path

from vibe.cli import main


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_merge_verify_non_conflicting_success_and_verification_summary(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
constraint:
  deterministic ordering
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
constraint:
  deterministic ordering
  graceful fallback
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
constraint:
  deterministic ordering
bridge:
  epsilon_floor = 0.03
  measurement_safe_ratio = 0.85
emit python
""",
    )

    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["report_type"] == "merge_verify"
    assert payload["merge_status"] == "merged"
    assert payload["intent_outcome"] in {"merged_verified", "merged_verification_failed"}
    assert payload["merged_text"]
    assert payload["verification"] is not None
    assert payload["verification_context"]["available"] is True
    assert payload["verification_context"]["base"]["bridge_score"] is not None
    assert payload["verification_context"]["left"]["bridge_score"] is not None
    assert payload["verification_context"]["right"]["bridge_score"] is not None
    assert payload["verification_context"]["merged"]["bridge_score"] is not None
    assert isinstance(payload["verification_context"]["bridge_score_delta_vs_base"], float)
    assert payload["regression_evidence"]["available"] is True
    assert payload["regression_evidence"]["total_problem_obligations"] == 0
    assert payload["regression_evidence"]["top_problem_obligations"] == []
    for key in ["bridge_score", "epsilon_post", "measurement_ratio", "obligations_total", "obligations_satisfied"]:
        assert key in payload["verification"]


def test_merge_verify_identical_changes_merge_cleanly(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "g2"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
intent M:
  goal: "g2"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )

    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["merge_status"] == "merged"
    assert 'goal: "g2"' in payload["merged_text"]


def test_merge_verify_conflict_reports_structured_conflicts(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "left-goal"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
intent M:
  goal: "right-goal"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )

    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["merge_status"] == "conflict"
    assert payload["intent_outcome"] == "structural_conflict"
    assert payload["verification"] is None
    assert payload["verification_context"]["available"] is False
    assert payload["verification_context"]["reason"] == "merge_conflict_no_merged_spec"
    assert payload["intent_conflicts"] == []
    assert payload["regression_evidence"]["available"] is False
    assert payload["regression_evidence"]["reason"] == "merge_conflict_no_merged_spec"
    assert payload["conflicts"]
    c0 = payload["conflicts"][0]
    assert {"address", "conflict_type", "base_value", "left_value", "right_value"}.issubset(c0.keys())
    assert c0["address"].startswith("intent::M::")


def test_merge_verify_merged_but_verification_failed_is_not_conflict(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 1.2
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
emit python
""",
    )

    rc = main(["merge-verify", str(base), str(left), str(right), "--report", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["merge_status"] == "merged"
    assert payload["intent_outcome"] == "merged_verification_failed"
    assert payload["verification"] is not None
    assert payload["verification"]["passed"] is False
    assert payload["intent_conflicts"]
    assert any(c["conflict_type"] in {"obligation_violation", "verification_regression"} for c in payload["intent_conflicts"])
    assert payload["regression_evidence"]["available"] is True
    assert payload["regression_evidence"]["total_problem_obligations"] >= 1
    assert payload["regression_evidence"]["shown_problem_obligations"] >= 1
    assert payload["regression_evidence"]["top_problem_obligations"]
    expected = json.loads(Path("tests/fixtures/merge_verify/regression_evidence_failure.json").read_text(encoding="utf-8"))
    assert payload["regression_evidence"]["available"] == expected["available"]
    assert payload["regression_evidence"]["selection_policy"] == expected["selection_policy"]
    first = payload["regression_evidence"]["top_problem_obligations"][0]
    assert {"id", "category", "address", "status", "severity", "message"}.issubset(first.keys())
    assert rc == 1


def test_merge_verify_threshold_weakening_classification(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
bridge:
  epsilon_floor = 0.10
  measurement_safe_ratio = 0.90
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
bridge:
  epsilon_floor = 0.05
  measurement_safe_ratio = 0.80
emit python
""",
    )
    right = _write(tmp_path / "right.vibe", base.read_text(encoding="utf-8"))

    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["merge_status"] == "merged"
    kinds = {c["conflict_type"] for c in payload["intent_conflicts"]}
    assert "threshold_weakening" in kinds


def test_merge_verify_regression_evidence_is_bounded_and_stably_sorted(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    a: number
  outputs:
    b: number
constraint:
  deterministic ordering
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "g"
  inputs:
    a: number
  outputs:
    b: number
preserve:
  p0 = false
  p1 = false
  p2 = false
  p3 = false
  p4 = false
  p5 = false
constraint:
  deterministic ordering
bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 1.20
emit python
""",
    )
    right = _write(tmp_path / "right.vibe", base.read_text(encoding="utf-8"))

    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    evidence = payload["regression_evidence"]
    assert evidence["available"] is True
    assert evidence["total_problem_obligations"] >= evidence["shown_problem_obligations"]
    assert evidence["shown_problem_obligations"] <= 5
    assert len(evidence["top_problem_obligations"]) == evidence["shown_problem_obligations"]
    rows = evidence["top_problem_obligations"]
    keys = [(r["severity"], r["status"], r["category"], r["id"], r["address"] or "") for r in rows]
    assert keys == sorted(
        keys,
        key=lambda x: (
            -({"error": 3, "warning": 2, "advisory": 1, "info": 0}.get(x[0], 0)),
            -({"violated": 2, "unknown": 1}.get(x[1], 0)),
            x[2],
            x[3],
            x[4],
        ),
    )


def test_merge_verify_write_merged_only_on_success(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "left-goal"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
intent M:
  goal: "right-goal"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    out_path = tmp_path / "merged.vibe"
    assert main(["merge-verify", str(base), str(left), str(right), "--write-merged", str(out_path)]) == 1
    assert not out_path.exists()

    capsys.readouterr()
    left_ok = _write(
        tmp_path / "left_ok.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
    z: number
  outputs:
    y: number
emit python
""",
    )
    assert main(["merge-verify", str(base), str(left_ok), str(right), "--write-merged", str(out_path), "--report", "json"]) in {
        0,
        1,
    }
    assert out_path.exists()


def test_merge_verify_merges_vibe_metadata_and_declarations(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
vibe_version 1.1
import std.core
module resonance.bridge
type SignalState
enum BridgeMode
interface PreservationContract

intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
vibe_version 1.1
import std.core
import std.math
module resonance.bridge
type SignalState
enum BridgeMode
interface PreservationContract

intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
vibe_version 1.1
import std.core
module resonance.bridge
module extra.mod
type SignalState
enum BridgeMode
interface PreservationContract

intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["merge_status"] == "merged"
    text = payload["merged_text"]
    assert "import std.math" in text
    assert "module extra.mod" in text


def test_merge_verify_agent_conflict_has_specific_type_and_normalized_address(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number

agentora {
  agent Router {
    role: "route"
    tools: ["db"]
    memory: "session"
    intention: "route safely"
    constraints: ["deterministic"]
    preserve: ["deterministic"]
  }
}

emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        base.read_text(encoding="utf-8").replace('"route safely"', '"route left"'),
    )
    right = _write(
        tmp_path / "right.vibe",
        base.read_text(encoding="utf-8").replace('"route safely"', '"route right"'),
    )
    assert main(["merge-verify", str(base), str(left), str(right), "--report", "json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["merge_status"] == "conflict"
    agent_conflicts = [c for c in payload["conflicts"] if c["conflict_type"] == "agent_conflict"]
    assert agent_conflicts
    assert agent_conflicts[0]["address"] == "intent::M::agent::Router"


def test_merge_verify_write_merge_report_for_conflict_and_success(tmp_path: Path, capsys) -> None:
    base = _write(
        tmp_path / "base.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    left = _write(
        tmp_path / "left.vibe",
        """
intent M:
  goal: "left"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    right = _write(
        tmp_path / "right.vibe",
        """
intent M:
  goal: "right"
  inputs:
    x: number
  outputs:
    y: number
emit python
""",
    )
    report_path = tmp_path / "merge-report-conflict.json"
    assert (
        main(
            [
                "merge-verify",
                str(base),
                str(left),
                str(right),
                "--report",
                "json",
                "--write-merge-report",
                str(report_path),
            ]
        )
        == 1
    )
    payload_conflict = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload_conflict["merge_status"] == "conflict"
    assert payload_conflict["conflicts"]
    assert "verification_context" in payload_conflict
    assert "intent_conflicts" in payload_conflict
    assert "regression_evidence" in payload_conflict

    capsys.readouterr()
    left_ok = _write(
        tmp_path / "left_ok.vibe",
        """
intent M:
  goal: "g"
  inputs:
    x: number
    z: number
  outputs:
    y: number
emit python
""",
    )
    report_ok = tmp_path / "merge-report-success.json"
    rc = main(
        [
            "merge-verify",
            str(base),
            str(left_ok),
            str(right),
            "--report",
            "json",
            "--write-merge-report",
            str(report_ok),
        ]
    )
    payload_ok = json.loads(report_ok.read_text(encoding="utf-8"))
    assert payload_ok["merge_status"] == "merged"
    assert payload_ok["verification"] is not None
    assert payload_ok["verification_context"]["available"] is True
    assert payload_ok["regression_evidence"]["available"] is True
    assert rc in {0, 1}


def test_diff_verification_context_failure_path_is_machine_readable(tmp_path: Path, capsys, monkeypatch) -> None:
    old_case = _write(tmp_path / "old.vibe", Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"))
    new_case = _write(tmp_path / "new.vibe", Path("vibe/examples/edge_contract_ts.vibe").read_text(encoding="utf-8"))

    def _boom(*args, **kwargs):
        raise RuntimeError("forced verifier failure")

    monkeypatch.setattr("vibe.cli.verify", _boom)
    assert main(["diff", str(old_case), str(new_case), "--report", "json", "--with-verification-context"]) == 0
    payload = json.loads(capsys.readouterr().out)
    vc = payload["verification_context"]
    assert vc["verification_requested"] is True
    assert vc["available"] is False
    assert "forced verifier failure" in vc["reason"]
