"""Deterministic multi-candidate synthesis strategies (Phase 3.1)."""

from __future__ import annotations

from dataclasses import dataclass

from .emitter import emit_code
from .ir import IR
from .verifier import VerificationResult


@dataclass(slots=True)
class CandidateImplementation:
    candidate_id: str
    strategy: str
    target: str
    code: str


@dataclass(slots=True)
class CandidateEvaluation:
    candidate_id: str
    strategy: str
    result: VerificationResult
    rank_score: float


def _python_readability_variant(code: str) -> str:
    lines = code.splitlines()
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if line.startswith("def ") and not inserted:
            out.append("    # Synthesis strategy: readability-biased")
            inserted = True
    if not inserted:
        out.append("# Synthesis strategy: readability-biased")
    return "\n".join(out) + "\n"


def _python_minimal_variant(code: str) -> str:
    lines = [ln for ln in code.splitlines() if "TODO(" not in ln and "TODO:" not in ln]
    return "\n".join(lines) + "\n"


def _python_config_variant(code: str) -> str:
    return code + "SYNTHESIS_PROFILE = {'strategy': 'config-heavy', 'mode': 'deterministic'}\n"


def _ts_readability_variant(code: str) -> str:
    return "// Synthesis strategy: readability-biased\n" + code


def _ts_minimal_variant(code: str) -> str:
    lines = [ln for ln in code.splitlines() if "TODO(" not in ln and "TODO:" not in ln]
    return "\n".join(lines) + "\n"


def _ts_config_variant(code: str) -> str:
    return code + "export const SYNTHESIS_PROFILE = { strategy: 'config-heavy', mode: 'deterministic' } as const;\n"


def generate_candidates(ir: IR, candidate_count: int) -> list[CandidateImplementation]:
    base_code, backend = emit_code(ir)
    target = backend.target

    if target == "python":
        strategy_defs = [
            ("standard", lambda c: c),
            ("readability_biased", _python_readability_variant),
            ("minimal_helper_light", _python_minimal_variant),
            ("config_heavy", _python_config_variant),
        ]
    else:
        strategy_defs = [
            ("standard", lambda c: c),
            ("readability_biased", _ts_readability_variant),
            ("minimal_helper_light", _ts_minimal_variant),
            ("config_heavy", _ts_config_variant),
        ]

    candidates: list[CandidateImplementation] = []
    for idx in range(max(1, candidate_count)):
        strategy, fn = strategy_defs[idx % len(strategy_defs)]
        code = fn(base_code)
        candidates.append(
            CandidateImplementation(
                candidate_id=f"candidate.{idx + 1}",
                strategy=strategy,
                target=target,
                code=code,
            )
        )
    return candidates


def rank_candidate(candidate_id: str, strategy: str, result: VerificationResult) -> CandidateEvaluation:
    counts = result.obligation_counts
    violated = float(counts.get("violated", 0))
    unknown = float(counts.get("unknown", 0))
    score = (
        (1000.0 if result.passed else 0.0)
        + 100.0 * float(result.bridge_score)
        + 10.0 * float(result.measurement_ratio)
        + 5.0 * float(result.intent_equivalence_score)
        - 5.0 * float(result.drift_score)
        - 2.0 * violated
        - 0.5 * unknown
    )
    return CandidateEvaluation(candidate_id=candidate_id, strategy=strategy, result=result, rank_score=score)


def rank_candidates(evals: list[CandidateEvaluation]) -> list[CandidateEvaluation]:
    return sorted(
        evals,
        key=lambda e: (
            0 if e.result.passed else 1,
            -e.rank_score,
            e.candidate_id,
        ),
    )


def ranking_formula_description() -> str:
    return (
        "rank = pass_bonus(1000 if passed else 0) + 100*bridge_score + 10*measurement_ratio "
        "+ 5*intent_equivalence_score - 5*drift_score - 2*violated - 0.5*unknown"
    )
