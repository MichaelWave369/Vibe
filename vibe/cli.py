"""CLI entrypoint for vibec."""

from __future__ import annotations

import argparse
from pathlib import Path

from ._version import __version__
from .cache import (
    CacheRecord,
    clear_cache,
    load_cache_record,
    save_cache_record,
    sha256_text,
)
from .calibration import (
    fit_calibration_model,
    load_calibration_corpus,
    save_calibration_model,
)
from .emitter import emit_code, output_path_for
from .ir import ast_to_ir, serialize_ir
from .parser import parse_source
from .proof import (
    build_proof_artifact,
    default_proof_path,
    load_proof_artifact,
    render_proof_summary,
    write_proof_artifact,
)
from .report import render_report, render_report_json
from .synthesis import (
    generate_candidates,
    rank_candidate,
    rank_candidates,
    ranking_formula_description,
)
from .testgen import generate_intent_guided_tests
from .verifier import available_backends, verify


ReportMode = str


def _load(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return path.read_text(encoding="utf-8")


def _print_report(
    result,
    report: ReportMode,
    show_obligations: bool = True,
    show_equivalence: bool = False,
) -> None:
    if report == "json":
        print(render_report_json(result))
    else:
        print(render_report(result, show_obligations=show_obligations, show_equivalence=show_equivalence))


def _compile(
    path: Path,
    report: ReportMode,
    no_cache: bool = False,
    clean_cache: bool = False,
    show_obligations: bool = True,
    show_equivalence: bool = False,
    verification_backend: str = "heuristic",
    fallback_backend: str | None = None,
    use_calibration: bool = True,
    write_proof: bool = False,
    candidate_count: int = 3,
    with_tests: bool = False,
) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    ir_ser = serialize_ir(ir)
    source_hash = sha256_text(source)
    ir_hash = sha256_text(ir_ser)

    emitted_code, backend = emit_code(ir)
    out_path = output_path_for(path, backend)

    if clean_cache:
        clear_cache(path)

    if not no_cache and not with_tests:
        decision = load_cache_record(path)
        if decision.status == "cache_corrupt":
            print("cache: corrupt record detected, revalidating")
        elif decision.record is not None:
            rec = decision.record
            if (
                rec.source_hash == source_hash
                and rec.ir_hash == ir_hash
                and rec.target == backend.target
                and rec.compiler_version == __version__
                and rec.verification_passed
                and Path(rec.output_path).exists()
            ):
                print(f"cache: hit ({backend.target})")
                print(f"emitted: {out_path}")
                return 0
            print("cache: miss (metadata changed)")
        else:
            print("cache: miss")

    candidates = generate_candidates(ir, candidate_count)
    evaluations = [
        rank_candidate(
            c.candidate_id,
            c.strategy,
            verify(
                ir,
                c.code,
                backend=verification_backend,
                fallback_backend=fallback_backend,
                use_calibration=use_calibration,
            ),
        )
        for c in candidates
    ]
    ranked = rank_candidates(evaluations)
    winner = ranked[0]
    result = winner.result
    result.candidate_count = len(candidates)
    result.winning_candidate_id = winner.candidate_id
    result.synthesized_winner = len(candidates) > 1
    result.ranking_basis = ranking_formula_description()
    result.candidate_summaries = [
        {
            "candidate_id": e.candidate_id,
            "strategy": e.strategy,
            "passed": e.result.passed,
            "rank_score": round(e.rank_score, 6),
            "bridge_score": round(float(e.result.bridge_score), 6),
            "measurement_ratio": round(float(e.result.measurement_ratio), 6),
            "equivalence_score": round(float(e.result.intent_equivalence_score), 6),
            "drift_score": round(float(e.result.drift_score), 6),
        }
        for e in ranked
    ]
    winning_candidate = next(c for c in candidates if c.candidate_id == result.winning_candidate_id)
    generated_suite = None
    if with_tests:
        generated_suite = generate_intent_guided_tests(
            ir=ir,
            output_path=out_path,
            emitted_code=winning_candidate.code,
            candidate_id=winner.candidate_id,
        )
        result.test_generation_enabled = True
        result.generated_test_files = sorted(generated_suite.generated_files.keys())
        result.preserve_rule_coverage = list(generated_suite.preserve_rule_coverage)
        result.constraint_coverage = list(generated_suite.constraint_coverage)
        result.uncovered_items = list(generated_suite.uncovered_items)
        result.partial_coverage_items = list(generated_suite.partial_coverage_items)
        result.test_generation_notes = list(generated_suite.notes)
    _print_report(
        result,
        report,
        show_obligations=show_obligations,
        show_equivalence=show_equivalence,
    )

    proof_path = default_proof_path(path)
    if write_proof:
        proof = build_proof_artifact(
            path,
            source,
            ir,
            result,
            emitted_blocked=not result.passed,
            notes=["compile flow proof artifact"],
        )
        write_proof_artifact(proof_path, proof)
        print(f"proof: {proof_path}")

    if not result.passed:
        if result.backend_error:
            print(f"compile failed: {result.backend_error}")
        print("compile failed: bridge preservation threshold not met")
        if not no_cache:
            save_cache_record(
                path,
                CacheRecord(
                    source_path=str(path.resolve()),
                    source_hash=source_hash,
                    ir_hash=ir_hash,
                    target=backend.target,
                    compiler_version=__version__,
                    output_path=str(out_path.resolve()),
                    verification_passed=False,
                    bridge_score=float(result.bridge_score),
                ),
            )
        return 1

    out_path.write_text(winning_candidate.code, encoding="utf-8")
    print(f"emitted: {out_path}")
    if generated_suite is not None:
        for test_path, test_content in generated_suite.generated_files.items():
            tpath = Path(test_path)
            tpath.write_text(test_content, encoding="utf-8")
            print(f"emitted test: {tpath}")

    if not no_cache:
        save_cache_record(
            path,
            CacheRecord(
                source_path=str(path.resolve()),
                source_hash=source_hash,
                ir_hash=ir_hash,
                target=backend.target,
                compiler_version=__version__,
                output_path=str(out_path.resolve()),
                verification_passed=True,
                bridge_score=float(result.bridge_score),
            ),
        )

    return 0


def _explain(path: Path) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    emitted_code, _ = emit_code(ir)
    result = verify(ir, emitted_code)
    print("AST:")
    print(ast)
    print("\nNormalized IR:")
    print(serialize_ir(ir))
    print("\nPreservation reasoning:")
    print(render_report(result, show_obligations=True, show_equivalence=True))
    return 0


def _verify(
    path: Path,
    report: ReportMode,
    show_obligations: bool = True,
    show_equivalence: bool = False,
    verification_backend: str = "heuristic",
    fallback_backend: str | None = None,
    use_calibration: bool = True,
    write_proof: bool = False,
    candidate_count: int = 3,
    with_tests: bool = False,
) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    candidates = generate_candidates(ir, candidate_count)
    evaluations = [
        rank_candidate(
            c.candidate_id,
            c.strategy,
            verify(
                ir,
                c.code,
                backend=verification_backend,
                fallback_backend=fallback_backend,
                use_calibration=use_calibration,
            ),
        )
        for c in candidates
    ]
    ranked = rank_candidates(evaluations)
    winner = ranked[0]
    result = winner.result
    result.candidate_count = len(candidates)
    result.winning_candidate_id = winner.candidate_id
    result.synthesized_winner = len(candidates) > 1
    result.ranking_basis = ranking_formula_description()
    result.candidate_summaries = [
        {
            "candidate_id": e.candidate_id,
            "strategy": e.strategy,
            "passed": e.result.passed,
            "rank_score": round(e.rank_score, 6),
            "bridge_score": round(float(e.result.bridge_score), 6),
            "measurement_ratio": round(float(e.result.measurement_ratio), 6),
            "equivalence_score": round(float(e.result.intent_equivalence_score), 6),
            "drift_score": round(float(e.result.drift_score), 6),
        }
        for e in ranked
    ]
    if with_tests:
        emitted_code, backend = emit_code(ir)
        projected_path = output_path_for(path, backend)
        generated_suite = generate_intent_guided_tests(
            ir=ir,
            output_path=projected_path,
            emitted_code=emitted_code,
            candidate_id=winner.candidate_id,
        )
        result.test_generation_enabled = True
        result.generated_test_files = sorted(generated_suite.generated_files.keys())
        result.preserve_rule_coverage = list(generated_suite.preserve_rule_coverage)
        result.constraint_coverage = list(generated_suite.constraint_coverage)
        result.uncovered_items = list(generated_suite.uncovered_items)
        result.partial_coverage_items = list(generated_suite.partial_coverage_items)
        result.test_generation_notes = list(generated_suite.notes)
    _print_report(
        result,
        report,
        show_obligations=show_obligations,
        show_equivalence=show_equivalence,
    )
    if result.backend_error:
        print(f"verify failed: {result.backend_error}")
    if write_proof:
        proof_path = default_proof_path(path)
        proof = build_proof_artifact(
            path,
            source,
            ir,
            result,
            emitted_blocked=not result.passed,
            notes=["verify flow proof artifact"],
        )
        write_proof_artifact(proof_path, proof)
        print(f"proof: {proof_path}")
    return 0 if result.passed else 1


def _calibrate(corpus_path: Path) -> int:
    records = load_calibration_corpus(corpus_path)
    model = fit_calibration_model(records)
    artifact = save_calibration_model(model)
    print("=== Vibe Calibration Summary ===")
    print(f"corpus_records: {len(records)}")
    print(f"model_version: {model.model_version}")
    print(f"fit_confidence: {model.fit_confidence:.4f}")
    print(f"artifact: {artifact}")
    return 0


def _verify_proof(
    path: Path,
    report: ReportMode,
    verification_backend: str,
    fallback_backend: str | None,
    use_calibration: bool,
    candidate_count: int,
) -> int:
    rc = _verify(
        path,
        report,
        show_obligations=True,
        show_equivalence=True,
        verification_backend=verification_backend,
        fallback_backend=fallback_backend,
        use_calibration=use_calibration,
        write_proof=True,
        candidate_count=candidate_count,
    )
    return rc


def _inspect_proof(path: Path) -> int:
    try:
        payload = load_proof_artifact(path)
    except Exception as exc:
        print(f"inspect-proof failed: {exc}")
        return 1
    print(render_proof_summary(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibec", description="Vibe compiler prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    cp = sub.add_parser("compile", help="Compile a .vibe source file")
    cp.add_argument("path", type=Path)
    cp.add_argument("--report", choices=["human", "json"], default="human")
    cp.add_argument("--no-cache", action="store_true", help="Disable incremental cache for this compile")
    cp.add_argument("--clean-cache", action="store_true", help="Remove cache record before compiling")
    cp.add_argument("--show-obligations", action="store_true", help="Show full obligation list in human report")
    cp.add_argument("--show-equivalence", action="store_true", help="Show detailed equivalence/diff entries in human report")
    cp.add_argument("--backend", default="heuristic", help=f"Verification backend ({', '.join(available_backends())})")
    cp.add_argument("--fallback-backend", default=None, help="Optional fallback backend for unknown obligations")
    cp.add_argument("--no-calibration", action="store_true", help="Disable empirical epsilon calibration")
    cp.add_argument("--write-proof", action="store_true", help="Write deterministic preservation proof artifact")
    cp.add_argument("--candidates", type=int, default=3, help="Number of deterministic synthesis candidates")
    cp.add_argument("--with-tests", action="store_true", help="Emit intent-guided tests alongside compiled output")

    ex = sub.add_parser("explain", help="Explain AST and IR")
    ex.add_argument("path", type=Path)

    vf = sub.add_parser("verify", help="Run verifier without emission")
    vf.add_argument("path", type=Path)
    vf.add_argument("--report", choices=["human", "json"], default="human")
    vf.add_argument("--show-obligations", action="store_true", help="Show full obligation list in human report")
    vf.add_argument("--show-equivalence", action="store_true", help="Show detailed equivalence/diff entries in human report")
    vf.add_argument("--backend", default="heuristic", help=f"Verification backend ({', '.join(available_backends())})")
    vf.add_argument("--fallback-backend", default=None, help="Optional fallback backend for unknown obligations")
    vf.add_argument("--no-calibration", action="store_true", help="Disable empirical epsilon calibration")
    vf.add_argument("--write-proof", action="store_true", help="Write deterministic preservation proof artifact")
    vf.add_argument("--candidates", type=int, default=3, help="Number of deterministic synthesis candidates")
    vf.add_argument("--with-tests", action="store_true", help="Include intent-guided test metadata in verification report")

    cal = sub.add_parser("calibrate", help="Fit/update empirical epsilon calibration model")
    cal.add_argument("corpus_path", type=Path)

    vp = sub.add_parser("verify-proof", help="Verify and always write proof artifact")
    vp.add_argument("path", type=Path)
    vp.add_argument("--report", choices=["human", "json"], default="human")
    vp.add_argument("--backend", default="heuristic", help=f"Verification backend ({', '.join(available_backends())})")
    vp.add_argument("--fallback-backend", default=None, help="Optional fallback backend for unknown obligations")
    vp.add_argument("--no-calibration", action="store_true", help="Disable empirical epsilon calibration")
    vp.add_argument("--candidates", type=int, default=3, help="Number of deterministic synthesis candidates")

    ip = sub.add_parser("inspect-proof", help="Inspect a preservation proof artifact")
    ip.add_argument("path", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        return _compile(
            args.path,
            args.report,
            no_cache=args.no_cache,
            clean_cache=args.clean_cache,
            show_obligations=args.show_obligations,
            show_equivalence=args.show_equivalence,
            verification_backend=args.backend,
            fallback_backend=args.fallback_backend,
            use_calibration=not args.no_calibration,
            write_proof=args.write_proof,
            candidate_count=args.candidates,
            with_tests=args.with_tests,
        )
    if args.command == "explain":
        return _explain(args.path)
    if args.command == "verify":
        return _verify(
            args.path,
            args.report,
            show_obligations=args.show_obligations,
            show_equivalence=args.show_equivalence,
            verification_backend=args.backend,
            fallback_backend=args.fallback_backend,
            use_calibration=not args.no_calibration,
            write_proof=args.write_proof,
            candidate_count=args.candidates,
            with_tests=args.with_tests,
        )
    if args.command == "calibrate":
        return _calibrate(args.corpus_path)
    if args.command == "verify-proof":
        return _verify_proof(
            args.path,
            args.report,
            args.backend,
            args.fallback_backend,
            use_calibration=not args.no_calibration,
            candidate_count=args.candidates,
        )
    if args.command == "inspect-proof":
        return _inspect_proof(args.path)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
