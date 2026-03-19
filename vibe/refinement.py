"""Deterministic bridge-gated refinement protocol (Phase 3.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .synthesis import CandidateImplementation
from .testgen import GeneratedTestSuite
from .verifier import VerificationResult


@dataclass(slots=True)
class RefinementCounterexample:
    failed_obligation_ids: list[str] = field(default_factory=list)
    unknown_critical_obligation_ids: list[str] = field(default_factory=list)
    drift_missing_items: int = 0
    drift_extra_items: int = 0
    unsupported_mappings: list[str] = field(default_factory=list)
    uncovered_items: list[str] = field(default_factory=list)
    partial_coverage_items: list[str] = field(default_factory=list)
    backend_error: str | None = None
    bridge_score: float = 0.0
    measurement_ratio: float = 0.0
    shortfall_reasons: list[str] = field(default_factory=list)
    candidate_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RefinementIterationSummary:
    iteration: int
    candidate_ids: list[str]
    passing_candidates: list[str]
    selected_candidate_id: str
    selected_strategy: str
    selected_passed: bool
    failure_reasons: list[str] = field(default_factory=list)
    guidance: dict[str, object] = field(default_factory=dict)
    strategy_adjustments: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RefinementOutcome:
    success: bool
    iterations_run: int
    max_iterations: int
    winner_iteration: int | None
    winner_candidate_id: str | None
    hit_max_iterations: bool
    history: list[RefinementIterationSummary] = field(default_factory=list)
    failure_summary: list[str] = field(default_factory=list)


def extract_counterexample(
    result: VerificationResult,
    *,
    test_suite: GeneratedTestSuite | None = None,
    candidate_notes: list[str] | None = None,
) -> RefinementCounterexample:
    failed = [o.obligation_id for o in result.obligations if o.status == "violated"]
    unknown_critical = [o.obligation_id for o in result.obligations if o.status == "unknown" and o.critical]
    unsupported = [c.source_item for c in result.correspondence_entries if c.status in {"missing", "extra", "unknown"}]
    reasons: list[str] = []
    if result.bridge_score < 1.0:
        reasons.append("bridge_score_shortfall")
    if result.measurement_ratio < 1.0:
        reasons.append("measurement_ratio_shortfall")
    if result.backend_error:
        reasons.append("backend_error")
    if failed:
        reasons.append("violated_obligations")
    if unknown_critical:
        reasons.append("unknown_critical_obligations")
    if result.intent_items_missing:
        reasons.append("missing_intent_mappings")
    if result.intent_items_extra:
        reasons.append("extra_intent_mappings")
    if test_suite and test_suite.uncovered_items:
        reasons.append("uncovered_test_surface_items")
    if test_suite and test_suite.partial_coverage_items:
        reasons.append("partial_test_surface_items")

    return RefinementCounterexample(
        failed_obligation_ids=failed,
        unknown_critical_obligation_ids=unknown_critical,
        drift_missing_items=result.intent_items_missing,
        drift_extra_items=result.intent_items_extra,
        unsupported_mappings=unsupported,
        uncovered_items=list(test_suite.uncovered_items) if test_suite else list(result.uncovered_items),
        partial_coverage_items=list(test_suite.partial_coverage_items) if test_suite else list(result.partial_coverage_items),
        backend_error=result.backend_error,
        bridge_score=float(result.bridge_score),
        measurement_ratio=float(result.measurement_ratio),
        shortfall_reasons=reasons,
        candidate_notes=list(candidate_notes or []),
    )


def strategy_adjustments(counterexample: RefinementCounterexample) -> list[str]:
    adjustments: list[str] = []
    if counterexample.drift_missing_items > 0:
        adjustments.append("prioritize_readability_and_config")
    if counterexample.drift_extra_items > 0:
        adjustments.append("reduce_helper_noise")
    if any("preserve:" in x for x in counterexample.uncovered_items):
        adjustments.append("increase_config_heavy_bias")
    if counterexample.failed_obligation_ids:
        adjustments.append("target_failed_obligations")
    if counterexample.backend_error:
        adjustments.append("avoid_backend_sensitive_patterns")
    if not adjustments:
        adjustments.append("stability_pass")
    return adjustments


def refine_candidates(
    candidates: list[CandidateImplementation],
    *,
    iteration: int,
    counterexample: RefinementCounterexample,
) -> list[CandidateImplementation]:
    adjustments = strategy_adjustments(counterexample)
    scored: list[tuple[int, CandidateImplementation]] = []
    for c in candidates:
        score = 0
        if "readability" in c.strategy:
            score += 2 if "prioritize_readability_and_config" in adjustments else 0
        if "config" in c.strategy:
            score += 2 if "increase_config_heavy_bias" in adjustments else 0
        if "minimal" in c.strategy:
            score += 2 if "reduce_helper_noise" in adjustments else 0
        score += 1 if c.strategy == "standard" else 0
        scored.append((score, c))
    ordered = [c for _, c in sorted(scored, key=lambda item: (-item[0], item[1].candidate_id))]

    notes = ",".join(adjustments)
    refined: list[CandidateImplementation] = []
    for idx, c in enumerate(ordered):
        marker = f"refinement_round_{iteration}_candidate_{idx + 1}"
        suffix = f"\n# refinement: {marker}; adjustments={notes}\n"
        if c.target == "typescript":
            suffix = f"\n// refinement: {marker}; adjustments={notes}\n"
        refined.append(
            CandidateImplementation(
                candidate_id=f"iter{iteration}.{idx + 1}",
                strategy=f"{c.strategy}+refined",
                target=c.target,
                code=c.code + suffix,
            )
        )
    return refined


def to_history_row(summary: RefinementIterationSummary) -> dict[str, object]:
    return asdict(summary)
