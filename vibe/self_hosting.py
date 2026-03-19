"""Phase 8.1 self-hosting checks for bounded Vibe compiler specs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .emitter import emit_code
from .ir import ast_to_ir
from .parser import parse_source
from .proof import build_proof_artifact, default_proof_path, write_proof_artifact
from .verifier import VerificationResult, verify


BASELINE_SCHEMA_VERSION = "v1"


@dataclass(slots=True)
class SelfCheckConfig:
    spec_path: Path
    baseline_path: Path | None = None
    update_baseline: bool = False
    fail_on_regression: bool = False
    max_bridge_drop: float = 0.0
    verification_backend: str = "heuristic"
    fallback_backend: str | None = None
    use_calibration: bool = True
    write_proof: bool = True


@dataclass(slots=True)
class SelfCheckResult:
    summary: dict[str, object]
    verification: VerificationResult
    exit_code: int


def _load_baseline(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("schema_version", "")) != BASELINE_SCHEMA_VERSION:
        raise ValueError(
            f"invalid self-hosting baseline schema `{payload.get('schema_version')}` (expected `{BASELINE_SCHEMA_VERSION}`)"
        )
    return payload


def _write_baseline(path: Path, summary: dict[str, object]) -> None:
    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "compiler_spec_path": summary["compiler_spec_path"],
        "self_bridge_score": summary["self_bridge_score"],
        "measurement_ratio": summary["measurement_ratio"],
        "passed": summary["passed"],
        "proof_artifact_paths": summary["proof_artifact_paths"],
        "key_obligations": summary["key_obligations"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _key_obligations(result: VerificationResult) -> list[dict[str, object]]:
    ranked = sorted(
        [asdict(o) for o in result.obligations],
        key=lambda row: (
            0 if row.get("status") == "violated" else 1,
            0 if row.get("critical") else 1,
            str(row.get("obligation_id", "")),
        ),
    )
    return ranked[:8]


def run_self_check(config: SelfCheckConfig) -> SelfCheckResult:
    source = config.spec_path.read_text(encoding="utf-8")
    ir = ast_to_ir(parse_source(source))
    emitted_code, _ = emit_code(ir)
    result = verify(
        ir,
        emitted_code,
        backend=config.verification_backend,
        fallback_backend=config.fallback_backend,
        use_calibration=config.use_calibration,
    )
    result.self_hosting_enabled = True
    result.compiler_spec_path = str(config.spec_path)
    result.self_bridge_score = float(round(float(result.bridge_score), 6))
    result.self_regression_status = None
    result.self_baseline_reference = str(config.baseline_path) if config.baseline_path else None

    proof_paths: list[str] = []
    if config.write_proof:
        proof_path = default_proof_path(config.spec_path)
        proof = build_proof_artifact(
            config.spec_path,
            source,
            ir,
            result,
            emitted_blocked=not result.passed,
            notes=[
                "self-hosting check proof artifact",
                "phase 8.1 bounded compiler self-spec (not full compiler bootstrap)",
            ],
        )
        write_proof_artifact(proof_path, proof)
        proof_paths.append(str(proof_path))

    baseline = _load_baseline(config.baseline_path)
    baseline_score = float(baseline["self_bridge_score"]) if baseline is not None else None
    score = float(result.bridge_score)
    score_delta = (score - baseline_score) if baseline_score is not None else None
    regressed = score_delta is not None and score_delta < (-1.0 * float(config.max_bridge_drop))

    if baseline is None:
        regression_status = "no_baseline"
    elif regressed:
        regression_status = "regressed"
    elif score_delta is not None and score_delta > 0:
        regression_status = "improved"
    else:
        regression_status = "stable"

    summary: dict[str, object] = {
        "self_hosting_enabled": True,
        "compiler_spec_path": str(config.spec_path),
        "self_bridge_score": round(score, 6),
        "measurement_ratio": round(float(result.measurement_ratio), 6),
        "passed": bool(result.passed),
        "key_obligations": _key_obligations(result),
        "proof_artifact_paths": proof_paths,
        "baseline_reference": str(config.baseline_path) if config.baseline_path else None,
        "baseline_available": baseline is not None,
        "baseline_bridge_score": round(baseline_score, 6) if baseline_score is not None else None,
        "bridge_score_delta": round(score_delta, 6) if score_delta is not None else None,
        "max_bridge_drop": float(config.max_bridge_drop),
        "regressed": bool(regressed),
        "self_regression_status": regression_status,
        "fail_on_regression": bool(config.fail_on_regression),
    }

    if config.update_baseline and config.baseline_path is not None:
        _write_baseline(config.baseline_path, summary)

    result.self_bridge_score = float(summary["self_bridge_score"])
    result.self_regression_status = regression_status
    result.self_baseline_reference = summary["baseline_reference"]

    exit_code = 0
    if not result.passed:
        exit_code = 1
    if config.fail_on_regression and regressed:
        exit_code = 1

    return SelfCheckResult(summary=summary, verification=result, exit_code=exit_code)
