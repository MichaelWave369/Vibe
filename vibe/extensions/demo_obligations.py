"""Example external obligation provider for Phase 4A registry seam."""

from __future__ import annotations

from ..obligation_registry import (
    ExternalObligation,
    ExternalObligationContext,
    register_external_obligation_provider,
)

DEMO_OBLIGATION_CATEGORY = "demo.audit"
DEMO_PROVIDER_NAME = "demo_audit_obligation_provider"
DEMO_PROVIDER_VERSION = "v1"


def _requires_audit_log(ir_constraints: list[str]) -> bool:
    normalized = [c.strip().lower().replace(" ", "") for c in ir_constraints]
    return "demo.require_audit_log=true" in normalized or "demo.require_audit_log:true" in normalized


def demo_audit_obligation_provider(context: ExternalObligationContext) -> list[ExternalObligation]:
    if not _requires_audit_log(context.ir.constraints):
        return []
    has_audit_marker = "audit" in context.generated_code.lower()
    return [
        ExternalObligation(
            obligation_id="external.demo.audit_log_present",
            category=DEMO_OBLIGATION_CATEGORY,
            description="Demo external obligation: generated code should expose an audit marker when requested",
            source_location="constraint:demo.require_audit_log",
            status="satisfied" if has_audit_marker else "violated",
            evidence="substring `audit` found in generated code" if has_audit_marker else "substring `audit` not found in generated code",
            critical=False,
        )
    ]


def register_demo_obligation_provider(*, override: bool = False) -> None:
    register_external_obligation_provider(
        DEMO_OBLIGATION_CATEGORY,
        demo_audit_obligation_provider,
        override=override,
        provider_name=DEMO_PROVIDER_NAME,
        provider_version=DEMO_PROVIDER_VERSION,
    )
