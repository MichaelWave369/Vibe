"""Bridge report rendering utilities."""

from __future__ import annotations

from .verifier import VerificationResult


def render_report(result: VerificationResult) -> str:
    """Render a detailed bridge report."""

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
        f"verdict: {result.verdict}",
        f"pass: {result.passed}",
    ]
    return "\n".join(lines)
