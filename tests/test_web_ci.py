from pathlib import Path

from vibe.ci import run_file_check


def test_ci_bridge_check_routes_web_page_via_sidecar() -> None:
    checked = run_file_check(
        Path("vibe/examples/web_counter.vibe"),
        backend="heuristic",
        fallback_backend=None,
        with_proofs=False,
        with_tests=False,
    )
    assert checked.passed
    assert checked.bridge_score >= 0.85
    assert checked.verdict not in {"ENTROPY_NOISE", "FIELD_COLLAPSE_ERROR"}
