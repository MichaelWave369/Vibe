"""Semantic type attribution and first-pass qualifier checking (Phase 4.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re

from .ir import IR


QUALIFIERS = {
    "deterministic",
    "secret_sensitive",
    "latency_bounded",
    "fallback_required",
    "coherence_preserving",
    "sovereignty_preserving",
    "bridge_critical",
    "intent_derived",
}


@dataclass(slots=True)
class SemanticTypeIssue:
    issue_id: str
    severity: str
    qualifier: str
    message: str
    binding: str | None = None
    value_id: str | None = None
    evidence: str | None = None


@dataclass(slots=True)
class SemanticTypeSummary:
    qualifier_counts: dict[str, int] = field(default_factory=dict)
    binding_qualifiers: dict[str, list[str]] = field(default_factory=dict)
    propagation_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SemanticTypingResult:
    summary: SemanticTypeSummary
    issues: list[SemanticTypeIssue] = field(default_factory=list)


def _binding_map(ir: IR) -> dict[str, str]:
    return {b.name: b.value_id for b in ir.module.bindings}


def _add_qual(ir: IR, value_id: str, qualifier: str) -> None:
    if qualifier not in QUALIFIERS:
        return
    cur = ir.module.values[value_id].semantic_qualifiers
    if qualifier not in cur:
        cur.append(qualifier)
        cur.sort()


def annotate_semantic_types(ir: IR) -> SemanticTypingResult:
    bindings = _binding_map(ir)
    input_refs = [vid for name, vid in bindings.items() if name.startswith("intent.input.")]
    output_refs = [vid for name, vid in bindings.items() if name.startswith("intent.output.")]

    for vid in input_refs + output_refs:
        _add_qual(ir, vid, "intent_derived")

    lower_constraints = [c.lower() for c in ir.constraints]
    if any("deterministic" in c for c in lower_constraints):
        for vid in output_refs:
            _add_qual(ir, vid, "deterministic")
    if any("no hardcoded secrets" in c for c in lower_constraints):
        for vid in input_refs:
            _add_qual(ir, vid, "secret_sensitive")
    if any("fallback" in c for c in lower_constraints):
        for vid in output_refs:
            _add_qual(ir, vid, "fallback_required")

    for key, _, value in ir.preserve_rules:
        k = key.lower().strip()
        v = value.lower().strip()
        if "latency" in k:
            for vid in output_refs:
                _add_qual(ir, vid, "latency_bounded")
        if "coherence" in k:
            for vid in output_refs:
                _add_qual(ir, vid, "coherence_preserving")
        if "sovereignty" in k and v in {"true", "1", "yes", "strict"}:
            for vid in output_refs:
                _add_qual(ir, vid, "sovereignty_preserving")
                _add_qual(ir, vid, "bridge_critical")

    if str(ir.bridge_config.get("mode", "")).lower() == "strict":
        for vid in output_refs:
            _add_qual(ir, vid, "bridge_critical")

    if ir.tesla_victory_layer:
        for vid in output_refs:
            _add_qual(ir, vid, "coherence_preserving")
        if bool(ir.arc_tower_policy.get("preserve_sovereignty", False)):
            for vid in output_refs:
                _add_qual(ir, vid, "sovereignty_preserving")

    if ir.agentception_config.get("inherit_constraints") or ir.agentception_config.get("inherit_preserve"):
        for vid in output_refs:
            _add_qual(ir, vid, "coherence_preserving")

    counts = {q: 0 for q in sorted(QUALIFIERS)}
    binding_quals: dict[str, list[str]] = {}
    for name, vid in sorted(bindings.items()):
        quals = sorted(ir.module.values[vid].semantic_qualifiers)
        binding_quals[name] = quals
        for q in quals:
            counts[q] += 1

    notes = [
        "Semantic qualifiers are first-pass heuristics, not full theorem proof.",
        "Qualifiers complement obligations and bridge checks; they do not replace them.",
    ]
    return SemanticTypingResult(
        summary=SemanticTypeSummary(qualifier_counts=counts, binding_qualifiers=binding_quals, propagation_notes=notes),
        issues=[],
    )


def check_semantic_type_issues(ir: IR, generated_code: str) -> list[SemanticTypeIssue]:
    issues: list[SemanticTypeIssue] = []
    lower = generated_code.lower()
    bindings = _binding_map(ir)

    for name, vid in sorted(bindings.items()):
        quals = set(ir.module.values[vid].semantic_qualifiers)
        if "secret_sensitive" in quals and re.search(r"secret\s*=|token\s*=|password\s*=", lower):
            issues.append(
                SemanticTypeIssue(
                    issue_id=f"semantic.secret.{name}",
                    severity="critical",
                    qualifier="secret_sensitive",
                    binding=name,
                    value_id=vid,
                    message="secret_sensitive semantic value appears to flow into hardcoded secret-like literal",
                    evidence="secret/token/password assignment detected",
                )
            )
        if "deterministic" in quals and re.search(r"random\(|uuid|time\.time\(|date\.now\(", lower):
            issues.append(
                SemanticTypeIssue(
                    issue_id=f"semantic.deterministic.{name}",
                    severity="critical",
                    qualifier="deterministic",
                    binding=name,
                    value_id=vid,
                    message="deterministic semantic value appears to use non-deterministic helper",
                    evidence="random/time/uuid marker detected",
                )
            )
        if "sovereignty_preserving" in quals and "http://" in lower:
            issues.append(
                SemanticTypeIssue(
                    issue_id=f"semantic.sovereignty.{name}",
                    severity="high",
                    qualifier="sovereignty_preserving",
                    binding=name,
                    value_id=vid,
                    message="sovereignty-preserving semantic value appears to use non-secure external endpoint",
                    evidence="http:// marker detected",
                )
            )
        if "bridge_critical" in quals and "semantic_qualifiers" not in lower:
            issues.append(
                SemanticTypeIssue(
                    issue_id=f"semantic.bridge_critical.{name}",
                    severity="medium",
                    qualifier="bridge_critical",
                    binding=name,
                    value_id=vid,
                    message="bridge-critical qualifier is not reflected in emitted semantic metadata",
                    evidence="SEMANTIC_QUALIFIERS metadata marker missing",
                )
            )
    return issues


def semantic_summary_payload(ir: IR) -> dict[str, object]:
    return {
        "qualifier_counts": dict(ir.module.semantic_summary.get("qualifier_counts", {})),
        "binding_qualifiers": dict(ir.module.semantic_summary.get("binding_qualifiers", {})),
        "propagation_notes": list(ir.module.semantic_summary.get("propagation_notes", [])),
        "issues": list(ir.module.semantic_issues),
    }


def issues_to_obligation_rows(issues: list[SemanticTypeIssue]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for issue in issues:
        status = "violated" if issue.severity in {"critical", "high"} else "unknown"
        rows.append(
            {
                "obligation_id": issue.issue_id,
                "category": "semantic_type",
                "description": issue.message,
                "source_location": issue.binding,
                "status": status,
                "evidence": issue.evidence,
                "critical": issue.severity in {"critical", "high"},
            }
        )
    return rows


def issues_as_dicts(issues: list[SemanticTypeIssue]) -> list[dict[str, object]]:
    return [asdict(i) for i in issues]
