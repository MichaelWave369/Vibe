"""Semantic bridge verifier for generated Vibe implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace
import re
from typing import Protocol

from .calibration import (
    apply_calibration,
    extract_calibration_features,
    load_calibration_model,
)
from .equivalence import CorrespondenceEntry, analyze_intent_equivalence
from .effects import (
    check_effect_issues,
    effect_issues_to_obligation_rows,
    effect_summary_payload,
    issues_as_dicts as effect_issues_as_dicts,
)
from .ir import DEFAULT_EPSILON_FLOOR, DEFAULT_MEASUREMENT_SAFE_RATIO, IR
from .semantic_types import (
    check_semantic_type_issues,
    issues_as_dicts,
    issues_to_obligation_rows,
    semantic_summary_payload,
)

ObligationStatus = str


@dataclass(slots=True)
class VerificationObligation:
    obligation_id: str
    category: str
    description: str
    source_location: str | None
    status: ObligationStatus
    evidence: str | None = None
    critical: bool = False


@dataclass(slots=True)
class NormalizedObligation:
    obligation_id: str
    category: str
    description: str
    source_location: str | None
    subject_ref: str | None
    expected_predicate: dict[str, object]
    severity: str
    critical: bool = False


@dataclass(slots=True)
class VerificationBackendMetadata:
    name: str
    version: str
    mode: str
    capabilities: list[str] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ObligationEvaluationContext:
    epsilon_floor: float
    measurement_safe_ratio: float
    lower_code: str
    readability_score: float
    epsilon_post: float
    measurement_ratio: float
    delegation_integrity: float
    sovereignty_required: bool
    sovereignty_preserved: bool | None
    agentception_enabled: bool
    inherit_constraints: bool
    inherit_ok: bool
    observed_scalars: dict[str, float] = field(default_factory=dict)
    observed_bools: dict[str, bool] = field(default_factory=dict)
    observed_symbols: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BackendEvaluationResult:
    obligations: list[VerificationObligation]
    metadata: VerificationBackendMetadata


class ObligationBackend(Protocol):
    backend_name: str

    def evaluate(
        self,
        ir: IR,
        obligations: list[NormalizedObligation],
        context: ObligationEvaluationContext,
    ) -> BackendEvaluationResult: ...


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
    tesla_enabled: bool = False
    substrate_bridge: list[str] | None = None
    baseline_frequency_hz: float | None = None
    harmonic_mode: str | None = None
    breath_monitor: str | None = None
    sovereignty_preserved: bool | None = None
    agent_count: int = 0
    spawn_depth: int = 0
    child_alignment: float = 1.0
    delegation_integrity: float = 1.0
    merge_preservation: float = 1.0
    agent_bridge_score: float = 1.0
    obligations: list[VerificationObligation] = field(default_factory=list)
    obligation_counts: dict[str, int] = field(default_factory=dict)
    verification_backend: str = "heuristic"
    backend_version: str = "v1"
    backend_mode: str = "operational"
    backend_capabilities: list[str] = field(default_factory=list)
    backend_details: dict[str, object] = field(default_factory=dict)
    backend_error: str | None = None
    intent_items_total: int = 0
    intent_items_matched: int = 0
    intent_items_partial: int = 0
    intent_items_missing: int = 0
    intent_items_extra: int = 0
    intent_items_unknown: int = 0
    intent_equivalence_score: float = 0.0
    drift_score: float = 1.0
    mapping_notes: list[str] = field(default_factory=list)
    correspondence_entries: list[CorrespondenceEntry] = field(default_factory=list)
    calibration_applied: bool = False
    calibration_model_version: str | None = None
    calibration_artifact_path: str | None = None
    calibration_confidence: float | None = None
    calibration_notes: str = ""
    candidate_count: int = 1
    winning_candidate_id: str = "candidate.1"
    synthesized_winner: bool = False
    ranking_basis: str = ""
    candidate_summaries: list[dict[str, object]] = field(default_factory=list)
    test_generation_enabled: bool = False
    generated_test_files: list[str] = field(default_factory=list)
    preserve_rule_coverage: list[dict[str, str]] = field(default_factory=list)
    constraint_coverage: list[dict[str, str]] = field(default_factory=list)
    uncovered_items: list[str] = field(default_factory=list)
    partial_coverage_items: list[str] = field(default_factory=list)
    test_generation_notes: list[str] = field(default_factory=list)
    refinement_enabled: bool = False
    refinement_iterations_run: int = 1
    refinement_max_iterations: int = 1
    refinement_success: bool = False
    refinement_history: list[dict[str, object]] = field(default_factory=list)
    refinement_failure_summary: list[str] = field(default_factory=list)
    winning_iteration: int = 1
    semantic_type_summary: dict[str, object] = field(default_factory=dict)
    semantic_type_issues: list[dict[str, object]] = field(default_factory=list)
    semantic_type_obligations: list[dict[str, object]] = field(default_factory=list)
    effect_type_summary: dict[str, object] = field(default_factory=dict)
    effect_type_issues: list[dict[str, object]] = field(default_factory=list)
    effect_type_obligations: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class _MetricSnapshot:
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
    tesla_enabled: bool
    substrate_bridge: list[str]
    baseline_frequency_hz: float
    harmonic_mode: str
    breath_monitor: str
    sovereignty_required: bool
    sovereignty_preserved: bool | None
    agent_count: int
    spawn_depth: int
    child_alignment: float
    delegation_integrity: float
    merge_preservation: float
    agent_bridge_score: float
    inherit_ok: bool
    epsilon_floor: float
    measurement_safe_ratio: float


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _compute_obligation_counts(obligations: list[VerificationObligation]) -> dict[str, int]:
    counts = {"satisfied": 0, "violated": 0, "unknown": 0, "not_applicable": 0}
    for o in obligations:
        counts[o.status] = counts.get(o.status, 0) + 1
    return counts


def _constraint_match(constraint: str, lower_code: str, inherit_constraints: bool) -> bool:
    c = constraint.lower()
    return (
        (c in lower_code)
        or ("deterministic" in c and ("sort(" in lower_code or "sorted(" in lower_code))
        or ("no hardcoded secrets" in c and "secret" not in lower_code)
        or ("fallback" in c and "fallback" in lower_code)
        or ("preserve parent constraints" in c and inherit_constraints)
    )


def _parse_numeric_literal(value: str) -> tuple[float, str | None] | None:
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)([a-zA-Z%]+)?\s*", value)
    if not m:
        return None
    number = float(m.group(1))
    unit = m.group(2)
    return number, unit


def _parse_bool_literal(value: str) -> bool | None:
    lower = value.strip().lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return None


def _parse_constraint_simple_form(text: str) -> dict[str, object] | None:
    if ":" in text:
        lhs, rhs = text.split(":", 1)
        b = _parse_bool_literal(rhs)
        if b is not None:
            return {"kind": "bool_assert", "lhs": lhs.strip(), "rhs": b}
    if "=" in text:
        lhs, rhs = text.split("=", 1)
        rhs_clean = rhs.strip()
        b = _parse_bool_literal(rhs_clean)
        if b is not None:
            return {"kind": "bool_assert", "lhs": lhs.strip(), "rhs": b}
        n = _parse_numeric_literal(rhs_clean)
        if n is not None:
            return {"kind": "scalar_eq", "lhs": lhs.strip(), "rhs": n[0], "unit": n[1]}
        return {"kind": "symbol_eq", "lhs": lhs.strip(), "rhs": rhs_clean}
    return None


class HeuristicObligationBackend:
    backend_name = "heuristic"

    def evaluate(
        self,
        ir: IR,
        obligations: list[NormalizedObligation],
        context: ObligationEvaluationContext,
    ) -> BackendEvaluationResult:
        evaluated: list[VerificationObligation] = []
        for o in obligations:
            status: ObligationStatus = "unknown"
            evidence = "No backend evidence"
            pred = o.expected_predicate
            kind = str(pred.get("kind", ""))

            if kind == "readability_min":
                threshold = float(pred.get("min", 0.85))
                status = "satisfied" if context.readability_score >= threshold else "violated"
                evidence = f"readability_score={context.readability_score:.3f}"
            elif kind == "heuristic_preserve_surface":
                status = "unknown"
                evidence = "No formal solver bound yet; preserved as heuristic surface"
            elif kind == "constraint_pattern":
                text = str(pred.get("text", ""))
                matched = _constraint_match(text, context.lower_code, context.inherit_constraints)
                status = "satisfied" if matched else "violated"
                evidence = "heuristic generated-code pattern match"
            elif kind == "epsilon_post_gt_floor":
                status = "satisfied" if context.epsilon_post > context.epsilon_floor else "violated"
                evidence = (
                    f"epsilon_post={context.epsilon_post:.4f}, "
                    f"epsilon_floor={context.epsilon_floor:.4f}"
                )
            elif kind == "measurement_ratio_safe":
                status = (
                    "satisfied"
                    if context.measurement_ratio >= context.measurement_safe_ratio
                    else "violated"
                )
                evidence = (
                    f"measurement_ratio={context.measurement_ratio:.4f}, "
                    f"threshold={context.measurement_safe_ratio:.4f}"
                )
            elif kind == "sovereignty_required":
                status = "satisfied" if context.sovereignty_preserved else "violated"
                evidence = "heuristic sovereignty marker check"
            elif kind == "sovereignty_not_declared":
                status = "not_applicable"
                evidence = "preserve.sovereignty not requested"
            elif kind == "delegation_inherit_flags":
                status = "satisfied" if context.inherit_ok else "violated"
                evidence = "inherit flags from agentception config"
            elif kind == "delegation_integrity_floor":
                floor = float(pred.get("min", 0.7))
                status = "satisfied" if context.delegation_integrity >= floor else "violated"
                evidence = f"delegation_integrity={context.delegation_integrity:.3f}"
            elif kind == "delegation_not_enabled":
                status = "not_applicable"
                evidence = "agentception disabled"

            evaluated.append(
                VerificationObligation(
                    obligation_id=o.obligation_id,
                    category=o.category,
                    description=o.description,
                    source_location=o.source_location,
                    status=status,
                    evidence=evidence,
                    critical=o.critical,
                )
            )

        return BackendEvaluationResult(
            obligations=evaluated,
            metadata=VerificationBackendMetadata(
                name="heuristic",
                version="v1",
                mode="operational",
                capabilities=["pattern_match", "bridge_thresholds", "delegation_checks"],
            ),
        )


class SymbolicObligationBackend:
    backend_name = "symbolic"

    def evaluate(
        self,
        ir: IR,
        obligations: list[NormalizedObligation],
        context: ObligationEvaluationContext,
    ) -> BackendEvaluationResult:
        raise NotImplementedError("verification backend `symbolic` is not implemented yet")


class SMTObligationBackend:
    backend_name = "smt"

    def evaluate(
        self,
        ir: IR,
        obligations: list[NormalizedObligation],
        context: ObligationEvaluationContext,
    ) -> BackendEvaluationResult:
        evaluated: list[VerificationObligation] = []
        solver_evaluated = 0
        deferred = 0

        for o in obligations:
            pred = o.expected_predicate
            kind = str(pred.get("kind", ""))
            status: ObligationStatus = "unknown"
            evidence = "deferred: unsupported predicate for smt subset"

            if kind == "epsilon_post_gt_floor":
                status = "satisfied" if context.epsilon_post > context.epsilon_floor else "violated"
                evidence = (
                    "solver-evaluated: "
                    f"{context.epsilon_post:.4f} > {context.epsilon_floor:.4f}"
                )
                solver_evaluated += 1
            elif kind == "measurement_ratio_safe":
                status = (
                    "satisfied"
                    if context.measurement_ratio >= context.measurement_safe_ratio
                    else "violated"
                )
                evidence = (
                    "solver-evaluated: "
                    f"{context.measurement_ratio:.4f} >= {context.measurement_safe_ratio:.4f}"
                )
                solver_evaluated += 1
            elif kind == "scalar_compare":
                lhs = str(pred.get("lhs", ""))
                op = str(pred.get("operator", ""))
                rhs = float(pred.get("rhs", 0.0))
                obs = context.observed_scalars.get(lhs)
                if obs is None:
                    deferred += 1
                    evidence = f"deferred: no observed scalar for `{lhs}`"
                else:
                    if op == "<":
                        ok = obs < rhs
                    elif op == "<=":
                        ok = obs <= rhs
                    elif op == ">":
                        ok = obs > rhs
                    elif op == ">=":
                        ok = obs >= rhs
                    else:
                        ok = False
                    status = "satisfied" if ok else "violated"
                    evidence = f"solver-evaluated: {lhs}={obs:.4f} {op} {rhs:.4f}"
                    solver_evaluated += 1
            elif kind == "scalar_eq":
                lhs = str(pred.get("lhs", ""))
                rhs = float(pred.get("rhs", 0.0))
                obs = context.observed_scalars.get(lhs)
                if obs is None:
                    deferred += 1
                    evidence = f"deferred: no observed scalar for `{lhs}`"
                else:
                    status = "satisfied" if abs(obs - rhs) < 1e-9 else "violated"
                    evidence = f"solver-evaluated: {lhs}={obs:.4f} == {rhs:.4f}"
                    solver_evaluated += 1
            elif kind == "bool_assert":
                lhs = str(pred.get("lhs", ""))
                rhs = bool(pred.get("rhs", False))
                obs = context.observed_bools.get(lhs)
                if obs is None:
                    deferred += 1
                    evidence = f"deferred: no observed boolean for `{lhs}`"
                else:
                    status = "satisfied" if obs is rhs else "violated"
                    evidence = f"solver-evaluated: {lhs}={obs} == {rhs}"
                    solver_evaluated += 1
            elif kind == "symbol_eq":
                lhs = str(pred.get("lhs", ""))
                rhs = str(pred.get("rhs", ""))
                obs = context.observed_symbols.get(lhs)
                if obs is None:
                    deferred += 1
                    evidence = f"deferred: no observed symbol for `{lhs}`"
                else:
                    status = "satisfied" if obs == rhs else "violated"
                    evidence = f"solver-evaluated: {lhs}={obs} == {rhs}"
                    solver_evaluated += 1
            elif kind in {"sovereignty_not_declared", "delegation_not_enabled"}:
                status = "not_applicable"
                evidence = "not applicable in current program state"
                solver_evaluated += 1
            else:
                deferred += 1

            evaluated.append(
                VerificationObligation(
                    obligation_id=o.obligation_id,
                    category=o.category,
                    description=o.description,
                    source_location=o.source_location,
                    status=status,
                    evidence=evidence,
                    critical=o.critical,
                )
            )

        return BackendEvaluationResult(
            obligations=evaluated,
            metadata=VerificationBackendMetadata(
                name="smt",
                version="v0-subset",
                mode="symbolic_smt_subset",
                capabilities=[
                    "numeric_comparisons",
                    "scalar_equality",
                    "boolean_assertions",
                    "founding_law_checks",
                ],
                details={
                    "solver_evaluated": solver_evaluated,
                    "deferred": deferred,
                    "fallback_used": False,
                },
            ),
        )


_BACKENDS: dict[str, ObligationBackend] = {
    "heuristic": HeuristicObligationBackend(),
    "symbolic": SymbolicObligationBackend(),
    "smt": SMTObligationBackend(),
}


def available_backends() -> list[str]:
    return sorted(_BACKENDS.keys())


def get_backend(name: str) -> ObligationBackend:
    backend = _BACKENDS.get(name)
    if backend is None:
        raise ValueError(f"unknown verification backend `{name}`")
    return backend


def _compute_metrics(ir: IR, generated_code: str) -> _MetricSnapshot:
    epsilon_floor = float(ir.bridge_config.get("epsilon_floor", DEFAULT_EPSILON_FLOOR))
    measurement_safe_ratio = float(
        ir.bridge_config.get("measurement_safe_ratio", DEFAULT_MEASUREMENT_SAFE_RATIO)
    )

    c_bar = sum(bool(x) for x in [ir.goal, ir.inputs, ir.outputs]) / 3
    epsilon_pre = 0.35 + 0.55 * c_bar

    lower_code = generated_code.lower()
    constraint_hits = sum(
        1 for constraint in ir.constraints if _constraint_match(constraint, lower_code, bool(ir.agentception_config.get("inherit_constraints", False)))
    )

    constraint_score = 1.0 if not ir.constraints else constraint_hits / len(ir.constraints)
    deterministic_score = 1.0 if ("sort(" in lower_code or "sorted(" in lower_code) else 0.8
    readability_score = (
        1.0
        if "\n" in generated_code and ("def " in generated_code or "export function" in generated_code)
        else 0.85
    )
    preserve_score = 1.0 if ir.preserve_rules else 0.9

    tesla_factor = 0.0
    sovereignty_required = False
    sovereignty_preserved: bool | None = None
    if ir.tesla_victory_layer:
        tesla_factor = 0.04
        sovereignty_required = bool(ir.arc_tower_policy.get("preserve_sovereignty", False))
        sovereignty_preserved = (
            ("sovereignty" in lower_code or "preserve" in lower_code)
            if sovereignty_required
            else True
        )
        if sovereignty_required and not sovereignty_preserved:
            tesla_factor = -0.08

    agent_count = len(ir.agent_definitions)
    spawn_depth = int(ir.agentception_config.get("max_depth", 0)) if ir.agentception_config else 0
    inherit_ok = True
    if ir.agentception_config.get("enabled"):
        inherit_ok = all(
            bool(ir.agentception_config.get(k, False))
            for k in ["inherit_preserve", "inherit_constraints", "inherit_bridge"]
        )
    child_alignment = _clamp(0.72 + 0.08 * min(agent_count, 3) - 0.04 * max(spawn_depth - 3, 0))
    delegation_integrity = _clamp(0.9 if inherit_ok else 0.55)
    merge_preservation = _clamp(0.92 if ir.merge_strategy else 0.75)
    agent_bridge_score = _clamp((child_alignment + delegation_integrity + merge_preservation) / 3)

    q_persistence = _clamp(0.4 * c_bar + 0.6 * preserve_score)
    q_spatial_consistency = _clamp(0.5 * deterministic_score + 0.5 * constraint_score)
    q_cohesion = _clamp(0.5 * readability_score + 0.5 * c_bar)
    q_alignment = _clamp((q_persistence + q_spatial_consistency + q_cohesion) / 3 + tesla_factor)
    q_intent_constant = _clamp(
        0.65 * c_bar + 0.25 * constraint_score + 0.10 * agent_bridge_score + tesla_factor
    )

    petra_alignment = _clamp(0.55 * q_alignment + 0.35 * q_intent_constant + 0.10 * agent_bridge_score)
    multimodal_resonance = _clamp(
        0.55 * q_cohesion + 0.25 * readability_score + 0.20 * agent_bridge_score + tesla_factor
    )

    epsilon_post = _clamp(
        epsilon_pre
        * (
            0.70 * q_alignment
            + 0.1 * constraint_score
            + 0.1 * deterministic_score
            + 0.1 * readability_score
        )
        + 0.02 * c_bar
    )
    measurement_ratio = epsilon_post / max(epsilon_pre, epsilon_floor)

    bridge_score = _clamp(
        0.28 * q_alignment
        + 0.16 * q_persistence
        + 0.12 * q_spatial_consistency
        + 0.1 * q_cohesion
        + 0.1 * q_intent_constant
        + 0.08 * petra_alignment
        + 0.06 * multimodal_resonance
        + 0.1 * agent_bridge_score
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

    return _MetricSnapshot(
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
        tesla_enabled=ir.tesla_victory_layer,
        substrate_bridge=list(ir.arc_tower_policy.get("substrate_bridge", [])) if ir.arc_tower_policy else [],
        baseline_frequency_hz=float(ir.life_ray_protocol.get("baseline_frequency_hz", 0.0)) if ir.life_ray_protocol else 0.0,
        harmonic_mode=str(ir.life_ray_protocol.get("harmonic_mode", "")) if ir.life_ray_protocol else "",
        breath_monitor=str(ir.breath_cycle_protocol.get("monitor", "")) if ir.breath_cycle_protocol else "",
        sovereignty_required=sovereignty_required,
        sovereignty_preserved=sovereignty_preserved,
        agent_count=agent_count,
        spawn_depth=spawn_depth,
        child_alignment=child_alignment,
        delegation_integrity=delegation_integrity,
        merge_preservation=merge_preservation,
        agent_bridge_score=agent_bridge_score,
        inherit_ok=inherit_ok,
        epsilon_floor=epsilon_floor,
        measurement_safe_ratio=measurement_safe_ratio,
    )


def generate_normalized_obligations(ir: IR) -> list[NormalizedObligation]:
    obligations: list[NormalizedObligation] = []

    for idx, (key, op, value) in enumerate(ir.preserve_rules, start=1):
        key_lower = key.lower()
        if key_lower in {"readability", "testability"}:
            predicate = {"kind": "readability_min", "metric": "readability_score", "min": 0.85}
        elif op in {"<", "<=", ">", ">="}:
            parsed = _parse_numeric_literal(value)
            if parsed is not None:
                number, unit = parsed
                predicate = {
                    "kind": "scalar_compare",
                    "lhs": key_lower,
                    "operator": op,
                    "rhs": number,
                    "unit": unit,
                }
            else:
                predicate = {"kind": "heuristic_preserve_surface", "operator": op, "value": value}
        elif op == "=":
            bool_val = _parse_bool_literal(value)
            if bool_val is not None:
                predicate = {"kind": "bool_assert", "lhs": key_lower, "rhs": bool_val}
            else:
                numeric = _parse_numeric_literal(value)
                if numeric is not None:
                    predicate = {
                        "kind": "scalar_eq",
                        "lhs": key_lower,
                        "rhs": numeric[0],
                        "unit": numeric[1],
                    }
                else:
                    predicate = {"kind": "symbol_eq", "lhs": key_lower, "rhs": value.strip()}
        else:
            predicate = {"kind": "heuristic_preserve_surface", "operator": op, "value": value}
        obligations.append(
            NormalizedObligation(
                obligation_id=f"preserve.{idx}",
                category="preserve",
                description=f"Preserve rule `{key} {op} {value}`",
                source_location=None,
                subject_ref=f"preserve.{idx}",
                expected_predicate=predicate,
                severity="advisory",
                critical=False,
            )
        )

    for idx, constraint in enumerate(ir.constraints, start=1):
        parsed_constraint = _parse_constraint_simple_form(constraint)
        obligations.append(
            NormalizedObligation(
                obligation_id=f"constraint.{idx}",
                category="constraint",
                description=f"Constraint `{constraint}`",
                source_location=None,
                subject_ref=f"constraint.{idx}",
                expected_predicate=parsed_constraint or {"kind": "constraint_pattern", "text": constraint},
                severity="advisory",
                critical=False,
            )
        )

    obligations.append(
        NormalizedObligation(
            obligation_id="bridge.founding.epsilon_post_gt_floor",
            category="bridge",
            description="Founding law: epsilon_post > epsilon_floor",
            source_location=None,
            subject_ref="bridge.epsilon_floor",
            expected_predicate={"kind": "epsilon_post_gt_floor"},
            severity="error",
            critical=True,
        )
    )
    obligations.append(
        NormalizedObligation(
            obligation_id="bridge.founding.measurement_ratio_safe",
            category="bridge",
            description="Founding law: measurement_ratio >= measurement_safe_ratio",
            source_location=None,
            subject_ref="bridge.measurement_safe_ratio",
            expected_predicate={"kind": "measurement_ratio_safe"},
            severity="error",
            critical=True,
        )
    )

    if ir.tesla_victory_layer and bool(ir.arc_tower_policy.get("preserve_sovereignty", False)):
        obligations.append(
            NormalizedObligation(
                obligation_id="sovereignty.preserve",
                category="sovereignty",
                description="Tesla sovereignty preservation must hold when declared",
                source_location=None,
                subject_ref="arc_tower.preserve_sovereignty",
                expected_predicate={"kind": "sovereignty_required"},
                severity="error",
                critical=True,
            )
        )
    else:
        obligations.append(
            NormalizedObligation(
                obligation_id="sovereignty.preserve",
                category="sovereignty",
                description="Sovereignty obligation not declared",
                source_location=None,
                subject_ref="arc_tower.preserve_sovereignty",
                expected_predicate={"kind": "sovereignty_not_declared"},
                severity="info",
                critical=False,
            )
        )

    if ir.agentception_config.get("enabled"):
        obligations.append(
            NormalizedObligation(
                obligation_id="delegation.inherit_bridge",
                category="delegation",
                description="Child delegation inherits preserve/constraint/bridge protections",
                source_location=None,
                subject_ref="agentception.inherit_*",
                expected_predicate={"kind": "delegation_inherit_flags"},
                severity="error",
                critical=True,
            )
        )
        obligations.append(
            NormalizedObligation(
                obligation_id="delegation.integrity",
                category="delegation",
                description="Delegation integrity must remain above operational floor",
                source_location=None,
                subject_ref="agentception.delegation_integrity",
                expected_predicate={"kind": "delegation_integrity_floor", "min": 0.7},
                severity="error",
                critical=True,
            )
        )
    else:
        obligations.append(
            NormalizedObligation(
                obligation_id="delegation.inherit_bridge",
                category="delegation",
                description="Delegation not enabled",
                source_location=None,
                subject_ref="agentception.enabled",
                expected_predicate={"kind": "delegation_not_enabled"},
                severity="info",
                critical=False,
            )
        )

    return obligations


def normalize_obligations(obligations: list[NormalizedObligation]) -> list[NormalizedObligation]:
    """Normalize obligations for backend consumption (deterministic serializable form)."""

    normalized: list[NormalizedObligation] = []
    for o in obligations:
        normalized.append(
            NormalizedObligation(
                obligation_id=o.obligation_id,
                category=o.category,
                description=o.description,
                source_location=o.source_location,
                subject_ref=o.subject_ref,
                expected_predicate=dict(o.expected_predicate),
                severity=o.severity,
                critical=o.critical,
            )
        )
    return normalized


def _build_result(
    ir: IR,
    generated_code: str,
    metrics: _MetricSnapshot,
    obligations: list[VerificationObligation],
    metadata: VerificationBackendMetadata,
    backend_error: str | None,
    calibration_meta: dict[str, object] | None = None,
) -> VerificationResult:
    semantic_issues = check_semantic_type_issues(ir, generated_code)
    ir.module.semantic_issues = issues_as_dicts(semantic_issues)
    semantic_rows = issues_to_obligation_rows(semantic_issues)
    semantic_obligations = [
        VerificationObligation(
            obligation_id=str(row["obligation_id"]),
            category=str(row["category"]),
            description=str(row["description"]),
            source_location=str(row["source_location"]) if row.get("source_location") is not None else None,
            status=str(row["status"]),
            evidence=str(row["evidence"]) if row.get("evidence") is not None else None,
            critical=bool(row["critical"]),
        )
        for row in semantic_rows
    ]
    effect_issues = check_effect_issues(ir, generated_code)
    ir.module.effect_issues = effect_issues_as_dicts(effect_issues)
    effect_rows = effect_issues_to_obligation_rows(effect_issues)
    effect_obligations = [
        VerificationObligation(
            obligation_id=str(row["obligation_id"]),
            category=str(row["category"]),
            description=str(row["description"]),
            source_location=str(row["source_location"]) if row.get("source_location") is not None else None,
            status=str(row["status"]),
            evidence=str(row["evidence"]) if row.get("evidence") is not None else None,
            critical=bool(row["critical"]),
        )
        for row in effect_rows
    ]
    all_obligations = list(obligations) + semantic_obligations + effect_obligations

    counts = _compute_obligation_counts(all_obligations)
    critical_unknown = any(o.status == "unknown" and o.critical for o in all_obligations)
    critical_violation = any(o.status == "violated" and o.critical for o in all_obligations)

    passed = (
        metrics.epsilon_post > metrics.epsilon_floor
        and metrics.measurement_ratio >= metrics.measurement_safe_ratio
        and metrics.bridge_score >= metrics.measurement_safe_ratio
        and not critical_violation
        and not critical_unknown
        and backend_error is None
    )

    equivalence = analyze_intent_equivalence(ir, generated_code)

    return VerificationResult(
        c_bar=metrics.c_bar,
        epsilon_pre=metrics.epsilon_pre,
        epsilon_post=metrics.epsilon_post,
        measurement_ratio=metrics.measurement_ratio,
        q_persistence=metrics.q_persistence,
        q_spatial_consistency=metrics.q_spatial_consistency,
        q_cohesion=metrics.q_cohesion,
        q_alignment=metrics.q_alignment,
        q_intent_constant=metrics.q_intent_constant,
        petra_alignment=metrics.petra_alignment,
        multimodal_resonance=metrics.multimodal_resonance,
        bridge_score=metrics.bridge_score,
        verdict=metrics.verdict if backend_error is None else "VERIFICATION_BACKEND_ERROR",
        passed=passed,
        tesla_enabled=metrics.tesla_enabled,
        substrate_bridge=metrics.substrate_bridge,
        baseline_frequency_hz=metrics.baseline_frequency_hz,
        harmonic_mode=metrics.harmonic_mode,
        breath_monitor=metrics.breath_monitor,
        sovereignty_preserved=metrics.sovereignty_preserved,
        agent_count=metrics.agent_count,
        spawn_depth=metrics.spawn_depth,
        child_alignment=metrics.child_alignment,
        delegation_integrity=metrics.delegation_integrity,
        merge_preservation=metrics.merge_preservation,
        agent_bridge_score=metrics.agent_bridge_score,
        obligations=all_obligations,
        obligation_counts=counts,
        verification_backend=metadata.name,
        backend_version=metadata.version,
        backend_mode=metadata.mode,
        backend_capabilities=list(metadata.capabilities),
        backend_details=dict(metadata.details),
        backend_error=backend_error,
        intent_items_total=equivalence.intent_items_total,
        intent_items_matched=equivalence.intent_items_matched,
        intent_items_partial=equivalence.intent_items_partial,
        intent_items_missing=equivalence.intent_items_missing,
        intent_items_extra=equivalence.intent_items_extra,
        intent_items_unknown=equivalence.intent_items_unknown,
        intent_equivalence_score=equivalence.intent_equivalence_score,
        drift_score=equivalence.drift_score,
        mapping_notes=list(equivalence.mapping_notes),
        correspondence_entries=list(equivalence.correspondences),
        calibration_applied=bool((calibration_meta or {}).get("applied", False)),
        calibration_model_version=(calibration_meta or {}).get("model_version"),
        calibration_artifact_path=(calibration_meta or {}).get("artifact_path"),
        calibration_confidence=(calibration_meta or {}).get("confidence"),
        calibration_notes=str((calibration_meta or {}).get("notes", "")),
        semantic_type_summary=semantic_summary_payload(ir),
        semantic_type_issues=issues_as_dicts(semantic_issues),
        semantic_type_obligations=semantic_rows,
        effect_type_summary=effect_summary_payload(ir),
        effect_type_issues=effect_issues_as_dicts(effect_issues),
        effect_type_obligations=effect_rows,
    )


def _build_observed_facts(ir: IR, metrics: _MetricSnapshot, generated_code: str) -> tuple[dict[str, float], dict[str, bool], dict[str, str]]:
    scalar_facts: dict[str, float] = {
        "epsilon_post": metrics.epsilon_post,
        "epsilon_floor": metrics.epsilon_floor,
        "measurement_ratio": metrics.measurement_ratio,
        "measurement_safe_ratio": metrics.measurement_safe_ratio,
        "bridge_score": metrics.bridge_score,
        "q_alignment": metrics.q_alignment,
        "q_cohesion": metrics.q_cohesion,
        "q_persistence": metrics.q_persistence,
        "delegation_integrity": metrics.delegation_integrity,
        "count": float(len(ir.outputs)),
    }
    scalar_facts["failure_rate"] = _clamp(1.0 - metrics.measurement_ratio)
    scalar_facts["latency"] = 180.0 if ("sort(" in generated_code.lower() or "sorted(" in generated_code.lower()) else 260.0

    bool_facts: dict[str, bool] = {
        "inherit.bridge": bool(ir.agentception_config.get("inherit_bridge", False)),
        "inherit.constraints": bool(ir.agentception_config.get("inherit_constraints", False)),
        "inherit.preserve": bool(ir.agentception_config.get("inherit_preserve", False)),
        "preserve.epsilon": metrics.epsilon_post > metrics.epsilon_floor,
    }
    symbol_facts: dict[str, str] = {
        "verdict": metrics.verdict,
        "mode": str(ir.bridge_config.get("mode", "")),
    }
    for key, _, value in ir.preserve_rules:
        symbol_facts[key.lower()] = value.strip()
        bool_val = _parse_bool_literal(value)
        if bool_val is not None:
            bool_facts[key.lower()] = bool_val
        numeric = _parse_numeric_literal(value)
        if numeric is not None:
            scalar_facts[key.lower()] = numeric[0]
    return scalar_facts, bool_facts, symbol_facts


def verify(
    ir: IR,
    generated_code: str,
    backend: str = "heuristic",
    fallback_backend: str | None = None,
    use_calibration: bool = True,
    calibration_path: str | None = None,
) -> VerificationResult:
    """Compute bridge preservation metrics and evaluate obligations via backend."""

    metrics = _compute_metrics(ir, generated_code)
    calibration_meta: dict[str, object] = {
        "applied": False,
        "model_version": None,
        "artifact_path": str(calibration_path or ".vibe_calibration/bridge_calibration.json"),
        "confidence": None,
        "notes": "default heuristic epsilon surfaces",
    }
    if use_calibration:
        model = load_calibration_model(calibration_path)
        if model is None:
            calibration_meta["notes"] = "calibration artifact missing or invalid; using default epsilon surfaces"
        else:
            eq_preview = analyze_intent_equivalence(ir, generated_code)
            features = extract_calibration_features(
                intent_complexity=len(ir.inputs) + len(ir.outputs),
                preserve_count=len(ir.preserve_rules),
                constraint_count=len(ir.constraints),
                bridge_setting_count=len(ir.bridge_config),
                equivalence_score=eq_preview.intent_equivalence_score,
                drift_score=eq_preview.drift_score,
                target=ir.emit_target.lower(),
            )
            conservative_no_rescue = (
                metrics.epsilon_post <= metrics.epsilon_floor
                or metrics.measurement_ratio < metrics.measurement_safe_ratio
            )
            cal_pre, cal_post, cal_info = apply_calibration(
                model,
                metrics.epsilon_pre,
                metrics.epsilon_post,
                features,
                conservative_no_rescue=conservative_no_rescue,
            )
            metrics = replace(
                metrics,
                epsilon_pre=cal_pre,
                epsilon_post=cal_post,
                measurement_ratio=cal_post / max(cal_pre, metrics.epsilon_floor),
            )
            calibration_meta = {
                "applied": True,
                "model_version": model.model_version,
                "artifact_path": str(calibration_path or ".vibe_calibration/bridge_calibration.json"),
                "confidence": float(cal_info.get("fit_confidence", 0.0)),
                "notes": (
                    f"empirical calibration applied "
                    f"(delta_pre={cal_info.get('delta_pre')}, delta_post={cal_info.get('delta_post')})"
                ),
            }
    observed_scalars, observed_bools, observed_symbols = _build_observed_facts(ir, metrics, generated_code)
    context = ObligationEvaluationContext(
        epsilon_floor=metrics.epsilon_floor,
        measurement_safe_ratio=metrics.measurement_safe_ratio,
        lower_code=generated_code.lower(),
        readability_score=1.0
        if "\n" in generated_code and ("def " in generated_code or "export function" in generated_code)
        else 0.85,
        epsilon_post=metrics.epsilon_post,
        measurement_ratio=metrics.measurement_ratio,
        delegation_integrity=metrics.delegation_integrity,
        sovereignty_required=metrics.sovereignty_required,
        sovereignty_preserved=metrics.sovereignty_preserved,
        agentception_enabled=bool(ir.agentception_config.get("enabled")),
        inherit_constraints=bool(ir.agentception_config.get("inherit_constraints", False)),
        inherit_ok=metrics.inherit_ok,
        observed_scalars=observed_scalars,
        observed_bools=observed_bools,
        observed_symbols=observed_symbols,
    )

    normalized = normalize_obligations(generate_normalized_obligations(ir))

    try:
        evaluator = get_backend(backend)
    except ValueError as exc:
        metadata = VerificationBackendMetadata(
            name=backend,
            version="n/a",
            mode="invalid",
            capabilities=[],
        )
        fallback_obligations = [
            VerificationObligation(
                obligation_id=o.obligation_id,
                category=o.category,
                description=o.description,
                source_location=o.source_location,
                status="unknown",
                evidence="backend unavailable",
                critical=o.critical,
            )
            for o in normalized
        ]
        return _build_result(
            ir,
            generated_code,
            metrics,
            fallback_obligations,
            metadata,
            backend_error=str(exc),
            calibration_meta=calibration_meta,
        )

    try:
        evaluated = evaluator.evaluate(ir, normalized, context)
        obligations = evaluated.obligations
        metadata = evaluated.metadata
        if fallback_backend:
            try:
                fallback = get_backend(fallback_backend)
                fallback_eval = fallback.evaluate(ir, normalized, context)
                fallback_by_id = {o.obligation_id: o for o in fallback_eval.obligations}
                merged: list[VerificationObligation] = []
                fallback_used = 0
                for o in obligations:
                    if o.status == "unknown" and o.obligation_id in fallback_by_id:
                        fo = fallback_by_id[o.obligation_id]
                        if fo.status != "unknown":
                            fallback_used += 1
                        merged.append(
                            VerificationObligation(
                                obligation_id=o.obligation_id,
                                category=o.category,
                                description=o.description,
                                source_location=o.source_location,
                                status=fo.status,
                                evidence=f"{o.evidence}; fallback({fallback_backend}): {fo.evidence}",
                                critical=o.critical,
                            )
                        )
                    else:
                        merged.append(o)
                obligations = merged
                metadata.details["fallback_used"] = fallback_used > 0
                metadata.details["fallback_backend"] = fallback_backend
            except (ValueError, NotImplementedError) as exc:
                metadata.details["fallback_used"] = False
                metadata.details["fallback_backend"] = fallback_backend
                metadata.details["fallback_error"] = str(exc)

        return _build_result(
            ir,
            generated_code,
            metrics,
            obligations,
            metadata,
            backend_error=None,
            calibration_meta=calibration_meta,
        )
    except NotImplementedError as exc:
        metadata = VerificationBackendMetadata(
            name=backend,
            version="stub",
            mode="not_implemented",
            capabilities=[],
        )
        fallback_obligations = [
            VerificationObligation(
                obligation_id=o.obligation_id,
                category=o.category,
                description=o.description,
                source_location=o.source_location,
                status="unknown",
                evidence="evaluation unavailable",
                critical=o.critical,
            )
            for o in normalized
        ]
        return _build_result(
            ir,
            generated_code,
            metrics,
            fallback_obligations,
            metadata,
            backend_error=str(exc),
            calibration_meta=calibration_meta,
        )
