"""First-pass effect type attribution/checking (Phase 4.2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re

from .ir import IR


EFFECTS = {
    "pure",
    "io",
    "stateful",
    "nondeterministic",
    "network",
    "secret_exposing",
    "fallback_path",
    "bridge_critical_effect",
    "unknown_effect",
}


@dataclass(slots=True)
class EffectIssue:
    issue_id: str
    severity: str
    effect: str
    message: str
    evidence: str | None = None


@dataclass(slots=True)
class EffectSummary:
    inferred_effects: list[str] = field(default_factory=list)
    required_effects: list[str] = field(default_factory=list)
    forbidden_effects: list[str] = field(default_factory=list)
    value_effects: dict[str, list[str]] = field(default_factory=dict)
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EffectResult:
    summary: EffectSummary
    issues: list[EffectIssue] = field(default_factory=list)


def _binding_map(ir: IR) -> dict[str, str]:
    return {b.name: b.value_id for b in ir.module.bindings}


def _add_value_effect(ir: IR, value_id: str, effect: str) -> None:
    if effect not in EFFECTS:
        return
    tags = ir.module.values[value_id].effect_tags
    if effect not in tags:
        tags.append(effect)
        tags.sort()


def annotate_effects(ir: IR) -> EffectResult:
    bindings = _binding_map(ir)
    output_refs = [vid for name, vid in bindings.items() if name.startswith("intent.output.")]

    inferred: set[str] = {"pure"}
    required: set[str] = set()
    forbidden: set[str] = set()

    lower_constraints = [c.lower() for c in ir.constraints]
    if any("fallback" in c for c in lower_constraints):
        inferred.add("fallback_path")
        for vid in output_refs:
            _add_value_effect(ir, vid, "fallback_path")
    if any("deterministic" in c for c in lower_constraints):
        forbidden.add("nondeterministic")
    if any("stateless" in c for c in lower_constraints):
        forbidden.add("stateful")
    if any("no side effects" in c for c in lower_constraints):
        required.add("pure")
        forbidden.update({"io", "stateful"})

    for key, _, value in ir.preserve_rules:
        k = key.lower().strip()
        v = value.lower().strip()
        if "no_side_effects" in k or "side_effect" in k:
            required.add("pure")
            forbidden.update({"io", "stateful"})
        if "fallback" in k and v in {"true", "required", "strict"}:
            required.add("fallback_path")
        if "sovereignty" in k and v in {"true", "strict", "yes", "1"}:
            inferred.add("bridge_critical_effect")

    if str(ir.bridge_config.get("mode", "")).lower() == "strict":
        inferred.add("bridge_critical_effect")

    if ir.agentora_config.get("enabled"):
        inferred.update({"io", "stateful"})
    if ir.agentception_config.get("enabled"):
        inferred.add("stateful")

    binding_quals = ir.module.semantic_summary.get("binding_qualifiers", {})
    if any("secret_sensitive" in quals for quals in binding_quals.values()):
        inferred.add("unknown_effect")

    for vid in output_refs:
        _add_value_effect(ir, vid, "bridge_critical_effect" if "bridge_critical_effect" in inferred else "pure")
        for eff in sorted(inferred):
            if eff in {"fallback_path", "bridge_critical_effect"}:
                _add_value_effect(ir, vid, eff)

    value_effects = {name: list(ir.module.values[vid].effect_tags) for name, vid in sorted(bindings.items())}

    summary = EffectSummary(
        inferred_effects=sorted(inferred),
        required_effects=sorted(required),
        forbidden_effects=sorted(forbidden),
        value_effects=value_effects,
        propagation_notes=[
            "Effects are first-pass compile-time inferences and constraints.",
            "Effect checks complement obligations; they do not replace bridge law.",
        ],
    )
    return EffectResult(summary=summary, issues=[])


def _observed_effects_from_code(code: str) -> set[str]:
    lower = code.lower()
    effects: set[str] = {"pure"}
    if re.search(r"\bprint\(|\bopen\(|\bfetch\(|\brequests\.|\bhttp://|\bhttps://", lower):
        effects.add("io")
    if re.search(r"global\s+|\bsetattr\(|\bstate\b|\bmutable\b", lower):
        effects.add("stateful")
    if re.search(r"random\(|uuid|time\.time\(|date\.now\(", lower):
        effects.add("nondeterministic")
    if "http://" in lower or "https://" in lower:
        effects.add("network")
    if re.search(r"secret\s*=|token\s*=|password\s*=", lower):
        effects.add("secret_exposing")
    if "fallback" in lower:
        effects.add("fallback_path")
    return effects or {"unknown_effect"}


def check_effect_issues(ir: IR, generated_code: str) -> list[EffectIssue]:
    summary = ir.module.effect_summary
    required = set(summary.get("required_effects", []))
    forbidden = set(summary.get("forbidden_effects", []))
    inferred = set(summary.get("inferred_effects", []))
    observed = _observed_effects_from_code(generated_code)

    issues: list[EffectIssue] = []
    for eff in sorted(required):
        if eff not in observed and eff not in inferred:
            issues.append(
                EffectIssue(
                    issue_id=f"effect.required.{eff}",
                    severity="high",
                    effect=eff,
                    message=f"required effect `{eff}` not observed in inferred/observed profile",
                    evidence=f"required={sorted(required)}, observed={sorted(observed)}",
                )
            )
    for eff in sorted(forbidden):
        if eff in observed:
            issues.append(
                EffectIssue(
                    issue_id=f"effect.forbidden.{eff}",
                    severity="critical",
                    effect=eff,
                    message=f"forbidden effect `{eff}` observed in emitted artifact",
                    evidence=f"forbidden={sorted(forbidden)}, observed={sorted(observed)}",
                )
            )

    if "pure" in required and any(eff in observed for eff in {"io", "stateful", "network"}):
        issues.append(
            EffectIssue(
                issue_id="effect.purity.violation",
                severity="critical",
                effect="pure",
                message="path expected to be pure but side-effecting behavior detected",
                evidence=f"observed={sorted(observed)}",
            )
        )
    if "nondeterministic" in observed and "nondeterministic" in forbidden:
        issues.append(
            EffectIssue(
                issue_id="effect.determinism.mismatch",
                severity="critical",
                effect="nondeterministic",
                message="determinism constraint conflicts with nondeterministic observed effect",
                evidence=f"observed={sorted(observed)}",
            )
        )

    if "unknown_effect" in inferred and "secret_exposing" in observed:
        issues.append(
            EffectIssue(
                issue_id="effect.secret.exposure",
                severity="high",
                effect="secret_exposing",
                message="secret-sensitive path appears to expose secret-like literal",
                evidence="secret/token/password assignment marker observed",
            )
        )

    return issues


def effect_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "inferred_effects": list(ir.module.effect_summary.get("inferred_effects", [])),
        "required_effects": list(ir.module.effect_summary.get("required_effects", [])),
        "forbidden_effects": list(ir.module.effect_summary.get("forbidden_effects", [])),
        "value_effects": dict(ir.module.effect_summary.get("value_effects", {})),
        "propagation_notes": list(ir.module.effect_summary.get("propagation_notes", [])),
        "issues": list(ir.module.effect_issues),
    }


def effect_issues_to_obligation_rows(issues: list[EffectIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "effect_type",
                "description": issue.message,
                "source_location": None,
                "status": "violated" if issue.severity in {"critical", "high"} else "unknown",
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[EffectIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
