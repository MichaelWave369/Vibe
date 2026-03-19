"""Recursive delegation attribution and proof inheritance checks (Phase 5.3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .ir import IR

ALLOWED_INHERITS = {"preserve", "constraint", "bridge"}


@dataclass(slots=True)
class DelegationIssue:
    issue_id: str
    severity: str
    category: str
    message: str
    edge: str
    evidence: str | None = None


@dataclass(slots=True)
class DelegationSummary:
    delegation_tree: list[dict[str, object]] = field(default_factory=list)
    inherited_contract_summary: list[dict[str, object]] = field(default_factory=list)
    recursion_metadata: dict[str, object] = field(default_factory=dict)
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DelegationResult:
    summary: DelegationSummary
    issues: list[DelegationIssue] = field(default_factory=list)


def _parse_numeric_threshold(rule: str) -> tuple[str, float] | None:
    raw = rule.strip().lower()
    for marker in ("measurement_safe_ratio", "epsilon_floor"):
        if marker in raw and "=" in raw:
            try:
                return marker, float(raw.split("=", 1)[1].strip())
            except Exception:
                return None
    return None


def annotate_delegation(ir: IR) -> DelegationResult:
    graph_nodes = dict(ir.module.agent_graph_summary.get("agents", {}))
    decls = list(ir.module.delegation_tree.get("edges", []))
    bridge_cfg = ir.bridge_config
    parent_threshold = float(bridge_cfg.get("measurement_safe_ratio", "0.85"))
    preserve_rules = [f"{k} {op} {v}" for k, op, v in ir.preserve_rules]
    constraints = list(ir.constraints)

    tree_rows: list[dict[str, object]] = []
    inherited_rows: list[dict[str, object]] = []
    issues: list[DelegationIssue] = []

    adjacency: dict[str, list[str]] = {}
    for d in decls:
        parent = str(d.get("parent", ""))
        child = str(d.get("child", ""))
        edge = f"{parent}->{child}"
        inherits = [str(x).strip() for x in d.get("inherits", ["preserve", "constraint", "bridge"])]
        max_depth = d.get("max_depth")
        stop_when = d.get("stop_when")
        adjacency.setdefault(parent, []).append(child)

        invalid = sorted([x for x in inherits if x not in ALLOWED_INHERITS])
        if invalid:
            issues.append(
                DelegationIssue(
                    issue_id=f"delegation.invalid_inherits.{parent}.{child}",
                    severity="high",
                    category="invalid_inheritance_policy",
                    message="delegation inherits policy includes unsupported entries",
                    edge=edge,
                    evidence=str(invalid),
                )
            )

        if parent not in graph_nodes or child not in graph_nodes:
            issues.append(
                DelegationIssue(
                    issue_id=f"delegation.missing_agent.{parent}.{child}",
                    severity="critical",
                    category="missing_parent_or_child",
                    message="delegation references undeclared parent/child agent",
                    edge=edge,
                    evidence=f"known={sorted(graph_nodes.keys())}",
                )
            )

        parent_node = graph_nodes.get(parent, {})
        child_node = graph_nodes.get(child, {})
        parent_preserve = list(parent_node.get("preserve", []))
        child_preserve = list(child_node.get("preserve", []))
        parent_constraints = list(parent_node.get("constraints", []))
        child_constraints = list(child_node.get("constraints", []))

        inherited_preserve = parent_preserve if "preserve" in inherits else []
        inherited_constraints = parent_constraints if "constraint" in inherits else []
        inherited_bridge = dict(bridge_cfg) if "bridge" in inherits else {}

        effective_preserve = sorted(set(child_preserve) | set(inherited_preserve))
        effective_constraints = sorted(set(child_constraints) | set(inherited_constraints))
        effective_bridge = dict(inherited_bridge)

        child_lower = " ".join(child_preserve + child_constraints).lower()
        if "deterministic" in " ".join(parent_constraints + parent_preserve).lower() and "deterministic" not in child_lower:
            issues.append(
                DelegationIssue(
                    issue_id=f"delegation.semantic_loss.{parent}.{child}",
                    severity="high",
                    category="inherited_qualifier_loss",
                    message="child appears to drop deterministic requirement inherited from parent",
                    edge=edge,
                    evidence=f"parent={parent_constraints + parent_preserve}, child={child_constraints + child_preserve}",
                )
            )
        if "sovereignty" in " ".join(parent_preserve).lower() and "sovereignty" not in " ".join(effective_preserve).lower():
            issues.append(
                DelegationIssue(
                    issue_id=f"delegation.sovereignty_loss.{parent}.{child}",
                    severity="critical",
                    category="contract_weakening",
                    message="child delegation weakens inherited sovereignty-preserving contract",
                    edge=edge,
                    evidence=f"parent_preserve={parent_preserve}, effective_child={effective_preserve}",
                )
            )

        child_threshold = parent_threshold
        for r in child_preserve:
            parsed = _parse_numeric_threshold(r)
            if parsed and parsed[0] == "measurement_safe_ratio":
                child_threshold = parsed[1]
        if child_threshold < parent_threshold:
            issues.append(
                DelegationIssue(
                    issue_id=f"delegation.threshold_weaken.{parent}.{child}",
                    severity="critical",
                    category="contract_weakening",
                    message="child delegation weakens inherited measurement_safe_ratio threshold",
                    edge=edge,
                    evidence=f"parent={parent_threshold}, child={child_threshold}",
                )
            )

        tree_rows.append(
            {
                "edge": edge,
                "inherits": inherits,
                "max_depth": max_depth,
                "stop_when": stop_when,
            }
        )
        inherited_rows.append(
            {
                "edge": edge,
                "inherited_preserve": inherited_preserve,
                "inherited_constraints": inherited_constraints,
                "inherited_bridge": effective_bridge,
                "effective_child_preserve": effective_preserve,
                "effective_child_constraints": effective_constraints,
            }
        )

    has_cycle = False
    seen: set[str] = set()
    visiting: set[str] = set()

    def _dfs(node: str) -> bool:
        visiting.add(node)
        for nxt in adjacency.get(node, []):
            if nxt in visiting:
                return True
            if nxt not in seen and _dfs(nxt):
                return True
        visiting.remove(node)
        seen.add(node)
        return False

    for root in sorted(adjacency.keys()):
        if root not in seen and _dfs(root):
            has_cycle = True
            break

    missing_stop_edges = [row["edge"] for row in tree_rows if row.get("max_depth") is None and not row.get("stop_when")]
    if missing_stop_edges:
        issues.append(
            DelegationIssue(
                issue_id="delegation.recursion.missing_stop",
                severity="high",
                category="recursion_stop_missing",
                message="delegation chain has unbounded edges without max_depth/stop_when",
                edge=",".join(sorted(missing_stop_edges)),
                evidence=str(sorted(missing_stop_edges)),
            )
        )
    if has_cycle and not any(row.get("stop_when") for row in tree_rows):
        issues.append(
            DelegationIssue(
                issue_id="delegation.cycle.without_stop",
                severity="critical",
                category="cycle_risk",
                message="delegation cycle detected without explicit stop proof",
                edge="delegation_tree",
                evidence=str(tree_rows),
            )
        )

    summary = DelegationSummary(
        delegation_tree=tree_rows,
        inherited_contract_summary=inherited_rows,
        recursion_metadata={
            "edge_count": len(tree_rows),
            "has_cycle": has_cycle,
            "missing_stop_edges": sorted(missing_stop_edges),
        },
        propagation_notes=[
            "Child agents inherit preserve/constraint/bridge contracts by default.",
            "Children may strengthen inherited contracts but cannot weaken critical thresholds.",
            "Recursive delegation remains statically checked in this phase (no runtime execution proof).",
        ],
    )
    return DelegationResult(summary=summary, issues=issues)


def delegation_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "delegation_tree": list(ir.module.delegation_summary.get("delegation_tree", [])),
        "inherited_contract_summary": list(ir.module.delegation_summary.get("inherited_contract_summary", [])),
        "recursion_metadata": dict(ir.module.delegation_summary.get("recursion_metadata", {})),
        "propagation_notes": list(ir.module.delegation_summary.get("propagation_notes", [])),
        "issues": list(ir.module.delegation_issues),
    }


def delegation_issues_to_obligation_rows(issues: list[DelegationIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "delegation",
                "description": issue.message,
                "source_location": issue.edge,
                "status": "violated" if issue.severity in {"critical", "high"} else "unknown",
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[DelegationIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
