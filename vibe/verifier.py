"""Semantic bridge verifier for generated Vibe implementations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ir import DEFAULT_EPSILON_FLOOR, DEFAULT_MEASUREMENT_SAFE_RATIO, IR

ObligationStatus = str


@dataclass(slots=True)
class VerificationObligation:
    obligation_id: str
    category: str
    description: str
    source_location: str | None
    status: ObligationStatus
    evidence: str | None = None


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



def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _status_for_bool(value: bool, evidence: str) -> tuple[str, str]:
    return ("satisfied", evidence) if value else ("violated", evidence)


def _compute_obligation_counts(obligations: list[VerificationObligation]) -> dict[str, int]:
    counts = {"satisfied": 0, "violated": 0, "unknown": 0, "not_applicable": 0}
    for o in obligations:
        counts[o.status] = counts.get(o.status, 0) + 1
    return counts


def verify(ir: IR, generated_code: str) -> VerificationResult:
    """Compute heuristic bridge preservation metrics for v0.x."""

    epsilon_floor = float(ir.bridge_config.get("epsilon_floor", DEFAULT_EPSILON_FLOOR))
    measurement_safe_ratio = float(
        ir.bridge_config.get("measurement_safe_ratio", DEFAULT_MEASUREMENT_SAFE_RATIO)
    )

    c_bar = sum(bool(x) for x in [ir.goal, ir.inputs, ir.outputs]) / 3
    epsilon_pre = 0.35 + 0.55 * c_bar

    constraint_hits = 0
    lower_code = generated_code.lower()
    for constraint in ir.constraints:
        c = constraint.lower()
        if "deterministic" in c and ("sort(" in lower_code or "sorted(" in lower_code):
            constraint_hits += 1
        elif "no hardcoded secrets" in c and "secret" not in lower_code:
            constraint_hits += 1
        elif "fallback" in c and "fallback" in lower_code:
            constraint_hits += 1
        elif c and c in lower_code:
            constraint_hits += 1

    constraint_score = 1.0 if not ir.constraints else constraint_hits / len(ir.constraints)
    deterministic_score = 1.0 if ("sort(" in lower_code or "sorted(" in lower_code) else 0.8
    readability_score = 1.0 if "\n" in generated_code and ("def " in generated_code or "export function" in generated_code) else 0.85
    preserve_score = 1.0 if ir.preserve_rules else 0.9

    tesla_factor = 0.0
    sovereignty_preserved: bool | None = None
    if ir.tesla_victory_layer:
        tesla_factor = 0.04
        sovereignty_required = bool(ir.arc_tower_policy.get("preserve_sovereignty", False))
        sovereignty_preserved = ("sovereignty" in lower_code or "preserve" in lower_code) if sovereignty_required else True
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
    q_intent_constant = _clamp(0.65 * c_bar + 0.25 * constraint_score + 0.10 * agent_bridge_score + tesla_factor)

    petra_alignment = _clamp(0.55 * q_alignment + 0.35 * q_intent_constant + 0.10 * agent_bridge_score)
    multimodal_resonance = _clamp(0.55 * q_cohesion + 0.25 * readability_score + 0.20 * agent_bridge_score + tesla_factor)

    epsilon_post = _clamp(
        epsilon_pre
        * (0.70 * q_alignment + 0.1 * constraint_score + 0.1 * deterministic_score + 0.1 * readability_score)
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

    obligations: list[VerificationObligation] = []

    for idx, (key, op, value) in enumerate(ir.preserve_rules, start=1):
        status = "unknown"
        evidence = "No formal solver bound yet; preserved as heuristic surface"
        if key.lower() in {"readability", "testability"}:
            status = "satisfied" if readability_score >= 0.85 else "violated"
            evidence = f"readability_score={readability_score:.3f}"
        obligations.append(
            VerificationObligation(
                obligation_id=f"preserve.{idx}",
                category="preserve",
                description=f"Preserve rule `{key} {op} {value}`",
                source_location=None,
                status=status,
                evidence=evidence,
            )
        )

    for idx, c in enumerate(ir.constraints, start=1):
        matched = c.lower() in lower_code or (
            "deterministic" in c.lower() and ("sort(" in lower_code or "sorted(" in lower_code)
        ) or ("no hardcoded secrets" in c.lower() and "secret" not in lower_code) or (
            "fallback" in c.lower() and "fallback" in lower_code
        ) or (
            "preserve parent constraints" in c.lower()
            and bool(ir.agentception_config.get("inherit_constraints", False))
        )
        status, evidence = _status_for_bool(matched, "heuristic generated-code pattern match")
        obligations.append(
            VerificationObligation(
                obligation_id=f"constraint.{idx}",
                category="constraint",
                description=f"Constraint `{c}`",
                source_location=None,
                status=status,
                evidence=evidence,
            )
        )

    obligations.append(
        VerificationObligation(
            obligation_id="bridge.founding.epsilon_post_gt_floor",
            category="bridge",
            description="Founding law: epsilon_post > epsilon_floor",
            source_location=None,
            status="satisfied" if epsilon_post > epsilon_floor else "violated",
            evidence=f"epsilon_post={epsilon_post:.4f}, epsilon_floor={epsilon_floor:.4f}",
        )
    )
    obligations.append(
        VerificationObligation(
            obligation_id="bridge.founding.measurement_ratio_safe",
            category="bridge",
            description="Founding law: measurement_ratio >= measurement_safe_ratio",
            source_location=None,
            status="satisfied" if measurement_ratio >= measurement_safe_ratio else "violated",
            evidence=f"measurement_ratio={measurement_ratio:.4f}, threshold={measurement_safe_ratio:.4f}",
        )
    )

    if ir.tesla_victory_layer and bool(ir.arc_tower_policy.get("preserve_sovereignty", False)):
        obligations.append(
            VerificationObligation(
                obligation_id="sovereignty.preserve",
                category="sovereignty",
                description="Tesla sovereignty preservation must hold when declared",
                source_location=None,
                status="satisfied" if sovereignty_preserved else "violated",
                evidence="heuristic sovereignty marker check",
            )
        )
    else:
        obligations.append(
            VerificationObligation(
                obligation_id="sovereignty.preserve",
                category="sovereignty",
                description="Sovereignty obligation not declared",
                source_location=None,
                status="not_applicable",
                evidence="preserve.sovereignty not requested",
            )
        )

    if ir.agentception_config.get("enabled"):
        obligations.append(
            VerificationObligation(
                obligation_id="delegation.inherit_bridge",
                category="delegation",
                description="Child delegation inherits preserve/constraint/bridge protections",
                source_location=None,
                status="satisfied" if inherit_ok else "violated",
                evidence="inherit flags from agentception config",
            )
        )
        obligations.append(
            VerificationObligation(
                obligation_id="delegation.integrity",
                category="delegation",
                description="Delegation integrity must remain above operational floor",
                source_location=None,
                status="satisfied" if delegation_integrity >= 0.7 else "violated",
                evidence=f"delegation_integrity={delegation_integrity:.3f}",
            )
        )
    else:
        obligations.append(
            VerificationObligation(
                obligation_id="delegation.inherit_bridge",
                category="delegation",
                description="Delegation not enabled",
                source_location=None,
                status="not_applicable",
                evidence="agentception disabled",
            )
        )

    counts = _compute_obligation_counts(obligations)
    critical_unknown = any(
        o.status == "unknown" and o.category in {"bridge", "sovereignty", "delegation"} for o in obligations
    )
    critical_violation = any(
        o.status == "violated" and o.category in {"bridge", "sovereignty", "delegation"}
        for o in obligations
    )

    passed = (
        epsilon_post > epsilon_floor
        and measurement_ratio >= measurement_safe_ratio
        and bridge_score >= measurement_safe_ratio
    )
    if sovereignty_preserved is False:
        passed = False
    if ir.agentception_config.get("enabled") and not inherit_ok:
        passed = False
    if critical_violation or critical_unknown:
        passed = False

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
        tesla_enabled=ir.tesla_victory_layer,
        substrate_bridge=list(ir.arc_tower_policy.get("substrate_bridge", [])) if ir.arc_tower_policy else [],
        baseline_frequency_hz=float(ir.life_ray_protocol.get("baseline_frequency_hz", 0.0)) if ir.life_ray_protocol else 0.0,
        harmonic_mode=str(ir.life_ray_protocol.get("harmonic_mode", "")) if ir.life_ray_protocol else "",
        breath_monitor=str(ir.breath_cycle_protocol.get("monitor", "")) if ir.breath_cycle_protocol else "",
        sovereignty_preserved=sovereignty_preserved,
        agent_count=agent_count,
        spawn_depth=spawn_depth,
        child_alignment=child_alignment,
        delegation_integrity=delegation_integrity,
        merge_preservation=merge_preservation,
        agent_bridge_score=agent_bridge_score,
        obligations=obligations,
        obligation_counts=counts,
    )
