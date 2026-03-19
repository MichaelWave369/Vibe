"""Bridge propagation across agent boundaries (Phase 5.2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import prod

from .ir import IR


@dataclass(slots=True)
class AgentBoundaryIssue:
    issue_id: str
    severity: str
    category: str
    message: str
    edge: str
    evidence: str | None = None


@dataclass(slots=True)
class AgentBoundarySummary:
    edge_summaries: list[dict[str, object]] = field(default_factory=list)
    pipeline_bridge_score: float = 1.0
    critical_boundary_failures: list[str] = field(default_factory=list)
    aggregation_rule: str = "pipeline_bridge_score = product(edge_bridge_scores)"
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentBoundaryResult:
    summary: AgentBoundarySummary
    issues: list[AgentBoundaryIssue] = field(default_factory=list)


def _rule_tokens(values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for raw in values:
        t = raw.lower()
        if "deterministic" in t:
            tokens.add("deterministic")
        if "stateless" in t:
            tokens.add("stateless")
        if "coherence" in t:
            tokens.add("coherence_preserving")
        if "sovereignty" in t or "bridge_critical" in t:
            tokens.add("bridge_critical")
        if "latency" in t:
            tokens.add("latency_bounded")
    return tokens


def annotate_agent_bridges(ir: IR) -> AgentBoundaryResult:
    graph = ir.module.agent_graph_summary
    nodes = dict(graph.get("agents", {}))
    edges = list(graph.get("edges", []))

    inferred_effects = set(ir.module.effect_summary.get("inferred_effects", []))
    inferred_resources = set(ir.module.resource_summary.get("inferred_resources", []))

    edge_rows: list[dict[str, object]] = []
    issues: list[AgentBoundaryIssue] = []
    critical_failures: list[str] = []

    for row in edges:
        src = str(row.get("source", ""))
        dst = str(row.get("target", ""))
        edge_name = f"{src}->{dst}"
        up = nodes.get(src, {})
        down = nodes.get(dst, {})

        emits = str(up.get("emits", ""))
        receives = str(down.get("receives", ""))
        type_ok = bool(emits and receives and emits == receives)

        up_rules = _rule_tokens(list(up.get("preserve", [])) + list(up.get("constraints", [])))
        down_rules = _rule_tokens(list(down.get("preserve", [])) + list(down.get("constraints", [])))

        semantic_loss = sorted([r for r in down_rules if r in {"deterministic", "coherence_preserving", "bridge_critical"} and r not in up_rules])
        effect_mismatch = "stateless" in down_rules and "stateful" in inferred_effects
        resource_mismatch = "latency_bounded" in down_rules and "unknown_resource" in inferred_resources

        penalties = 0.0
        if not type_ok:
            penalties += 0.55
        if semantic_loss:
            penalties += 0.2
        if effect_mismatch:
            penalties += 0.15
        if resource_mismatch:
            penalties += 0.1
        edge_score = max(0.0, round(1.0 - penalties, 6))

        bridge_critical = "bridge_critical" in down_rules or "bridge_critical" in up_rules
        bridge_failure = bridge_critical and edge_score < 0.85
        critical_failure = (not type_ok) or bridge_failure
        if critical_failure:
            critical_failures.append(edge_name)

        if not type_ok:
            issues.append(
                AgentBoundaryIssue(
                    issue_id=f"agent_boundary_type_mismatch.{src}.{dst}",
                    severity="critical",
                    category="agent_boundary_type_mismatch",
                    message="upstream emits contract does not satisfy downstream receives contract",
                    edge=edge_name,
                    evidence=f"{src}.emits={emits}, {dst}.receives={receives}",
                )
            )
        if semantic_loss:
            issues.append(
                AgentBoundaryIssue(
                    issue_id=f"agent_boundary_semantic_loss.{src}.{dst}",
                    severity="high",
                    category="agent_boundary_semantic_loss",
                    message="downstream semantic/preserve requirements are not propagated from upstream boundary",
                    edge=edge_name,
                    evidence=f"missing={semantic_loss}",
                )
            )
        if effect_mismatch:
            issues.append(
                AgentBoundaryIssue(
                    issue_id=f"agent_boundary_effect_mismatch.{src}.{dst}",
                    severity="high",
                    category="agent_boundary_effect_mismatch",
                    message="downstream stateless boundary conflicts with inferred stateful effect profile",
                    edge=edge_name,
                    evidence=f"inferred_effects={sorted(inferred_effects)}",
                )
            )
        if resource_mismatch:
            issues.append(
                AgentBoundaryIssue(
                    issue_id=f"agent_boundary_resource_mismatch.{src}.{dst}",
                    severity="high",
                    category="agent_boundary_resource_mismatch",
                    message="downstream latency/resource boundary conflicts with uncertain upstream resource profile",
                    edge=edge_name,
                    evidence=f"inferred_resources={sorted(inferred_resources)}",
                )
            )
        if bridge_failure:
            issues.append(
                AgentBoundaryIssue(
                    issue_id=f"agent_boundary_bridge_failure.{src}.{dst}",
                    severity="critical",
                    category="agent_boundary_bridge_failure",
                    message="bridge-critical boundary score fell below threshold",
                    edge=edge_name,
                    evidence=f"edge_score={edge_score}, threshold=0.85",
                )
            )

        edge_rows.append(
            {
                "edge": edge_name,
                "upstream_emits": emits,
                "downstream_receives": receives,
                "type_compatible": type_ok,
                "semantic_loss": semantic_loss,
                "effect_mismatch": effect_mismatch,
                "resource_mismatch": resource_mismatch,
                "bridge_critical_boundary": bridge_critical,
                "edge_bridge_score": edge_score,
                "critical_failure": critical_failure,
            }
        )

    pipeline_score = round(prod([float(r["edge_bridge_score"]) for r in edge_rows]), 6) if edge_rows else 1.0
    summary = AgentBoundarySummary(
        edge_summaries=edge_rows,
        pipeline_bridge_score=pipeline_score,
        critical_boundary_failures=sorted(critical_failures),
        propagation_notes=[
            "Boundary checks are static compile-time compatibility checks.",
            "Pipeline bridge score is a monotone product of per-edge scores.",
            "Unknown runtime semantics remain explicit and are not assumed safe.",
        ],
    )
    return AgentBoundaryResult(summary=summary, issues=issues)


def boundary_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "edge_summaries": list(ir.module.agent_boundary_summary.get("edge_summaries", [])),
        "pipeline_bridge_score": float(ir.module.agent_boundary_summary.get("pipeline_bridge_score", 1.0)),
        "critical_boundary_failures": list(ir.module.agent_boundary_summary.get("critical_boundary_failures", [])),
        "aggregation_rule": str(ir.module.agent_boundary_summary.get("aggregation_rule", "")),
        "propagation_notes": list(ir.module.agent_boundary_summary.get("propagation_notes", [])),
        "issues": list(ir.module.agent_boundary_issues),
    }


def boundary_issues_to_obligation_rows(issues: list[AgentBoundaryIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "agent_boundary",
                "description": issue.message,
                "source_location": issue.edge,
                "status": "violated" if issue.severity in {"critical", "high"} else "unknown",
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[AgentBoundaryIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
