"""Semantic bridge verifier for generated Vibe implementations."""

from __future__ import annotations

from dataclasses import dataclass

from .ir import DEFAULT_EPSILON_FLOOR, DEFAULT_MEASUREMENT_SAFE_RATIO, IR


@dataclass(slots=True)
class VerificationResult:
    c_bar: float
    epsilon_pre: float
    epsilon_post: float
    measurement_ratio: float
    q_persistence: float
    q_spatial_consistency: float
    q_cohesion: float
    q_alignment: float
    q_intent_constant: float
    petra_alignment: float
    multimodal_resonance: float
    bridge_score: float
    verdict: str
    passed: bool


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def verify(ir: IR, generated_python: str) -> VerificationResult:
    """Compute heuristic bridge preservation metrics for v0.1."""

    epsilon_floor = float(ir.bridge_config.get("epsilon_floor", DEFAULT_EPSILON_FLOOR))
    measurement_safe_ratio = float(
        ir.bridge_config.get("measurement_safe_ratio", DEFAULT_MEASUREMENT_SAFE_RATIO)
    )

    coverage_numerator = 0
    coverage_denominator = 3
    if ir.goal:
        coverage_numerator += 1
    if ir.inputs:
        coverage_numerator += 1
    if ir.outputs:
        coverage_numerator += 1

    c_bar = coverage_numerator / coverage_denominator
    epsilon_pre = 0.35 + 0.55 * c_bar

    constraint_hits = 0
    lower_code = generated_python.lower()
    for constraint in ir.constraints:
        c = constraint.lower()
        if "deterministic" in c and ("sort(" in lower_code or "sorted(" in lower_code):
            constraint_hits += 1
        elif "no hardcoded secrets" in c and "secret" not in lower_code:
            constraint_hits += 1
        elif "fallback" in c and "fallback" in lower_code:
            constraint_hits += 1
        elif c not in {""} and c in lower_code:
            constraint_hits += 1

    constraint_score = 1.0 if not ir.constraints else constraint_hits / len(ir.constraints)
    deterministic_score = 1.0 if ("sort(" in lower_code or "sorted(" in lower_code) else 0.8
    readability_score = 1.0 if "\n    " in generated_python and '"""' in generated_python else 0.85
    preserve_score = 1.0 if ir.preserve_rules else 0.9

    q_persistence = _clamp(0.4 * c_bar + 0.6 * preserve_score)
    q_spatial_consistency = _clamp(0.5 * deterministic_score + 0.5 * constraint_score)
    q_cohesion = _clamp(0.5 * readability_score + 0.5 * c_bar)
    q_alignment = _clamp((q_persistence + q_spatial_consistency + q_cohesion) / 3)
    q_intent_constant = _clamp(0.7 * c_bar + 0.3 * constraint_score)

    petra_alignment = _clamp(0.6 * q_alignment + 0.4 * q_intent_constant)
    multimodal_resonance = _clamp(0.65 * q_cohesion + 0.35 * readability_score)

    epsilon_post = _clamp(
        epsilon_pre
        * (0.74 * q_alignment + 0.1 * constraint_score + 0.1 * deterministic_score + 0.06 * readability_score)
        + 0.03 * c_bar
    )
    measurement_ratio = epsilon_post / max(epsilon_pre, epsilon_floor)

    bridge_score = _clamp(
        0.3 * q_alignment
        + 0.18 * q_persistence
        + 0.14 * q_spatial_consistency
        + 0.12 * q_cohesion
        + 0.1 * q_intent_constant
        + 0.08 * petra_alignment
        + 0.06 * multimodal_resonance
        + 0.02 * c_bar
    )

    if bridge_score < 0.45:
        verdict = "FIELD_COLLAPSE_ERROR"
    elif bridge_score < 0.6:
        verdict = "ENTROPY_NOISE"
    elif bridge_score < 0.75:
        verdict = "EMPIRICAL_BRIDGE_ACTIVE"
    elif bridge_score < 0.88:
        verdict = "PETRA_BRIDGE_LOCK"
    else:
        verdict = "MULTIMODAL_BRIDGE_STABLE"

    passed = epsilon_post > epsilon_floor and measurement_ratio >= measurement_safe_ratio

    return VerificationResult(
        c_bar=c_bar,
        epsilon_pre=epsilon_pre,
        epsilon_post=epsilon_post,
        measurement_ratio=measurement_ratio,
        q_persistence=q_persistence,
        q_spatial_consistency=q_spatial_consistency,
        q_cohesion=q_cohesion,
        q_alignment=q_alignment,
        q_intent_constant=q_intent_constant,
        petra_alignment=petra_alignment,
        multimodal_resonance=multimodal_resonance,
        bridge_score=bridge_score,
        verdict=verdict,
        passed=passed,
    )
