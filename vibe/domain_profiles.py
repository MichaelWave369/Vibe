"""Phase 7A: shared cross-domain intent architecture profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Callable

from .ir import IR


DomainObligationFactory = Callable[[IR], list[dict[str, object]]]


@dataclass(slots=True)
class DomainProfile:
    name: str
    preserve_families: list[str]
    constraint_families: list[str]
    supported_emit_targets: list[str]
    proof_extensions: dict[str, object] = field(default_factory=dict)
    report_extensions: dict[str, object] = field(default_factory=dict)
    compatibility_hooks: list[str] = field(default_factory=list)
    obligation_factory: DomainObligationFactory | None = None



def _prefix_obligations(domain: str, prefixes: list[str], *, family: str) -> DomainObligationFactory:
    def _factory(ir: IR) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        if family == "preserve":
            keys = [k for k, _, _ in ir.preserve_rules]
        else:
            keys = [c.lower() for c in ir.constraints]
        for key in keys:
            key_norm = key.lower()
            allowed = any(key_norm.startswith(p.lower()) for p in prefixes)
            rows.append(
                {
                    "obligation_id": f"domain.{domain}.{family}.{key_norm.replace(' ', '_')}",
                    "category": "domain",
                    "description": f"{domain} {family} family check for `{key}`",
                    "source_location": None,
                    "status": "satisfied" if allowed else "unknown",
                    "evidence": "family matched profile" if allowed else "no matching family prefix in active domain profile",
                    "critical": False,
                }
            )
        return sorted(rows, key=lambda r: str(r["obligation_id"]))

    return _factory


DOMAIN_PROFILES: dict[str, DomainProfile] = {
    "hardware": DomainProfile(
        name="hardware",
        preserve_families=["timing", "latency", "power", "clock", "reset", "safety"],
        constraint_families=["no_x", "synth", "cdc", "rtl", "formal"],
        supported_emit_targets=["vhdl", "systemverilog", "python"],
        proof_extensions={"timing_model": "logical", "clock_domains": "declared"},
        report_extensions={"domain_track": "7.1 hardware intent"},
        compatibility_hooks=["timing_budget", "clock_domain_consistency"],
        obligation_factory=_prefix_obligations("hardware", ["timing", "latency", "power", "clock", "reset"], family="preserve"),
    ),
    "scientific_simulation": DomainProfile(
        name="scientific_simulation",
        preserve_families=["stability", "convergence", "precision", "reproducibility"],
        constraint_families=["units", "boundary", "solver", "deterministic_seed"],
        supported_emit_targets=["julia", "python"],
        proof_extensions={"numerics": "tracked", "solver_assumptions": "explicit"},
        report_extensions={"domain_track": "7.2 scientific simulation intent"},
        compatibility_hooks=["solver_family", "numerical_stability"],
        obligation_factory=_prefix_obligations("scientific_simulation", ["stability", "convergence", "precision", "reproducibility"], family="preserve"),
    ),
    "legal_compliance": DomainProfile(
        name="legal_compliance",
        preserve_families=["retention", "audit", "consent", "jurisdiction", "traceability"],
        constraint_families=["gdpr", "hipaa", "sox", "policy", "disclosure"],
        supported_emit_targets=["compliance_report", "python"],
        proof_extensions={"policy_bindings": "declared", "evidence_chain": "required"},
        report_extensions={"domain_track": "7.3 legal/compliance intent"},
        compatibility_hooks=["policy_version", "jurisdiction_overlap"],
        obligation_factory=_prefix_obligations("legal_compliance", ["retention", "audit", "consent", "jurisdiction", "traceability"], family="preserve"),
    ),
    "genomics": DomainProfile(
        name="genomics",
        preserve_families=["coverage", "specificity", "sensitivity", "quality", "lineage"],
        constraint_families=["reference", "variant", "reproducibility", "pipeline"],
        supported_emit_targets=["snakemake", "nextflow", "python"],
        proof_extensions={"sample_provenance": "tracked", "reference_build": "declared"},
        report_extensions={"domain_track": "7.4 genomics intent"},
        compatibility_hooks=["reference_build", "pipeline_stage_alignment"],
        obligation_factory=_prefix_obligations("genomics", ["coverage", "specificity", "sensitivity", "quality", "lineage"], family="preserve"),
    ),
}



def list_domain_profiles() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for key in sorted(DOMAIN_PROFILES.keys()):
        payload = asdict(DOMAIN_PROFILES[key])
        payload.pop("obligation_factory", None)
        rows.append(payload)
    return rows



def resolve_domain_profile(name: str | None) -> DomainProfile | None:
    if not name:
        return None
    return DOMAIN_PROFILES.get(name.strip().lower())



def domain_summary_json() -> str:
    return json.dumps({"domains": list_domain_profiles()}, indent=2, sort_keys=True)



def apply_domain_profile(ir: IR, domain_name: str | None) -> None:
    profile = resolve_domain_profile(domain_name)
    issues: list[dict[str, object]] = []
    obligations: list[dict[str, object]] = []
    if profile is None:
        if domain_name:
            issues.append(
                {
                    "issue_id": f"domain.unknown.{domain_name}",
                    "severity": "medium",
                    "message": f"unknown domain profile `{domain_name}`",
                }
            )
        ir.module.active_domain_profile = domain_name or "general"
        ir.module.domain_summary = {
            "profile": ir.module.active_domain_profile,
            "supported_emit_targets": [ir.emit_target],
            "note": "no domain profile selected; general compiler mode",
        }
        ir.module.domain_issues = issues
        ir.module.domain_obligations = obligations
        ir.module.domain_target_metadata = {
            "planned_target": ir.emit_target,
            "target_supported_by_profile": True,
            "scaffold_only": False,
        }
        return

    if profile.obligation_factory is not None:
        obligations = profile.obligation_factory(ir)
    if ir.emit_target not in set(profile.supported_emit_targets):
        issues.append(
            {
                "issue_id": f"domain.emit.unsupported.{profile.name}.{ir.emit_target}",
                "severity": "high",
                "message": f"emit target `{ir.emit_target}` is not declared in domain `{profile.name}` profile",
            }
        )
    ir.module.active_domain_profile = profile.name
    ir.module.domain_summary = {
        "profile": profile.name,
        "preserve_families": profile.preserve_families,
        "constraint_families": profile.constraint_families,
        "supported_emit_targets": profile.supported_emit_targets,
        "report_extensions": profile.report_extensions,
        "proof_extensions": profile.proof_extensions,
    }
    ir.module.domain_issues = sorted(issues, key=lambda x: str(x.get("issue_id", "")))
    ir.module.domain_obligations = obligations
    ir.module.domain_target_metadata = {
        "planned_target": ir.emit_target,
        "target_supported_by_profile": ir.emit_target in set(profile.supported_emit_targets),
        "scaffold_only": ir.emit_target in {"vhdl", "systemverilog", "julia", "compliance_report", "snakemake", "nextflow"},
    }
