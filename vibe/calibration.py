"""Empirical epsilon calibration subsystem (Phase calibration)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Any

from .emitter import emit_code
from .equivalence import analyze_intent_equivalence
from .ir import ast_to_ir
from .parser import parse_source

DEFAULT_CALIBRATION_ARTIFACT = Path(".vibe_calibration/bridge_calibration.json")


@dataclass(slots=True)
class CalibrationModel:
    model_version: str
    feature_names: list[str]
    bias_pre: float
    bias_post: float
    weights_pre: dict[str, float]
    weights_post: dict[str, float]
    fit_confidence: float
    corpus_size: int


@dataclass(slots=True)
class CalibrationRecord:
    source: str
    target: str
    expected_epsilon_pre: float
    expected_epsilon_post: float
    notes: str = ""


def calibration_artifact_path(path_override: str | None = None) -> Path:
    return Path(path_override) if path_override else DEFAULT_CALIBRATION_ARTIFACT


def load_calibration_corpus(path: str | Path) -> list[CalibrationRecord]:
    corpus_path = Path(path)
    files: list[Path]
    if corpus_path.is_dir():
        files = sorted(corpus_path.glob("*.json"))
    else:
        files = [corpus_path]

    rows: list[CalibrationRecord] = []
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])
        for e in entries:
            labels = e.get("labels", {})
            rows.append(
                CalibrationRecord(
                    source=str(e["source"]),
                    target=str(e.get("target", "python")),
                    expected_epsilon_pre=float(labels["epsilon_pre"]),
                    expected_epsilon_post=float(labels["epsilon_post"]),
                    notes=str(e.get("notes", "")),
                )
            )
    return rows


def _extract_feature_vector(source_text: str, target: str) -> tuple[dict[str, float], float, float]:
    ir = ast_to_ir(parse_source(source_text))
    code, _ = emit_code(ir, target_override=target)
    eq = analyze_intent_equivalence(ir, code)

    c_bar = sum(bool(x) for x in [ir.goal, ir.inputs, ir.outputs]) / 3
    epsilon_pre = 0.35 + 0.55 * c_bar
    epsilon_post = epsilon_pre * (0.70 * 0.9 + 0.1 * 0.9 + 0.1 * 0.8 + 0.1 * 1.0) + 0.02 * c_bar

    features = {
        "intent_complexity": float(len(ir.inputs) + len(ir.outputs)),
        "preserve_count": float(len(ir.preserve_rules)),
        "constraint_count": float(len(ir.constraints)),
        "bridge_setting_count": float(len(ir.bridge_config)),
        "equivalence_score": float(eq.intent_equivalence_score),
        "drift_score": float(eq.drift_score),
        "target_python": 1.0 if target == "python" else 0.0,
        "target_typescript": 1.0 if target == "typescript" else 0.0,
    }
    return features, float(epsilon_pre), float(epsilon_post)


def _fit_weights(rows: list[tuple[dict[str, float], float]]) -> tuple[float, dict[str, float]]:
    if not rows:
        return 0.0, {}
    feature_names = sorted(rows[0][0].keys())
    avg_residual = sum(r for _, r in rows) / len(rows)
    weights: dict[str, float] = {}
    for name in feature_names:
        num = sum(feat[name] * residual for feat, residual in rows)
        den = sum((feat[name] ** 2) for feat, _ in rows) + 1e-9
        weights[name] = 0.2 * (num / den)
    return avg_residual, weights


def fit_calibration_model(records: list[CalibrationRecord]) -> CalibrationModel:
    if not records:
        return CalibrationModel(
            model_version="v1",
            feature_names=[],
            bias_pre=0.0,
            bias_post=0.0,
            weights_pre={},
            weights_post={},
            fit_confidence=0.0,
            corpus_size=0,
        )

    pre_rows: list[tuple[dict[str, float], float]] = []
    post_rows: list[tuple[dict[str, float], float]] = []
    for record in records:
        source_text = Path(record.source).read_text(encoding="utf-8")
        features, base_pre, base_post = _extract_feature_vector(source_text, record.target)
        pre_rows.append((features, record.expected_epsilon_pre - base_pre))
        post_rows.append((features, record.expected_epsilon_post - base_post))

    bias_pre, weights_pre = _fit_weights(pre_rows)
    bias_post, weights_post = _fit_weights(post_rows)
    feature_names = sorted(pre_rows[0][0].keys())
    mean_abs_resid = (
        sum(abs(r) for _, r in pre_rows) + sum(abs(r) for _, r in post_rows)
    ) / max(1, (len(pre_rows) + len(post_rows)))
    confidence = max(0.0, min(1.0, 1.0 - mean_abs_resid))

    return CalibrationModel(
        model_version="v1",
        feature_names=feature_names,
        bias_pre=bias_pre,
        bias_post=bias_post,
        weights_pre=weights_pre,
        weights_post=weights_post,
        fit_confidence=round(confidence, 6),
        corpus_size=len(records),
    )


def save_calibration_model(model: CalibrationModel, artifact_path: str | Path | None = None) -> Path:
    out = calibration_artifact_path(str(artifact_path) if artifact_path else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(model), indent=2, sort_keys=True), encoding="utf-8")
    return out


def load_calibration_model(artifact_path: str | Path | None = None) -> CalibrationModel | None:
    path = calibration_artifact_path(str(artifact_path) if artifact_path else None)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        return CalibrationModel(
            model_version=str(payload.get("model_version", "v1")),
            feature_names=list(payload.get("feature_names", [])),
            bias_pre=float(payload.get("bias_pre", 0.0)),
            bias_post=float(payload.get("bias_post", 0.0)),
            weights_pre={str(k): float(v) for k, v in dict(payload.get("weights_pre", {})).items()},
            weights_post={str(k): float(v) for k, v in dict(payload.get("weights_post", {})).items()},
            fit_confidence=float(payload.get("fit_confidence", 0.0)),
            corpus_size=int(payload.get("corpus_size", 0)),
        )
    except Exception:
        return None


def extract_calibration_features(
    intent_complexity: int,
    preserve_count: int,
    constraint_count: int,
    bridge_setting_count: int,
    equivalence_score: float,
    drift_score: float,
    target: str,
) -> dict[str, float]:
    return {
        "intent_complexity": float(intent_complexity),
        "preserve_count": float(preserve_count),
        "constraint_count": float(constraint_count),
        "bridge_setting_count": float(bridge_setting_count),
        "equivalence_score": float(equivalence_score),
        "drift_score": float(drift_score),
        "target_python": 1.0 if target == "python" else 0.0,
        "target_typescript": 1.0 if target == "typescript" else 0.0,
    }


def apply_calibration(
    model: CalibrationModel,
    base_pre: float,
    base_post: float,
    features: dict[str, float],
    *,
    conservative_no_rescue: bool,
) -> tuple[float, float, dict[str, Any]]:
    delta_pre = model.bias_pre + sum(model.weights_pre.get(k, 0.0) * features.get(k, 0.0) for k in model.feature_names)
    delta_post = model.bias_post + sum(model.weights_post.get(k, 0.0) * features.get(k, 0.0) for k in model.feature_names)
    calibrated_pre = max(0.0, min(1.0, base_pre + delta_pre))
    calibrated_post = max(0.0, min(1.0, base_post + delta_post))

    if conservative_no_rescue:
        calibrated_pre = min(calibrated_pre, base_pre)
        calibrated_post = min(calibrated_post, base_post)

    return calibrated_pre, calibrated_post, {
        "delta_pre": round(delta_pre, 6),
        "delta_post": round(delta_post, 6),
        "fit_confidence": model.fit_confidence,
    }
