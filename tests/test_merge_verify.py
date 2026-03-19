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
    assert payload["merged_text"]
    assert payload["verification"] is not None
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
    assert payload["verification"] is None
    assert payload["conflicts"]
    c0 = payload["conflicts"][0]
    assert {"address", "conflict_type", "base_value", "left_value", "right_value"}.issubset(c0.keys())


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
    assert payload["verification"] is not None
    assert payload["verification"]["passed"] is False
    assert rc == 1


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
