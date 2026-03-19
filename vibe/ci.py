"""Phase 6.4: GitHub Actions native bridge-check integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .emitter import emit_code
from .ir import ast_to_ir
from .manifest import VibeManifest
from .package_manager import apply_package_defaults_to_source, package_context_for_path
from .parser import parse_source
from .proof import build_proof_artifact, default_proof_path, write_proof_artifact
from .testgen import generate_intent_guided_tests
from .verifier import verify


@dataclass(slots=True)
class CICheckConfig:
    files_glob: str = "**/*.vibe"
    fail_on: str = ""
    report_json_path: str = ".vibe_ci/bridge_report.json"
    backend: str = "heuristic"
    fallback_backend: str | None = None
    with_proofs: bool = False
    with_tests: bool = False


@dataclass(slots=True)
class FileCheckResult:
    file_path: str
    passed: bool
    bridge_score: float
    measurement_ratio: float
    verdict: str
    backend: str
    obligation_summary: dict[str, int]
    intent_equivalence_score: float
    drift_score: float
    proof_path: str | None
    generated_test_files: list[str]



def parse_fail_on(fail_on: str) -> list[str]:
    if not fail_on.strip():
        return []
    return sorted({x.strip() for x in fail_on.split(",") if x.strip()})



def discover_vibe_files(files_glob: str, root: Path | None = None) -> list[Path]:
    root = (root or Path.cwd()).resolve()
    out = sorted([p.resolve() for p in root.glob(files_glob) if p.is_file() and p.suffix == ".vibe"])
    return out



def _load_source_with_package_defaults(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    pkg_ctx = package_context_for_path(path)
    if pkg_ctx:
        source = apply_package_defaults_to_source(
            source,
            VibeManifest(
                package_name=str(pkg_ctx.get("package_name", "")),
                package_version=str(pkg_ctx.get("package_version", "")),
                description="",
                dependencies=dict(pkg_ctx.get("dependencies", {})),
                bridge_defaults=dict(pkg_ctx.get("bridge_defaults", {})),
                emit_defaults=dict(pkg_ctx.get("emit_defaults", {})),
            ),
        )
    return source



def run_file_check(path: Path, *, backend: str, fallback_backend: str | None, with_proofs: bool, with_tests: bool) -> FileCheckResult:
    source = _load_source_with_package_defaults(path)
    ir = ast_to_ir(parse_source(source))
    emitted_code, emit_backend = emit_code(ir)
    result = verify(ir, emitted_code, backend=backend, fallback_backend=fallback_backend)

    proof_path: str | None = None
    if with_proofs:
        artifact = build_proof_artifact(
            path,
            source,
            ir,
            result,
            emitted_blocked=not result.passed,
            notes=["ci bridge-check proof artifact"],
        )
        pp = default_proof_path(path)
        write_proof_artifact(pp, artifact)
        proof_path = str(pp)

    generated_test_files: list[str] = []
    if with_tests:
        suite = generate_intent_guided_tests(
            ir=ir,
            output_path=path.with_suffix(f".{emit_backend.target}"),
            emitted_code=emitted_code,
            candidate_id="ci.candidate.1",
        )
        for tp, tc in sorted(suite.generated_files.items()):
            tpath = Path(tp)
            tpath.write_text(tc, encoding="utf-8")
            generated_test_files.append(str(tpath))

    return FileCheckResult(
        file_path=str(path),
        passed=bool(result.passed),
        bridge_score=float(result.bridge_score),
        measurement_ratio=float(result.measurement_ratio),
        verdict=str(result.verdict),
        backend=str(result.verification_backend),
        obligation_summary=dict(result.obligation_counts),
        intent_equivalence_score=float(result.intent_equivalence_score),
        drift_score=float(result.drift_score),
        proof_path=proof_path,
        generated_test_files=generated_test_files,
    )



def _fails_fail_on(result: FileCheckResult, fail_rules: list[str]) -> list[str]:
    hits: list[str] = []
    for rule in fail_rules:
        if rule == result.verdict:
            hits.append(rule)
            continue
        if rule.startswith("bridge_score_below_threshold"):
            threshold = 0.85
            if ":" in rule:
                try:
                    threshold = float(rule.split(":", 1)[1])
                except Exception:
                    threshold = 0.85
            if result.bridge_score < threshold:
                hits.append(f"bridge_score_below_threshold:{threshold}")
    return sorted(hits)



def render_markdown_summary(report: dict[str, object]) -> str:
    lines = [
        "# Vibe Bridge Check Summary",
        "",
        f"overall_passed: **{report['overall_passed']}**",
        f"files_checked: **{report['files_checked']}**",
        f"files_failed: **{report['files_failed']}**",
        f"worst_bridge_score: **{report['worst_bridge_score']}**",
        "",
        "| file | passed | bridge_score | measurement_ratio | verdict | fail_on_hits |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in report["results"]:
        lines.append(
            "| {file_path} | {passed} | {bridge_score:.6f} | {measurement_ratio:.6f} | {verdict} | {fail_on_hits} |".format(
                file_path=row["file_path"],
                passed="✅" if row["passed"] else "❌",
                bridge_score=float(row["bridge_score"]),
                measurement_ratio=float(row["measurement_ratio"]),
                verdict=row["verdict"],
                fail_on_hits=",".join(row["fail_on_hits"]) if row["fail_on_hits"] else "-",
            )
        )
    return "\n".join(lines) + "\n"



def run_ci_check(config: CICheckConfig, *, root: Path | None = None) -> tuple[dict[str, object], int]:
    root = (root or Path.cwd()).resolve()
    files = discover_vibe_files(config.files_glob, root=root)
    fail_rules = parse_fail_on(config.fail_on)

    results: list[dict[str, object]] = []
    failed = 0
    fail_on_triggered = 0
    proof_paths: list[str] = []

    for file in files:
        checked = run_file_check(
            file,
            backend=config.backend,
            fallback_backend=config.fallback_backend,
            with_proofs=config.with_proofs,
            with_tests=config.with_tests,
        )
        row = asdict(checked)
        hits = _fails_fail_on(checked, fail_rules)
        row["fail_on_hits"] = hits
        if checked.proof_path:
            proof_paths.append(checked.proof_path)
        if (not checked.passed) or hits:
            failed += 1
        if hits:
            fail_on_triggered += 1
        results.append(row)

    results = sorted(results, key=lambda r: str(r["file_path"]))
    worst_bridge = min([float(r["bridge_score"]) for r in results], default=1.0)
    report = {
        "config": {
            "files": config.files_glob,
            "fail_on": parse_fail_on(config.fail_on),
            "backend": config.backend,
            "fallback_backend": config.fallback_backend,
            "with_proofs": config.with_proofs,
            "with_tests": config.with_tests,
        },
        "files_checked": len(results),
        "files_failed": failed,
        "fail_on_triggered": fail_on_triggered,
        "worst_bridge_score": worst_bridge,
        "overall_passed": failed == 0,
        "proof_paths": sorted(proof_paths),
        "results": results,
    }

    report_path = Path(config.report_json_path)
    if not report_path.is_absolute():
        report_path = root / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    summary_path = report_path.with_suffix(".summary.md")
    summary_path.write_text(render_markdown_summary(report), encoding="utf-8")

    report["report_json_path"] = str(report_path)
    report["summary_markdown_path"] = str(summary_path)
    exit_code = 0 if report["overall_passed"] else 1
    return report, exit_code
