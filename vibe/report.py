"""Bridge report rendering utilities."""

from __future__ import annotations

import json
from dataclasses import asdict

from .verifier import VerificationResult


def report_dict(result: VerificationResult) -> dict[str, object]:
    """Return a JSON-serializable bridge report payload."""

    return asdict(result)


def render_report(result: VerificationResult, show_obligations: bool = True) -> str:
    """Render a detailed human-readable bridge report."""

    lines = [
        "=== Vibe Bridge Report ===",
        f"eps_pre: {result.epsilon_pre:.4f}",
        f"eps_post: {result.epsilon_post:.4f}",
        f"M_eps: {result.measurement_ratio:.4f}",
        f"C_bar: {result.c_bar:.4f}",
        "qixel metrics:",
        f"  q_persistence: {result.q_persistence:.4f}",
        f"  q_spatial_consistency: {result.q_spatial_consistency:.4f}",
        f"  q_cohesion: {result.q_cohesion:.4f}",
        f"  q_alignment: {result.q_alignment:.4f}",
        f"  q_intent_constant: {result.q_intent_constant:.4f}",
        f"petra_alignment: {result.petra_alignment:.4f}",
        f"multimodal_resonance: {result.multimodal_resonance:.4f}",
        f"bridge_score: {result.bridge_score:.4f}",
    ]
    if result.tesla_enabled:
        lines.extend(
            [
                "tesla:",
                f"  tesla_enabled: {result.tesla_enabled}",
                f"  substrate_bridge: {result.substrate_bridge}",
                f"  baseline_frequency_hz: {result.baseline_frequency_hz}",
                f"  harmonic_mode: {result.harmonic_mode}",
                f"  breath_monitor: {result.breath_monitor}",
                f"  sovereignty_preserved: {result.sovereignty_preserved}",
            ]
        )
    if result.agent_count:
        lines.extend(
            [
                "agent metrics:",
                f"  agent_count: {result.agent_count}",
                f"  spawn_depth: {result.spawn_depth}",
                f"  child_alignment: {result.child_alignment:.4f}",
                f"  delegation_integrity: {result.delegation_integrity:.4f}",
                f"  merge_preservation: {result.merge_preservation:.4f}",
                f"  agent_bridge_score: {result.agent_bridge_score:.4f}",
            ]
        )

    lines.append("obligations:")
    lines.append(f"  counts: {result.obligation_counts}")
    if show_obligations:
        for o in result.obligations:
            lines.append(f"  - [{o.status}] {o.obligation_id} ({o.category}) :: {o.description}")
            if o.evidence:
                lines.append(f"      evidence: {o.evidence}")

    lines.extend([f"verdict: {result.verdict}", f"pass: {result.passed}"])
    return "\n".join(lines)


def render_report_json(result: VerificationResult) -> str:
    """Render a deterministic JSON bridge report."""

    return json.dumps(report_dict(result), indent=2, sort_keys=True)
