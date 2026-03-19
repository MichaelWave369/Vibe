from __future__ import annotations

import json
import os
from pathlib import Path

from vibe.ci import CICheckConfig, run_ci_check


def _input(name: str, default: str) -> str:
    # GitHub usually exposes INPUT_<name> with uppercase and hyphens kept.
    # We also accept underscore variants for local testing ergonomics.
    hyphen_key = f"INPUT_{name.upper()}"
    underscore_key = hyphen_key.replace("-", "_")
    return os.environ.get(hyphen_key, os.environ.get(underscore_key, default))


def _get_bool(name: str, default: bool = False) -> bool:
    raw = _input(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _set_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as f:
        f.write(f"{name}={value}\n")


def _append_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as f:
        f.write(markdown)


def main() -> int:
    config = CICheckConfig(
        files_glob=_input("FILES", "**/*.vibe"),
        fail_on=_input("FAIL-ON", ""),
        report_json_path=_input("REPORT-JSON-PATH", ".vibe_ci/bridge_report.json"),
        backend=_input("BACKEND", "heuristic"),
        fallback_backend=(_input("FALLBACK-BACKEND", "").strip() or None),
        with_proofs=_get_bool("WITH-PROOFS", False),
        with_tests=_get_bool("WITH-TESTS", False),
    )

    report, code = run_ci_check(config, root=Path.cwd())

    _set_output("files_checked", str(report["files_checked"]))
    _set_output("files_failed", str(report["files_failed"]))
    _set_output("worst_bridge_score", str(report["worst_bridge_score"]))
    _set_output("report_json_path", str(report["report_json_path"]))
    _set_output("summary_markdown_path", str(report["summary_markdown_path"]))
    _set_output("proof_paths", json.dumps(report.get("proof_paths", []), sort_keys=True))

    summary = Path(str(report["summary_markdown_path"])).read_text(encoding="utf-8")
    _append_summary(summary)

    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
