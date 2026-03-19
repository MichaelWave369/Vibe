"""First-pass resource type attribution/checking (Phase 4.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re

from .ir import IR


RESOURCE_TYPES = {
    "memory_bound",
    "cpu_bound",
    "latency_budget",
    "allocation_sensitive",
    "bounded_iteration",
    "unbounded_iteration",
    "target_resource_profile",
    "unknown_resource",
}


@dataclass(slots=True)
class ResourceIssue:
    issue_id: str
    severity: str
    resource_type: str
    message: str
    evidence: str | None = None


@dataclass(slots=True)
class ResourceSummary:
    inferred_resources: list[str] = field(default_factory=list)
    declared_bounds: dict[str, str] = field(default_factory=dict)
    module_profile: dict[str, object] = field(default_factory=dict)
    value_resources: dict[str, list[str]] = field(default_factory=dict)
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResourceResult:
    summary: ResourceSummary
    issues: list[ResourceIssue] = field(default_factory=list)


def _binding_map(ir: IR) -> dict[str, str]:
    return {b.name: b.value_id for b in ir.module.bindings}


def _add_value_resource(ir: IR, value_id: str, resource_type: str) -> None:
    if resource_type not in RESOURCE_TYPES:
        return
    tags = ir.module.values[value_id].resource_tags
    if resource_type not in tags:
        tags.append(resource_type)
        tags.sort()


def annotate_resources(ir: IR) -> ResourceResult:
    bindings = _binding_map(ir)
    output_refs = [vid for name, vid in bindings.items() if name.startswith("intent.output.")]

    inferred: set[str] = {"target_resource_profile"}
    declared_bounds: dict[str, str] = {}

    for key, op, value in ir.preserve_rules:
        k = key.lower().strip()
        v = value.strip()
        if "memory" in k:
            inferred.add("memory_bound")
            declared_bounds["memory"] = f"{op} {v}"
        if "cpu" in k or "complexity" in k:
            inferred.add("cpu_bound")
            declared_bounds["cpu"] = f"{op} {v}"
        if "latency" in k:
            inferred.add("latency_budget")
            declared_bounds["latency"] = f"{op} {v}"

    if any("deterministic" in c.lower() for c in ir.constraints):
        inferred.add("bounded_iteration")
    if any("fallback" in c.lower() for c in ir.constraints):
        inferred.add("allocation_sensitive")

    effect_inferred = set(ir.module.effect_summary.get("inferred_effects", []))
    if "fallback_path" in effect_inferred:
        inferred.add("allocation_sensitive")
    if "stateful" in effect_inferred or "io" in effect_inferred:
        inferred.add("unknown_resource")

    for vid in output_refs:
        for rt in sorted(inferred):
            if rt in {"memory_bound", "cpu_bound", "latency_budget", "allocation_sensitive", "bounded_iteration", "target_resource_profile"}:
                _add_value_resource(ir, vid, rt)

    module_profile = {
        "emit_target": ir.emit_target,
        "bridge_mode": str(ir.bridge_config.get("mode", "")),
        "resource_hints": sorted(inferred),
    }
    value_resources = {name: list(ir.module.values[vid].resource_tags) for name, vid in sorted(bindings.items())}

    summary = ResourceSummary(
        inferred_resources=sorted(inferred),
        declared_bounds=declared_bounds,
        module_profile=module_profile,
        value_resources=value_resources,
        propagation_notes=[
            "Resource profiles are first-pass compile-time estimates.",
            "Resource checks complement obligations; they do not prove exact runtime bounds.",
        ],
    )
    return ResourceResult(summary=summary, issues=[])


def _observed_resource_markers(code: str) -> dict[str, bool]:
    lower = code.lower()
    return {
        "unbounded_iteration": bool(re.search(r"while\s+true|for\s*\(\s*;\s*;", lower)),
        "nested_loops": lower.count("for ") + lower.count("for(") > 1,
        "allocation_heavy": bool(re.search(r"\[\]|dict\(|new\s+array|append\(|push\(", lower)),
        "network_heavy": bool(re.search(r"http://|https://|fetch\(|requests\.", lower)),
    }


def check_resource_issues(ir: IR, generated_code: str) -> list[ResourceIssue]:
    summary = ir.module.resource_summary
    inferred = set(summary.get("inferred_resources", []))
    bounds = dict(summary.get("declared_bounds", {}))
    observed = _observed_resource_markers(generated_code)

    issues: list[ResourceIssue] = []
    if observed["unbounded_iteration"] and "bounded_iteration" in inferred:
        issues.append(
            ResourceIssue(
                issue_id="resource.iteration.unbounded",
                severity="critical",
                resource_type="unbounded_iteration",
                message="bounded iteration contract conflicts with unbounded iteration marker",
                evidence=str(observed),
            )
        )
    if "memory" in bounds and observed["allocation_heavy"]:
        issues.append(
            ResourceIssue(
                issue_id="resource.memory.allocation_risk",
                severity="high",
                resource_type="memory_bound",
                message="memory bound declared but allocation-heavy marker observed",
                evidence=f"bound={bounds['memory']}, observed={observed}",
            )
        )
    if "cpu" in bounds and observed["nested_loops"]:
        issues.append(
            ResourceIssue(
                issue_id="resource.cpu.complexity_risk",
                severity="high",
                resource_type="cpu_bound",
                message="cpu/complexity bound declared but nested loop marker observed",
                evidence=f"bound={bounds['cpu']}, observed={observed}",
            )
        )
    if "latency" in bounds and observed["network_heavy"]:
        issues.append(
            ResourceIssue(
                issue_id="resource.latency.network_risk",
                severity="high",
                resource_type="latency_budget",
                message="latency budget declared but network-heavy marker observed",
                evidence=f"bound={bounds['latency']}, observed={observed}",
            )
        )
    if "unknown_resource" in inferred:
        issues.append(
            ResourceIssue(
                issue_id="resource.unknown.profile",
                severity="medium",
                resource_type="unknown_resource",
                message="unknown resource interactions remain in inferred profile",
                evidence=str(sorted(inferred)),
            )
        )

    return issues


def resource_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "inferred_resources": list(ir.module.resource_summary.get("inferred_resources", [])),
        "declared_bounds": dict(ir.module.resource_summary.get("declared_bounds", {})),
        "module_profile": dict(ir.module.resource_summary.get("module_profile", {})),
        "value_resources": dict(ir.module.resource_summary.get("value_resources", {})),
        "propagation_notes": list(ir.module.resource_summary.get("propagation_notes", [])),
        "issues": list(ir.module.resource_issues),
    }


def resource_issues_to_obligation_rows(issues: list[ResourceIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "resource_type",
                "description": issue.message,
                "source_location": None,
                "status": "violated" if issue.severity in {"critical", "high"} else "unknown",
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[ResourceIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
