"""Intent-seeded type inference and diagnostics (Phase 4.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re

from .ir import IR


@dataclass(slots=True)
class InferenceIssue:
    issue_id: str
    severity: str
    category: str
    message: str
    source_location: str | None = None
    evidence: str | None = None


@dataclass(slots=True)
class InferenceSummary:
    declared_types: dict[str, str] = field(default_factory=dict)
    inferred_bindings: dict[str, dict[str, object]] = field(default_factory=dict)
    unresolved_points: list[dict[str, str]] = field(default_factory=list)
    contradiction_count: int = 0
    unresolved_count: int = 0
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class InferenceResult:
    summary: InferenceSummary
    issues: list[InferenceIssue] = field(default_factory=list)


def _binding_map(ir: IR) -> dict[str, str]:
    return {b.name: b.value_id for b in ir.module.bindings}


def _interface_hints(ir: IR) -> dict[str, str]:
    hints: dict[str, str] = {}
    for decl in ir.interfaces:
        if ":" not in decl:
            continue
        name, rhs = decl.split(":", 1)
        t = rhs.strip().strip("{}").strip()
        if t:
            hints[name.strip()] = t
    return hints


def _helper_profiles(ir: IR) -> list[dict[str, str]]:
    outputs = ir.outputs
    profile: dict[str, str] = {
        "helper": "candidate_selection",
        "returns": outputs.get("processor", next(iter(outputs.values()), "unknown")),
    }
    if "fee" in outputs:
        profile["supports"] = outputs["fee"]
    return [profile]


def annotate_type_inference(ir: IR) -> InferenceResult:
    bindings = _binding_map(ir)
    declared: dict[str, str] = {}
    for b in sorted(ir.module.bindings, key=lambda row: row.name):
        if b.name.startswith("intent.input.") or b.name.startswith("intent.output."):
            declared[b.name] = str(ir.module.values[b.value_id].data)
        else:
            declared[b.name] = b.vtype
    interface_hints = _interface_hints(ir)
    semantic = ir.module.semantic_summary.get("binding_qualifiers", {})
    effect_hints = ir.module.effect_summary.get("value_effects", {})
    resource_hints = ir.module.resource_summary.get("value_resources", {})
    lower_constraints = [c.lower() for c in ir.constraints]

    inferred_bindings: dict[str, dict[str, object]] = {}
    unresolved: list[dict[str, str]] = []
    issues: list[InferenceIssue] = []

    deterministic_bias = any("deterministic" in c for c in lower_constraints)
    secret_bias = any("no hardcoded secrets" in c or "secret" in c for c in lower_constraints)

    contradictions = 0
    for name, vid in sorted(bindings.items()):
        declared_type = str(declared.get(name, ir.module.values[vid].vtype))
        inferred_type = declared_type
        source = "declared"

        if declared_type in {"variant", "named"}:
            unresolved.append({"binding": name, "reason": f"declared type `{declared_type}` is too broad for first-pass inference"})
            source = "unresolved_seed"

        if name.startswith("intent.output.") and "processor" in name and interface_hints.get("processor_id"):
            hinted = interface_hints["processor_id"]
            if hinted != declared_type:
                contradictions += 1
                issues.append(
                    InferenceIssue(
                        issue_id=f"inference.contradiction.{name}",
                        severity="high",
                        category="contradictory_inference",
                        message="intent output declaration conflicts with inferred helper/interface type",
                        source_location=name,
                        evidence=f"declared={declared_type}, inferred_hint={hinted}",
                    )
                )
            inferred_type = hinted
            source = "interface_hint"

        inferred_bindings[name] = {
            "declared_type": declared_type,
            "inferred_type": inferred_type,
            "source": source,
            "semantic_qualifiers": list(semantic.get(name, [])),
            "effect_hints": list(effect_hints.get(name, [])),
            "resource_hints": list(resource_hints.get(name, [])),
            "deterministic_bias": deterministic_bias if name.startswith("intent.output.") else False,
            "secret_bias": secret_bias if name.startswith("intent.input.") else False,
        }

        if "secret_sensitive" in semantic.get(name, []) and not inferred_bindings[name]["secret_bias"]:
            issues.append(
                InferenceIssue(
                    issue_id=f"inference.qualifier.secret.{name}",
                    severity="medium",
                    category="lost_qualifier",
                    message="secret-sensitive intent qualifier was not preserved by inference context",
                    source_location=name,
                    evidence=f"qualifiers={semantic.get(name, [])}",
                )
            )
        if "deterministic" in semantic.get(name, []) and not inferred_bindings[name]["deterministic_bias"]:
            issues.append(
                InferenceIssue(
                    issue_id=f"inference.qualifier.deterministic.{name}",
                    severity="medium",
                    category="lost_qualifier",
                    message="deterministic intent qualifier was not preserved by inference context",
                    source_location=name,
                    evidence=f"qualifiers={semantic.get(name, [])}",
                )
            )

    unresolved_count = len(unresolved)
    for row in unresolved:
        issues.append(
            InferenceIssue(
                issue_id=f"inference.unresolved.{row['binding']}",
                severity="high",
                category="unresolved_inference",
                message="unresolved inferred type remains on an intent-preservation surface",
                source_location=row["binding"],
                evidence=row["reason"],
            )
        )

    summary = InferenceSummary(
        declared_types=declared,
        inferred_bindings=inferred_bindings,
        unresolved_points=unresolved,
        contradiction_count=contradictions,
        unresolved_count=unresolved_count,
        propagation_notes=[
            "Inference is intent-seeded and deterministic; unresolved entries remain explicit.",
            "Inference diagnostics are preservation-surface signals, not opaque compiler internals.",
            "This pass is partial and does not claim global polymorphic completeness.",
        ],
    )
    summary_payload = asdict(summary)
    summary_payload["helper_profiles"] = _helper_profiles(ir)
    ir.module.inference_summary = summary_payload
    return InferenceResult(summary=summary, issues=issues)


def check_inference_issues(ir: IR, generated_code: str) -> list[InferenceIssue]:
    issues: list[InferenceIssue] = []
    summary = ir.module.inference_summary
    inferred = dict(summary.get("inferred_bindings", {}))
    lower = generated_code.lower()

    for name, row in sorted(inferred.items()):
        declared = str(row.get("declared_type", "unknown"))
        inferred_type = str(row.get("inferred_type", "unknown"))
        if declared != inferred_type:
            issues.append(
                InferenceIssue(
                    issue_id=f"inference.contradiction.{name}",
                    severity="high",
                    category="contradictory_inference",
                    message="declared intent type conflicts with inferred helper/interface type",
                    source_location=name,
                    evidence=f"declared={declared}, inferred={inferred_type}",
                )
            )

    if re.search(r"random\(|uuid|time\.time\(|date\.now\(", lower):
        for name, row in sorted(inferred.items()):
            if row.get("deterministic_bias"):
                issues.append(
                    InferenceIssue(
                        issue_id=f"inference.helper.nondeterministic.{name}",
                        severity="high",
                        category="helper_interface_mismatch",
                        message="deterministic intent-seeded inference conflicts with nondeterministic helper behavior",
                        source_location=name,
                        evidence="random/time/uuid marker detected",
                    )
                )
                break

    if re.search(r"secret\s*=|token\s*=|password\s*=", lower):
        for name, row in sorted(inferred.items()):
            if row.get("secret_bias"):
                issues.append(
                    InferenceIssue(
                        issue_id=f"inference.helper.secret.{name}",
                        severity="high",
                        category="effect_resource_type_conflict",
                        message="secret-sensitive inference profile conflicts with emitted secret-like literal assignment",
                        source_location=name,
                        evidence="secret/token/password assignment marker detected",
                    )
                )
                break

    for unresolved in summary.get("unresolved_points", []):
        issues.append(
            InferenceIssue(
                issue_id=f"inference.unresolved.runtime.{unresolved.get('binding', 'unknown')}",
                severity="medium",
                category="unresolved_inference",
                message="unresolved inferred type reached verification stage; preserve intent declaration or refine type hints",
                source_location=str(unresolved.get("binding", "")),
                evidence=str(unresolved.get("reason", "unknown unresolved inference")),
            )
        )
    return issues


def inference_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "declared_types": dict(ir.module.inference_summary.get("declared_types", {})),
        "inferred_bindings": dict(ir.module.inference_summary.get("inferred_bindings", {})),
        "helper_profiles": list(ir.module.inference_summary.get("helper_profiles", [])),
        "unresolved_points": list(ir.module.inference_summary.get("unresolved_points", [])),
        "contradiction_count": int(ir.module.inference_summary.get("contradiction_count", 0)),
        "unresolved_count": int(ir.module.inference_summary.get("unresolved_count", 0)),
        "propagation_notes": list(ir.module.inference_summary.get("propagation_notes", [])),
        "issues": list(ir.module.inference_issues),
    }


def inference_issues_to_obligation_rows(issues: list[InferenceIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "inference_type",
                "description": issue.message,
                "source_location": issue.source_location,
                "status": "violated" if issue.severity in {"critical", "high"} else "unknown",
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[InferenceIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
