"""Agent graph attribution and validation (Phase 5.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .ir import IR


@dataclass(slots=True)
class AgentGraphIssue:
    issue_id: str
    severity: str
    category: str
    message: str
    source_location: str | None = None
    evidence: str | None = None


@dataclass(slots=True)
class AgentGraphSummary:
    graph_name: str = ""
    agent_count: int = 0
    edge_count: int = 0
    agents: dict[str, dict[str, object]] = field(default_factory=dict)
    edges: list[dict[str, str]] = field(default_factory=list)
    fallback_routes: list[str] = field(default_factory=list)
    disconnected_agents: list[str] = field(default_factory=list)
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentGraphResult:
    summary: AgentGraphSummary
    issues: list[AgentGraphIssue] = field(default_factory=list)


def annotate_agent_graph(ir: IR) -> AgentGraphResult:
    graph = ir.agent_graph
    agents = graph.get("agents", [])
    orchestration = graph.get("orchestrations", [])
    orch = orchestration[0] if orchestration else {"name": "", "edges": [], "on_error": None}
    edges = list(orch.get("edges", []))
    edge_rows = [{"source": str(e.get("source", "")), "target": str(e.get("target", ""))} for e in edges]

    nodes: dict[str, dict[str, object]] = {}
    for row in agents:
        name = str(row.get("name", ""))
        nodes[name] = {
            "role": str(row.get("role", "")),
            "receives": str(row.get("receives", "")),
            "emits": str(row.get("emits", "")),
            "preserve": list(row.get("preserve", [])),
            "constraints": list(row.get("constraints", [])),
        }

    connected: set[str] = set()
    for e in edge_rows:
        if e["source"]:
            connected.add(e["source"])
        if e["target"]:
            connected.add(e["target"])
    disconnected = sorted([name for name in nodes if name not in connected and edge_rows])

    summary = AgentGraphSummary(
        graph_name=str(orch.get("name", "")),
        agent_count=len(nodes),
        edge_count=len(edge_rows),
        agents=nodes,
        edges=edge_rows,
        fallback_routes=[str(orch.get("on_error"))] if orch.get("on_error") else [],
        disconnected_agents=disconnected,
        propagation_notes=[
            "Agent graphs are statically modeled and bridge-gated in this phase.",
            "Runtime orchestration autonomy is intentionally out of scope.",
        ],
    )
    return AgentGraphResult(summary=summary, issues=[])


def _extract_fallback_target(route: str | None) -> str | None:
    if not route:
        return None
    route = route.strip()
    if route.startswith("fallback(") and route.endswith(")"):
        return route[len("fallback(") : -1].strip()
    return None


def check_agent_graph_issues(ir: IR) -> list[AgentGraphIssue]:
    summary = ir.module.agent_graph_summary
    nodes = dict(summary.get("agents", {}))
    edges = list(summary.get("edges", []))
    fallback_routes = list(summary.get("fallback_routes", []))
    issues: list[AgentGraphIssue] = []

    if not nodes and not edges:
        return issues

    known = set(nodes.keys())
    indegree: dict[str, int] = {k: 0 for k in known}
    outdegree: dict[str, int] = {k: 0 for k in known}

    for e in edges:
        src = str(e.get("source", ""))
        dst = str(e.get("target", ""))
        if src not in known or dst not in known:
            issues.append(
                AgentGraphIssue(
                    issue_id=f"agent_graph.edge.invalid.{src}.{dst}",
                    severity="high",
                    category="orchestration_integrity",
                    message="orchestration edge references missing agent",
                    source_location=src or dst,
                    evidence=f"edge={src}->{dst}, known={sorted(known)}",
                )
            )
            continue
        outdegree[src] += 1
        indegree[dst] += 1

        src_emits = str(nodes[src].get("emits", ""))
        dst_receives = str(nodes[dst].get("receives", ""))
        if src_emits and dst_receives and src_emits != dst_receives:
            issues.append(
                AgentGraphIssue(
                    issue_id=f"agent_graph.boundary.mismatch.{src}.{dst}",
                    severity="high",
                    category="boundary_type_mismatch",
                    message="agent emits/receives contract mismatch across orchestration edge",
                    source_location=f"{src}->{dst}",
                    evidence=f"{src}.emits={src_emits}, {dst}.receives={dst_receives}",
                )
            )

        src_preserve = set(nodes[src].get("preserve", []))
        dst_preserve = set(nodes[dst].get("preserve", []))
        lost = sorted(src_preserve - dst_preserve)
        if lost:
            issues.append(
                AgentGraphIssue(
                    issue_id=f"agent_graph.contract.loss.{src}.{dst}",
                    severity="medium",
                    category="contract_loss",
                    message="upstream preserve contract not reflected downstream across graph edge",
                    source_location=f"{src}->{dst}",
                    evidence=f"lost={lost}",
                )
            )

    if edges:
        disconnected = sorted([n for n in known if indegree[n] == 0 and outdegree[n] == 0])
        for name in disconnected:
            issues.append(
                AgentGraphIssue(
                    issue_id=f"agent_graph.disconnected.{name}",
                    severity="medium",
                    category="orchestration_integrity",
                    message="agent is disconnected from orchestration graph",
                    source_location=name,
                    evidence="no incoming or outgoing edges",
                )
            )

    for route in fallback_routes:
        target = _extract_fallback_target(route)
        if target is None:
            issues.append(
                AgentGraphIssue(
                    issue_id="agent_graph.fallback.malformed",
                    severity="high",
                    category="fallback_route",
                    message="on_error route is malformed; expected fallback(TargetAgent)",
                    source_location="orchestrate.on_error",
                    evidence=route,
                )
            )
            continue
        if target not in known:
            issues.append(
                AgentGraphIssue(
                    issue_id=f"agent_graph.fallback.invalid.{target}",
                    severity="high",
                    category="fallback_route",
                    message="fallback target does not reference a declared agent",
                    source_location="orchestrate.on_error",
                    evidence=f"target={target}, known={sorted(known)}",
                )
            )

    visiting: set[str] = set()
    visited: set[str] = set()
    adjacency: dict[str, list[str]] = {k: [] for k in known}
    for e in edges:
        src = str(e.get("source", ""))
        dst = str(e.get("target", ""))
        if src in adjacency:
            adjacency[src].append(dst)

    def _dfs(node: str) -> bool:
        visiting.add(node)
        for nxt in adjacency.get(node, []):
            if nxt in visiting:
                return True
            if nxt not in visited and _dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    if any(_dfs(n) for n in sorted(known) if n not in visited):
        issues.append(
            AgentGraphIssue(
                issue_id="agent_graph.cycle.detected",
                severity="medium",
                category="orchestration_integrity",
                message="cycle detected in agent graph; runtime recursion semantics are unresolved in this phase",
                source_location="orchestrate",
                evidence=str(edges),
            )
        )

    return issues


def agent_graph_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "graph_name": str(ir.module.agent_graph_summary.get("graph_name", "")),
        "agent_count": int(ir.module.agent_graph_summary.get("agent_count", 0)),
        "edge_count": int(ir.module.agent_graph_summary.get("edge_count", 0)),
        "agents": dict(ir.module.agent_graph_summary.get("agents", {})),
        "edges": list(ir.module.agent_graph_summary.get("edges", [])),
        "fallback_routes": list(ir.module.agent_graph_summary.get("fallback_routes", [])),
        "disconnected_agents": list(ir.module.agent_graph_summary.get("disconnected_agents", [])),
        "propagation_notes": list(ir.module.agent_graph_summary.get("propagation_notes", [])),
        "issues": list(ir.module.agent_graph_issues),
    }


def agent_graph_issues_to_obligation_rows(issues: list[AgentGraphIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "agent_graph",
                "description": issue.message,
                "source_location": issue.source_location,
                "status": "violated" if issue.severity in {"critical", "high"} else "unknown",
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[AgentGraphIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
