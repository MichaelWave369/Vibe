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
from .ci import CICheckConfig, run_ci_check
from .diff import compute_intent_diff, render_intent_diff_human, render_intent_diff_json
from .domain_profiles import domain_summary_json
from .emitter import emit_code, output_path_for
from .ir import ast_to_ir, serialize_ir
from .parser import ParseError, parse_source
from .package_manager import (
    apply_package_defaults_to_source,
    build_project,
    package_context_for_path,
    package_summary_json,
    validate_manifest_and_graph,
)
from dataclasses import asdict
from .manifest import VibeManifest
from .lsp.server import run_stdio_server
from .interchange import (
    build_interchange_from_text,
    build_intent_brief,
    build_proof_brief,
    write_json_artifact,
)
from .negotiation import (
    negotiate_intents,
    render_negotiated_vibe,
    render_negotiation_human,
    render_negotiation_json,
    write_negotiation_artifact,
)
from .proof import (
    build_proof_artifact,
    default_proof_path,
    load_proof_artifact,
    render_proof_summary,
    write_proof_artifact,
)
from .registry import (
    compatibility_summary,
    inspect_registry_entry,
    publish_to_local_registry,
    search_local_registry,
)
from .self_hosting import SelfCheckConfig, run_self_check
from .semver import (
    current_version_from_manifest,
    derive_semver_from_diff,
    render_semver_human,
    render_semver_json,
    write_manifest_version,
)
from .runtime_monitor import evaluate_runtime_events, load_runtime_events
from .refinement import (
    RefinementIterationSummary,
    extract_counterexample,
    refine_candidates,
    strategy_adjustments,
    to_history_row,
)
from .report import render_report, render_report_json
from .verification_flow import prepare_verification_input
from .snapshot_store import SnapshotResolutionError, default_snapshot_store, resolve_snapshot, snapshot_put
from .merge_verify import (
    merge_verify_payload,
    merge_verify,
    maybe_write_merged,
    render_merge_verify_human,
    render_merge_verify_json,
    write_merge_report,
)
from .synthesis import (
    generate_candidates,
    rank_candidate,
    rank_candidates,
    ranking_formula_description,
)
from .testgen import generate_intent_guided_tests
from .verifier import available_backends, verify


ReportMode = str


def _non_negative_float(raw: str) -> float:
    value = float(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return value


def _print_report(
    result,
    report: ReportMode,
    show_obligations: bool = True,
    show_equivalence: bool = False,
    spec_path: str | None = "<unknown>",
    proof_artifact_path: str | None = None,
    input_mode: str = "path",
    snapshot_id: str | None = None,
    snapshot_store: str | None = None,
) -> None:
    if report == "json":
        print(
            render_report_json(
                result,
                spec_path=spec_path,
                proof_artifact_path=proof_artifact_path,
                input_mode=input_mode,
                snapshot_id=snapshot_id,
                snapshot_store=snapshot_store,
            )
        )
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
    refine: bool = False,
    max_iters: int = 3,
) -> int:
    prepared = prepare_verification_input(path=path)
    source = prepared.source_text
    ir = prepared.ir
    pkg_ctx = prepared.package_context
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
    max_iterations = max(1, max_iters if refine else 1)
    refinement_history: list[RefinementIterationSummary] = []
    refinement_failure_summary: list[str] = []
    selected_eval = None
    selected_candidate = None
    generated_suite = None

    for iteration in range(1, max_iterations + 1):
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
        passing = [e for e in ranked if e.result.passed]
        chosen = passing[0] if passing else ranked[0]
        chosen_candidate = next(c for c in candidates if c.candidate_id == chosen.candidate_id)

        suite_for_iteration = None
        if with_tests:
            suite_for_iteration = generate_intent_guided_tests(
                ir=ir,
                output_path=out_path,
                emitted_code=chosen_candidate.code,
                candidate_id=chosen.candidate_id,
            )

        counterexample = extract_counterexample(
            chosen.result,
            test_suite=suite_for_iteration,
            candidate_notes=[f"strategy={chosen.strategy}", f"rank_score={round(chosen.rank_score, 6)}"],
        )
        adjustments = strategy_adjustments(counterexample)
        refinement_history.append(
            RefinementIterationSummary(
                iteration=iteration,
                candidate_ids=[e.candidate_id for e in ranked],
                passing_candidates=[e.candidate_id for e in passing],
                selected_candidate_id=chosen.candidate_id,
                selected_strategy=chosen.strategy,
                selected_passed=chosen.result.passed,
                failure_reasons=list(counterexample.shortfall_reasons),
                guidance={
                    "failed_obligation_ids": counterexample.failed_obligation_ids,
                    "unknown_critical_obligation_ids": counterexample.unknown_critical_obligation_ids,
                    "unsupported_mappings": counterexample.unsupported_mappings,
                    "uncovered_items": counterexample.uncovered_items,
                    "partial_coverage_items": counterexample.partial_coverage_items,
                    "backend_error": counterexample.backend_error,
                },
                strategy_adjustments=adjustments,
            )
        )
        if chosen.result.passed:
            selected_eval = chosen
            selected_candidate = chosen_candidate
            generated_suite = suite_for_iteration
            break

        refinement_failure_summary.extend(counterexample.shortfall_reasons)
        selected_eval = chosen
        selected_candidate = chosen_candidate
        generated_suite = suite_for_iteration
        if not refine or iteration >= max_iterations:
            break
        candidates = refine_candidates(candidates, iteration=iteration + 1, counterexample=counterexample)

    assert selected_eval is not None
    assert selected_candidate is not None
    result = selected_eval.result
    result.package_context = dict(pkg_ctx)
    result.candidate_count = candidate_count
    result.winning_candidate_id = selected_eval.candidate_id
    result.synthesized_winner = candidate_count > 1
    result.ranking_basis = ranking_formula_description()
    result.candidate_summaries = [
        {
            "candidate_id": row.selected_candidate_id,
            "strategy": row.selected_strategy,
            "passed": row.selected_passed,
            "rank_score": None,
            "bridge_score": None,
            "measurement_ratio": None,
            "equivalence_score": None,
            "drift_score": None,
            "iteration": row.iteration,
        }
        for row in refinement_history
    ]
    if with_tests and generated_suite is not None:
        result.test_generation_enabled = True
        result.generated_test_files = sorted(generated_suite.generated_files.keys())
        result.preserve_rule_coverage = list(generated_suite.preserve_rule_coverage)
        result.constraint_coverage = list(generated_suite.constraint_coverage)
        result.uncovered_items = list(generated_suite.uncovered_items)
        result.partial_coverage_items = list(generated_suite.partial_coverage_items)
        result.test_generation_notes = list(generated_suite.notes)
    result.refinement_enabled = refine
    result.refinement_iterations_run = len(refinement_history)
    result.refinement_max_iterations = max_iterations
    result.refinement_success = result.passed
    result.winning_iteration = next(
        (h.iteration for h in refinement_history if h.selected_candidate_id == result.winning_candidate_id),
        len(refinement_history),
    )
    result.refinement_failure_summary = sorted(set(refinement_failure_summary))
    result.refinement_history = [to_history_row(h) for h in refinement_history]
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

    _print_report(
        result,
        report,
        show_obligations=show_obligations,
        show_equivalence=show_equivalence,
        spec_path=str(path),
        proof_artifact_path=str(proof_path) if write_proof else None,
    )
    if write_proof:
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

    out_path.write_text(selected_candidate.code, encoding="utf-8")
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


def _explain(
    path: Path,
    show_types: bool = False,
    show_effects: bool = False,
    show_resources: bool = False,
    show_inference: bool = False,
    show_agents: bool = False,
    show_agent_bridges: bool = False,
    show_delegation: bool = False,
    show_domain: bool = False,
    show_hardware: bool = False,
    show_simulation: bool = False,
    show_compliance: bool = False,
    show_genomics: bool = False,
) -> int:
    prepared = prepare_verification_input(path=path)
    source = prepared.source_text
    ir = prepared.ir
    pkg_ctx = prepared.package_context
    ast = parse_source(source)
    emitted_code, _ = emit_code(ir)
    result = verify(ir, emitted_code)
    print("AST:")
    print(ast)
    print("\nNormalized IR:")
    print(serialize_ir(ir))
    print("\nPreservation reasoning:")
    print(render_report(result, show_obligations=True, show_equivalence=True))
    if show_types:
        print("\nSemantic types:")
        print(f"summary: {ir.module.semantic_summary}")
        print(f"issues: {ir.module.semantic_issues}")
    if show_effects:
        print("\nEffect types:")
        print(f"summary: {ir.module.effect_summary}")
        print(f"issues: {ir.module.effect_issues}")
    if show_resources:
        print("\nResource types:")
        print(f"summary: {ir.module.resource_summary}")
        print(f"issues: {ir.module.resource_issues}")
    if show_inference:
        print("\nInference types:")
        print(f"summary: {ir.module.inference_summary}")
        print(f"issues: {ir.module.inference_issues}")
    if show_agents:
        print("\nAgent graph:")
        print(f"summary: {ir.module.agent_graph_summary}")
        print(f"issues: {ir.module.agent_graph_issues}")
    if show_agent_bridges:
        print("\nAgent boundary bridges:")
        print(f"summary: {ir.module.agent_boundary_summary}")
        print(f"issues: {ir.module.agent_boundary_issues}")
    if show_delegation:
        print("\nDelegation:")
        print(f"summary: {ir.module.delegation_summary}")
        print(f"issues: {ir.module.delegation_issues}")
    if show_domain:
        print("\nDomain:")
        print(f"profile: {ir.domain_profile}")
        print(f"summary: {ir.module.domain_summary}")
        print(f"issues: {ir.module.domain_issues}")
        print(f"obligations: {ir.module.domain_obligations}")
    if show_hardware:
        print("\nHardware:")
        print(f"summary: {ir.module.hardware_summary}")
        print(f"issues: {ir.module.hardware_issues}")
        print(f"obligations: {ir.module.hardware_obligations}")
        print(f"target_metadata: {ir.module.hardware_target_metadata}")
    if show_simulation:
        print("\nScientific Simulation:")
        print(f"summary: {ir.module.scientific_simulation_summary}")
        print(f"issues: {ir.module.scientific_simulation_issues}")
        print(f"obligations: {ir.module.scientific_simulation_obligations}")
        print(f"target_metadata: {ir.module.scientific_target_metadata}")
    if show_compliance:
        print("\nLegal Compliance:")
        print(f"summary: {ir.module.legal_compliance_summary}")
        print(f"issues: {ir.module.legal_compliance_issues}")
        print(f"obligations: {ir.module.legal_compliance_obligations}")
        print(f"target_metadata: {ir.module.compliance_target_metadata}")
        print(f"pii_taint_summary: {ir.module.pii_taint_summary}")
        print(f"audit_trail_metadata: {ir.module.audit_trail_metadata}")
    if show_genomics:
        print("\nGenomics:")
        print(f"summary: {ir.module.genomics_summary}")
        print(f"issues: {ir.module.genomics_issues}")
        print(f"obligations: {ir.module.genomics_obligations}")
        print(f"target_metadata: {ir.module.genomics_target_metadata}")
        print(f"metadata_privacy_summary: {ir.module.metadata_privacy_summary}")
        print(f"workflow_provenance_metadata: {ir.module.workflow_provenance_metadata}")
    return 0


def _verify(
    path: Path | None,
    report: ReportMode,
    show_obligations: bool = True,
    show_equivalence: bool = False,
    verification_backend: str = "heuristic",
    fallback_backend: str | None = None,
    use_calibration: bool = True,
    write_proof: bool = False,
    candidate_count: int = 3,
    with_tests: bool = False,
    snapshot: str | None = None,
    snapshot_store: Path | None = None,
) -> int:
    if path is not None and snapshot is not None:
        err = {
            "schema_version": "v1",
            "report_type": "verify",
            "error_type": "invalid_arguments",
            "error": "cannot use positional path and --snapshot together",
        }
        if report == "json":
            import json

            print(json.dumps(err, indent=2, sort_keys=True))
        else:
            print("verify failed: cannot use positional path and --snapshot together")
        return 1
    input_mode = "path"
    snapshot_id = None
    snapshot_store_str = None
    try:
        if snapshot is not None:
            resolved = resolve_snapshot(snapshot, snapshot_store)
            prepared = prepare_verification_input(
                source_text=resolved.source_text,
                source_name=f"snapshot:{resolved.snapshot_id}",
            )
            source = prepared.source_text
            ir = prepared.ir
            pkg_ctx = prepared.package_context
            input_mode = "snapshot"
            snapshot_id = resolved.snapshot_id
            snapshot_store_str = str(resolved.store_path)
            spec_path_for_report: str | None = None
            effective_path_for_proof = resolved.store_path / f"{resolved.snapshot_id}.vibe.proof.json"
            source_ref_path = Path(f"snapshot.{resolved.snapshot_id}.vibe")
        else:
            if path is None:
                raise ValueError("missing required input: provide a path or --snapshot <sha256>")
            prepared = prepare_verification_input(path=path)
            source = prepared.source_text
            ir = prepared.ir
            pkg_ctx = prepared.package_context
            spec_path_for_report = str(path)
            effective_path_for_proof = default_proof_path(path)
            source_ref_path = path
    except SnapshotResolutionError as exc:
        err = {
            "schema_version": "v1",
            "report_type": "verify",
            "input_mode": "snapshot",
            "snapshot_id": snapshot,
            "snapshot_store": str((snapshot_store or default_snapshot_store()).resolve()),
            "error_type": exc.code,
            "error": str(exc),
        }
        if report == "json":
            import json

            print(json.dumps(err, indent=2, sort_keys=True))
        else:
            print(f"verify failed: {exc}")
        return 1
    except Exception as exc:
        error_type = "parse_error" if isinstance(exc, ParseError) else "input_resolution_error"
        err = {
            "schema_version": "v1",
            "report_type": "verify",
            "input_mode": input_mode,
            "snapshot_id": snapshot_id,
            "snapshot_store": snapshot_store_str,
            "error_type": error_type,
            "error": str(exc),
        }
        if report == "json":
            import json

            print(json.dumps(err, indent=2, sort_keys=True))
        else:
            print(f"verify failed: {exc}")
        return 1
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
    result.package_context = dict(pkg_ctx)
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
        projected_path = output_path_for(path or Path("snapshot_input.vibe"), backend)
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
    proof_path = effective_path_for_proof
    if write_proof:
        proof = build_proof_artifact(
            source_ref_path,
            source,
            ir,
            result,
            emitted_blocked=not result.passed,
            notes=["verify flow proof artifact"],
            input_mode=input_mode,
            spec_path=spec_path_for_report,
            snapshot_id=snapshot_id,
            snapshot_store=snapshot_store_str,
        )
        write_proof_artifact(proof_path, proof)

    _print_report(
        result,
        report,
        show_obligations=show_obligations,
        show_equivalence=show_equivalence,
        spec_path=spec_path_for_report,
        proof_artifact_path=str(proof_path) if write_proof else None,
        input_mode=input_mode,
        snapshot_id=snapshot_id,
        snapshot_store=snapshot_store_str,
    )
    if result.backend_error:
        print(f"verify failed: {result.backend_error}")
    if write_proof:
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


def _snapshot_put(path: Path, report: ReportMode, snapshot_store: Path | None = None) -> int:
    try:
        source_text = path.read_text(encoding="utf-8")
    except Exception as exc:
        if report == "json":
            import json

            print(
                json.dumps(
                    {
                        "schema_version": "v1",
                        "report_type": "snapshot_put",
                        "error_type": "read_error",
                        "error": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"snapshot-put failed: {exc}")
        return 1

    out = snapshot_put(source_text, snapshot_store)
    if report == "json":
        import json

        print(
            json.dumps(
                {
                    "schema_version": "v1",
                    "report_type": "snapshot_put",
                    "snapshot_id": out.snapshot_id,
                    "snapshot_store": str(out.store_path),
                    "blob_path": str(out.blob_path),
                    "already_present": out.already_present,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"snapshot_id: {out.snapshot_id}")
        print(f"snapshot_store: {out.store_path}")
        print(f"blob_path: {out.blob_path}")
        print(f"already_present: {out.already_present}")
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


def _sigil_validate(path: Path, report: ReportMode) -> int:
    try:
        source = path.read_text(encoding="utf-8")
        ir = ast_to_ir(parse_source(source))
    except Exception as exc:
        if report == "json":
            import json

            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"sigil-validate failed: {exc}")
        return 1
    summary = dict(ir.module.sigil_summary)
    ok = bool(summary.get("syntax_valid", True)) and not any(
        not bool(summary.get(k, True))
        for k in (
            "structure_composable",
            "state_transition_allowed",
            "epsilon_nonzero",
            "temporal_sequence_coherent",
            "bridge_threshold_passed",
        )
    )
    if report == "json":
        import json

        print(json.dumps({"ok": ok, "summary": summary, "issues": list(ir.module.sigil_issues)}, indent=2, sort_keys=True))
    else:
        print("=== Vibe Sigil Validate ===")
        print(f"path: {path}")
        print(f"ok: {ok}")
        print(f"summary: {summary}")
        print(f"issues: {ir.module.sigil_issues}")
    return 0 if ok else 1


def _sigil_inspect(path: Path, report: ReportMode) -> int:
    try:
        source = path.read_text(encoding="utf-8")
        ir = ast_to_ir(parse_source(source))
    except Exception as exc:
        if report == "json":
            import json

            print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"sigil-inspect failed: {exc}")
        return 1
    if report == "json":
        import json

        print(
            json.dumps(
                {
                    "sigil_graph": ir.module.sigil_graph,
                    "sigil_summary": ir.module.sigil_summary,
                    "sigil_issues": ir.module.sigil_issues,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("=== Vibe Sigil Inspect ===")
        print(f"path: {path}")
        print(f"sigil_graph: {ir.module.sigil_graph}")
        print(f"sigil_summary: {ir.module.sigil_summary}")
        print(f"sigil_issues: {ir.module.sigil_issues}")
    return 0


def _monitor_eval(proof_path: Path, events_path: Path, report: ReportMode, show_events: bool = False) -> int:
    try:
        proof = load_proof_artifact(proof_path)
    except Exception as exc:
        print(f"monitor-eval failed: {exc}")
        return 1
    try:
        events = load_runtime_events(events_path)
    except Exception as exc:
        print(f"monitor-eval failed: {exc}")
        return 1

    config = dict(proof.get("runtime_monitor", {}))
    summary = evaluate_runtime_events(config, events)
    if report == "json":
        import json

        payload: dict[str, object] = {"runtime_monitor_config": config, "runtime_evaluation": summary}
        if show_events:
            payload["events"] = events
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("=== Vibe Runtime Monitor Eval ===")
        print(f"events_processed: {summary['events_processed']}")
        print(f"pipeline_runtime_score: {summary['pipeline_runtime_score']}")
        print(f"bridge_threshold: {summary['bridge_threshold']}")
        print(f"fallback_ratio: {summary['fallback_ratio']}")
        print(f"fallback_recommendation: {summary['fallback_recommendation']}")
        print(f"alert_recommendations: {summary['alert_recommendations']}")
        print(f"drift_signals: {summary['drift_signals']}")
        if show_events:
            print(f"events: {events}")
    return 0


def _init_project(path: Path) -> int:
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "vibe.toml"
    src_dir = root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    starter = src_dir / "main.vibe"
    if not manifest.exists():
        manifest.write_text(
            """[package]
name = "my-intent-package"
version = "0.1.0"
description = "Starter Vibe package"

[bridge]
measurement_safe_ratio = 0.85
epsilon_floor = 0.02

[emit]
default_target = "python"

[dependencies]
""",
            encoding="utf-8",
        )
    if not starter.exists():
        starter.write_text(
            """intent StarterIntent:
  goal: "Starter package intent"
  inputs:
    x: number
  outputs:
    y: number

emit python
""",
            encoding="utf-8",
        )
    print(f"initialized: {root}")
    return 0


def _manifest_check(manifest_path: Path, report: ReportMode) -> int:
    if manifest_path.is_dir():
        manifest_path = manifest_path / "vibe.toml"
    manifest, manifest_issues, graph = validate_manifest_and_graph(manifest_path)
    payload = {
        "manifest": {
            "name": manifest.package_name,
            "version": manifest.package_version,
            "description": manifest.description,
            "bridge_defaults": manifest.bridge_defaults,
            "emit_defaults": manifest.emit_defaults,
            "dependencies": manifest.dependencies,
        },
        "manifest_issues": [i.__dict__ for i in manifest_issues],
        "dependency_graph": {
            "root_package": graph.root_package,
            "packages": [asdict(p) for p in graph.packages],
            "edges": list(graph.edges),
            "issues": list(graph.issues),
        },
    }
    blocking = [i for i in payload["manifest_issues"] if i["severity"] in {"critical", "high"}] + [
        i for i in graph.issues if str(i.get("severity", "")) in {"critical", "high"}
    ]
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe Manifest Check ===")
        print(f"package: {manifest.package_name}@{manifest.package_version}")
        print(f"manifest_issues: {payload['manifest_issues']}")
        print(f"dependency_graph_edges: {payload['dependency_graph']['edges']}")
        print(f"dependency_graph_issues: {payload['dependency_graph']['issues']}")
    return 1 if blocking else 0


def _build_project(manifest_path: Path, report: ReportMode) -> int:
    if manifest_path.is_dir():
        manifest_path = manifest_path / "vibe.toml"
    payload = build_project(manifest_path)
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe Package Build ===")
        pkg = payload["package"]
        print(f"package: {pkg['name']}@{pkg['version']}")
        print(f"modules_built: {len(payload['build_modules'])}")
        print(f"manifest_issues: {payload['manifest_issues']}")
        print(f"dependency_issues: {payload['dependency_graph']['issues']}")
    return 1 if payload["blocking_issues"] else 0


def _diff(
    old_path: Path,
    new_path: Path,
    report: ReportMode,
    show_unchanged: bool = False,
    summary_only: bool = False,
    with_verification_context: bool = False,
) -> int:
    old_source = old_path.read_text(encoding="utf-8")
    new_source = new_path.read_text(encoding="utf-8")
    old_ir = ast_to_ir(parse_source(old_source))
    new_ir = ast_to_ir(parse_source(new_source))
    result = compute_intent_diff(old_ir, new_ir)
    verification_context: dict[str, object] | None = None
    if with_verification_context:
        try:
            old_code, _ = emit_code(old_ir)
            new_code, _ = emit_code(new_ir)
            old_verify = verify(old_ir, old_code, use_calibration=False)
            new_verify = verify(new_ir, new_code, use_calibration=False)
            old_summary = {
                "bridge_score": old_verify.bridge_score,
                "epsilon_post": old_verify.epsilon_post,
                "measurement_ratio": old_verify.measurement_ratio,
                "epsilon_floor": old_verify.epsilon_floor,
                "measurement_safe_ratio": old_verify.measurement_safe_ratio,
                "obligations_total": len(old_verify.obligations),
                "obligations_satisfied": sum(1 for o in old_verify.obligations if o.status == "satisfied"),
            }
            new_summary = {
                "bridge_score": new_verify.bridge_score,
                "epsilon_post": new_verify.epsilon_post,
                "measurement_ratio": new_verify.measurement_ratio,
                "epsilon_floor": new_verify.epsilon_floor,
                "measurement_safe_ratio": new_verify.measurement_safe_ratio,
                "obligations_total": len(new_verify.obligations),
                "obligations_satisfied": sum(1 for o in new_verify.obligations if o.status == "satisfied"),
            }
            verification_context = {
                "verification_requested": True,
                "available": True,
                "reason": None,
                "old": old_summary,
                "new": new_summary,
                "bridge_score_delta": round(new_verify.bridge_score - old_verify.bridge_score, 6),
            }
        except Exception as exc:
            verification_context = {
                "verification_requested": True,
                "available": False,
                "reason": f"verification_context_unavailable: {exc}",
                "old": None,
                "new": None,
                "bridge_score_delta": None,
            }
    if report == "json":
        print(
            render_intent_diff_json(
                result,
                old_spec=str(old_path),
                new_spec=str(new_path),
                verification_context=verification_context,
            )
        )
    else:
        print(render_intent_diff_human(result, show_unchanged=show_unchanged, summary_only=summary_only))
    return 0


def _publish(project_dir: Path, report: ReportMode, registry_root: Path | None = None) -> int:
    try:
        payload = publish_to_local_registry(project_dir.resolve(), registry_root=registry_root)
    except Exception as exc:
        print(f"publish failed: {exc}")
        return 1
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe Local Registry Publish ===")
        print(f"entry_id: {payload['entry_id']}")
        print(f"entry_hash: {payload['entry_hash']}")
        print(f"proof_status: {payload['proof_status']}")
        print(f"registry_root: {payload['registry_root']}")
        print(f"entry_path: {payload['entry_path']}")
        print("note: published to local filesystem registry (hosted registry is a future phase).")
    return 0


def _search(query: str, report: ReportMode, tags: list[str], domain: str | None, registry_root: Path | None = None) -> int:
    payload = search_local_registry(
        query,
        tag_filters=tags,
        domain_filter=domain,
        registry_root=registry_root,
    )
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe Local Registry Search ===")
        print(f"query: {query}")
        print(f"results: {payload['result_count']}")
        for row in payload["results"]:
            print(
                f"- {row['entry_id']} | score={row['score']} | proof={row['proof_status']} | "
                f"domain={row.get('domain') or '-'} | tags={','.join(row.get('tags', []))}"
            )
            if row.get("description"):
                print(f"  {row['description']}")
    return 0


def _registry_inspect(package_ref: str, report: ReportMode, registry_root: Path | None = None) -> int:
    try:
        payload = inspect_registry_entry(package_ref, registry_root=registry_root)
    except Exception as exc:
        print(f"registry-inspect failed: {exc}")
        return 1
    if report == "json":
        print(package_summary_json(payload))
    else:
        pkg = payload["package"]
        proof = payload["proof"]
        print("=== Vibe Local Registry Inspect ===")
        print(f"entry: {payload['entry_id']}")
        print(f"hash: {payload['entry_hash']}")
        print(f"package: {pkg.get('name')}@{pkg.get('version')}")
        print(f"description: {pkg.get('description', '')}")
        print(f"dependencies: {pkg.get('dependencies', {})}")
        print(f"bridge_defaults: {pkg.get('bridge_defaults', {})}")
        print(f"emit_defaults: {pkg.get('emit_defaults', {})}")
        print(f"modules: {[m.get('module') for m in pkg.get('modules', [])]}")
        print(f"domain: {pkg.get('domain')}")
        print(f"tags: {pkg.get('tags', [])}")
        print(
            "proof_summary: "
            f"status={proof.get('proof_status')} "
            f"artifacts={proof.get('proof_artifacts_present')}/{proof.get('total_modules')} "
            f"versions={proof.get('proof_artifact_versions')}"
        )
    return 0


def _compat(package_ref_a: str, package_ref_b: str, report: ReportMode, registry_root: Path | None = None) -> int:
    try:
        payload = compatibility_summary(package_ref_a, package_ref_b, registry_root=registry_root)
    except Exception as exc:
        print(f"compat failed: {exc}")
        return 1
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe Compatibility (Local Registry Hints) ===")
        print(payload["disclaimer"])
        p0, p1 = payload["packages"]
        print(f"a: {p0['entry_id']} proof={p0['proof_status']}")
        print(f"b: {p1['entry_id']} proof={p1['proof_status']}")
        print(f"major_compatible: {payload['semver']['major_compatible']}")
        print(f"minor_relation: {payload['semver']['minor_relation']}")
        print(f"dependency_mismatches: {payload['dependency_comparison']['mismatches']}")
        print(f"bridge_defaults_diff: {payload['bridge_defaults_diff']}")
        print(f"emit_defaults_equal: {payload['emit_defaults_equal']}")
        print(f"proof_version_overlap: {payload['proof_compatibility']['artifact_versions_overlap']}")
        print(f"compatibility_status: {payload['compatibility_status']}")
    return 0


def _lsp(check: bool = False) -> int:
    if check:
        print("vibe-lsp: ready")
        return 0
    return run_stdio_server()


def _ci_check(
    files: str,
    fail_on: str,
    report_json_path: str,
    backend: str,
    fallback_backend: str | None,
    with_proofs: bool,
    with_tests: bool,
    report: ReportMode,
) -> int:
    payload, code = run_ci_check(
        CICheckConfig(
            files_glob=files,
            fail_on=fail_on,
            report_json_path=report_json_path,
            backend=backend,
            fallback_backend=fallback_backend,
            with_proofs=with_proofs,
            with_tests=with_tests,
        )
    )
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe CI Bridge Check ===")
        print(f"files_checked: {payload['files_checked']}")
        print(f"files_failed: {payload['files_failed']}")
        print(f"worst_bridge_score: {payload['worst_bridge_score']}")
        print(f"report_json_path: {payload['report_json_path']}")
        print(f"summary_markdown_path: {payload['summary_markdown_path']}")
    return code


def _domains(report: ReportMode) -> int:
    if report == "json":
        print(domain_summary_json())
    else:
        print("=== Vibe Domain Profiles ===")
        print(domain_summary_json())
    return 0


def _self_check(
    spec: Path,
    baseline_path: Path | None,
    update_baseline: bool,
    fail_on_regression: bool,
    max_bridge_drop: float,
    verification_backend: str,
    fallback_backend: str | None,
    use_calibration: bool,
    write_proof: bool,
    report: ReportMode,
) -> int:
    try:
        checked = run_self_check(
            SelfCheckConfig(
                spec_path=spec,
                baseline_path=baseline_path,
                update_baseline=update_baseline,
                fail_on_regression=fail_on_regression,
                max_bridge_drop=max_bridge_drop,
                verification_backend=verification_backend,
                fallback_backend=fallback_backend,
                use_calibration=use_calibration,
                write_proof=write_proof,
            )
        )
    except Exception as exc:
        print(f"self-check failed: {exc}")
        return 1

    if report == "json":
        payload = {
            "self_hosting": checked.summary,
            "verification": asdict(checked.verification),
        }
        print(package_summary_json(payload))
    else:
        print("=== Vibe Self-Hosting Check (Phase 8.1) ===")
        print("scope: bounded compiler self-spec (not full compiler bootstrap)")
        print(f"compiler_spec_path: {checked.summary['compiler_spec_path']}")
        print(f"self_bridge_score: {checked.summary['self_bridge_score']}")
        print(f"measurement_ratio: {checked.summary['measurement_ratio']}")
        print(f"self_regression_status: {checked.summary['self_regression_status']}")
        print(f"baseline_reference: {checked.summary['baseline_reference']}")
        print(f"proof_artifact_paths: {checked.summary['proof_artifact_paths']}")
        print(f"regressed: {checked.summary['regressed']}")
        print(f"pass: {checked.exit_code == 0}")
    return checked.exit_code


def _semver(
    old_path: Path,
    new_path: Path,
    report: ReportMode,
    current_version: str | None,
    manifest_path: Path | None,
    apply_manifest: Path | None,
    show_rules: bool,
) -> int:
    old_source = old_path.read_text(encoding="utf-8")
    new_source = new_path.read_text(encoding="utf-8")
    old_ir = ast_to_ir(parse_source(old_source))
    new_ir = ast_to_ir(parse_source(new_source))

    effective_manifest = apply_manifest or manifest_path
    effective_version = current_version
    if effective_version is None and effective_manifest is not None:
        effective_version = current_version_from_manifest(effective_manifest)

    decision = derive_semver_from_diff(
        old_ir,
        new_ir,
        old_path=str(old_path),
        new_path=str(new_path),
        current_version=effective_version,
        manifest_path=str(effective_manifest) if effective_manifest is not None else None,
    )

    if apply_manifest is not None:
        if decision.recommended_next_version is None:
            print("semver failed: unable to derive next version for manifest write")
            return 1
        write_manifest_version(apply_manifest, decision.recommended_next_version)

    if report == "json":
        print(render_semver_json(decision))
    else:
        print(render_semver_human(decision, show_rules=show_rules))
        if apply_manifest is not None:
            print(f"manifest updated: {apply_manifest} -> {decision.recommended_next_version}")
    return 0


def _negotiate(
    paths: list[Path],
    report: ReportMode,
    write_negotiated: Path | None,
    write_artifact: Path | None,
    fail_on_conflict: bool,
    show_conflicts: bool,
    show_strengthening: bool,
) -> int:
    if len(paths) < 2:
        print("negotiate failed: need at least two .vibe specs")
        return 1
    sources = [p.read_text(encoding="utf-8") for p in paths]
    irs = [ast_to_ir(parse_source(src)) for src in sources]
    contract = negotiate_intents(irs, [str(p) for p in paths])

    if write_artifact is not None:
        write_negotiation_artifact(write_artifact, contract)
    if contract.success and write_negotiated is not None:
        write_negotiated.parent.mkdir(parents=True, exist_ok=True)
        write_negotiated.write_text(render_negotiated_vibe(contract), encoding="utf-8")

    if report == "json":
        print(render_negotiation_json(contract))
    else:
        print(
            render_negotiation_human(
                contract,
                show_conflicts=show_conflicts,
                show_strengthening=show_strengthening,
            )
        )
        if write_artifact is not None:
            print(f"negotiation_artifact: {write_artifact}")
        if contract.success and write_negotiated is not None:
            print(f"negotiated_intent: {write_negotiated}")

    if fail_on_conflict and not contract.success:
        return 1
    return 0


def _stdlib_list(report: ReportMode, root: Path = Path("stdlib")) -> int:
    packages: list[dict[str, object]] = []
    if root.exists():
        for pkg_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            manifest = pkg_dir / "vibe.toml"
            if manifest.exists():
                packages.append({"name": pkg_dir.name, "path": str(pkg_dir), "manifest": str(manifest)})
    payload = {"stdlib_root": str(root), "packages": packages, "count": len(packages)}
    if report == "json":
        print(package_summary_json(payload))
    else:
        print("=== Vibe Standard Library Packages ===")
        for row in packages:
            print(f"- {row['name']} ({row['path']})")
    return 0


def _merge_verify(
    base_path: Path,
    left_path: Path,
    right_path: Path,
    report: ReportMode,
    write_merged: Path | None,
    write_merge_report_path: Path | None,
    regression_top_n: int | None = None,
    regression_include_evidence: bool = False,
    require_merged_bridge: float | None = None,
    max_bridge_regression: float | None = None,
    fail_on_intent_conflicts: bool = False,
) -> int:
    result = merge_verify(
        base_path.read_text(encoding="utf-8"),
        left_path.read_text(encoding="utf-8"),
        right_path.read_text(encoding="utf-8"),
        regression_top_n=regression_top_n,
        regression_include_evidence=regression_include_evidence,
        require_merged_bridge=require_merged_bridge,
        max_bridge_regression=max_bridge_regression,
        fail_on_intent_conflicts=fail_on_intent_conflicts,
    )
    payload = merge_verify_payload(
        result,
        base_spec=str(base_path),
        left_spec=str(left_path),
        right_spec=str(right_path),
    )
    merged_path = maybe_write_merged(write_merged, result)
    merge_report_path = write_merge_report(write_merge_report_path, payload)
    if report == "json":
        payload_text = render_merge_verify_json(
            result,
            base_spec=str(base_path),
            left_spec=str(left_path),
            right_spec=str(right_path),
        )
        print(payload_text)
        if merged_path is not None:
            print(f"merged_output: {merged_path}")
        if merge_report_path is not None:
            print(f"merge_report: {merge_report_path}")
    else:
        print(render_merge_verify_human(result))
        if merged_path is not None:
            print(f"merged_output: {merged_path}")
        if merge_report_path is not None:
            print(f"merge_report: {merge_report_path}")
    if result.merge_status == "error":
        return 1
    if result.merge_status == "conflict":
        return 1
    assert result.verification is not None
    if not bool(result.verification.get("passed")):
        return 1
    if bool((result.policy_evaluation or {}).get("requested")) and not bool((result.policy_evaluation or {}).get("passed")):
        return 1
    return 0


def _interchange_from_text(input_path: Path, report: ReportMode, write_output: Path | None) -> int:
    try:
        source_text = input_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"interchange-from-text failed: {exc}")
        return 1

    artifact = build_interchange_from_text(source_text, source_path=input_path)
    if write_output is not None:
        write_json_artifact(write_output, artifact)

    if report == "json":
        print(package_summary_json(artifact))
    else:
        print("=== Vibe Interchange Artifact ===")
        print(f"artifact_version: {artifact['artifact_version']}")
        print(f"source_path: {input_path}")
        print(f"intent_name: {artifact['generated_intent']['intent_name']}")
        print("mode: deterministic_scaffold")
        if write_output is not None:
            print(f"artifact_path: {write_output}")
    return 0


def _intent_brief(path: Path, report: ReportMode, write_output: Path | None) -> int:
    try:
        source_text = path.read_text(encoding="utf-8")
        brief = build_intent_brief(path, source_text)
    except Exception as exc:
        print(f"intent-brief failed: {exc}")
        return 1

    if write_output is not None:
        write_json_artifact(write_output, brief)

    if report == "json":
        print(package_summary_json(brief))
    else:
        print("=== Vibe Intent Brief ===")
        print(f"source_path: {brief['source_path']}")
        intent = brief["intent"]
        print(f"intent: {intent['name']}")
        print(f"emit_target: {brief['emit_target']}")
        print(f"inputs: {[r['name'] for r in intent['inputs']]}")
        print(f"outputs: {[r['name'] for r in intent['outputs']]}")
        if write_output is not None:
            print(f"brief_path: {write_output}")
    return 0


def _proof_brief(path: Path, report: ReportMode, write_output: Path | None) -> int:
    try:
        proof = load_proof_artifact(path)
    except Exception as exc:
        print(f"proof-brief failed: {exc}")
        return 1

    brief = build_proof_brief(proof, proof_path=path)
    if write_output is not None:
        write_json_artifact(write_output, brief)

    if report == "json":
        print(package_summary_json(brief))
    else:
        print("=== Vibe Proof Consumer Brief ===")
        print(f"proof_path: {path}")
        print(f"source_path: {brief['source_path']}")
        print(f"bridge_verdict: {brief['bridge_result']['verdict']}")
        print(f"bridge_score: {brief['bridge_result']['bridge_score']}")
        print(f"equivalence_score: {brief['equivalence_drift_summary']['intent_equivalence_score']}")
        if write_output is not None:
            print(f"brief_path: {write_output}")
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
    cp.add_argument("--refine", action="store_true", help="Enable deterministic bridge-gated refinement loop")
    cp.add_argument("--max-iters", type=int, default=3, help="Maximum refinement iterations when --refine is enabled")

    ex = sub.add_parser("explain", help="Explain AST and IR")
    ex.add_argument("path", type=Path)
    ex.add_argument("--show-types", action="store_true", help="Show semantic type summary and issues")
    ex.add_argument("--show-effects", action="store_true", help="Show effect type summary and issues")
    ex.add_argument("--show-resources", action="store_true", help="Show resource type summary and issues")
    ex.add_argument("--show-inference", action="store_true", help="Show inference type summary and issues")
    ex.add_argument("--show-agents", action="store_true", help="Show agent graph summary and issues")
    ex.add_argument("--show-agent-bridges", action="store_true", help="Show boundary bridge propagation summary and issues")
    ex.add_argument("--show-delegation", action="store_true", help="Show delegation summary and issues")
    ex.add_argument("--show-domain", action="store_true", help="Show active domain profile summary/issues")
    ex.add_argument("--show-hardware", action="store_true", help="Show hardware domain summary/issues/obligations")
    ex.add_argument("--show-simulation", action="store_true", help="Show scientific simulation summary/issues/obligations")
    ex.add_argument("--show-compliance", action="store_true", help="Show legal compliance summary/issues/obligations")
    ex.add_argument("--show-genomics", action="store_true", help="Show genomics summary/issues/obligations")

    vf = sub.add_parser("verify", help="Run verifier without emission")
    vf.add_argument("path", type=Path, nargs="?", default=None)
    vf.add_argument("--snapshot", type=str, default=None, help="Verify from content-addressed snapshot sha256")
    vf.add_argument("--snapshot-store", type=Path, default=None, help="Snapshot store directory (default ./.vibe_snapshots or VIBE_SNAPSHOT_STORE)")
    vf.add_argument("--report", choices=["human", "json"], default="human")
    vf.add_argument("--show-obligations", action="store_true", help="Show full obligation list in human report")
    vf.add_argument("--show-equivalence", action="store_true", help="Show detailed equivalence/diff entries in human report")
    vf.add_argument("--backend", default="heuristic", help=f"Verification backend ({', '.join(available_backends())})")
    vf.add_argument("--fallback-backend", default=None, help="Optional fallback backend for unknown obligations")
    vf.add_argument("--no-calibration", action="store_true", help="Disable empirical epsilon calibration")
    vf.add_argument("--write-proof", action="store_true", help="Write deterministic preservation proof artifact")
    vf.add_argument("--candidates", type=int, default=3, help="Number of deterministic synthesis candidates")
    vf.add_argument("--with-tests", action="store_true", help="Include intent-guided test metadata in verification report")

    sp = sub.add_parser("snapshot-put", help="Store local .vibe source by content hash in a local snapshot store")
    sp.add_argument("path", type=Path)
    sp.add_argument("--snapshot-store", type=Path, default=None, help="Snapshot store directory (default ./.vibe_snapshots or VIBE_SNAPSHOT_STORE)")
    sp.add_argument("--report", choices=["human", "json"], default="human")

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

    me = sub.add_parser("monitor-eval", help="Evaluate runtime events against proof monitor metadata")
    me.add_argument("proof_path", type=Path)
    me.add_argument("events_path", type=Path)
    me.add_argument("--report", choices=["human", "json"], default="human")
    me.add_argument("--show-events", action="store_true", help="Include input runtime events in output")

    rc = sub.add_parser("runtime-check", help="Alias for monitor-eval")
    rc.add_argument("proof_path", type=Path)
    rc.add_argument("events_path", type=Path)
    rc.add_argument("--report", choices=["human", "json"], default="human")
    rc.add_argument("--show-events", action="store_true", help="Include input runtime events in output")

    ipm_init = sub.add_parser("init", help="Initialize a local Vibe package project")
    ipm_init.add_argument("path", type=Path, nargs="?", default=Path("."))

    ipm_check = sub.add_parser("manifest-check", help="Validate vibe.toml and local dependency graph")
    ipm_check.add_argument("manifest_path", type=Path, nargs="?", default=Path("vibe.toml"), help="Path to vibe.toml or package directory")
    ipm_check.add_argument("--report", choices=["human", "json"], default="human")

    ipm_build = sub.add_parser("build", help="Build multi-file package from vibe.toml")
    ipm_build.add_argument("manifest_path", type=Path, nargs="?", default=Path("vibe.toml"), help="Path to vibe.toml or package directory")
    ipm_build.add_argument("--report", choices=["human", "json"], default="human")

    df = sub.add_parser("diff", help="Semantic diff between two .vibe intent specs")
    df.add_argument("old_path", type=Path)
    df.add_argument("new_path", type=Path)
    df.add_argument("--report", choices=["human", "json"], default="human")
    df.add_argument("--show-unchanged", action="store_true", help="Show unchanged summary row if there are no semantic changes")
    df.add_argument("--summary-only", action="store_true", help="Show summary only")
    df.add_argument(
        "--with-verification-context",
        action="store_true",
        help="Include whole-spec old/new verification summaries in JSON diff output",
    )

    pub = sub.add_parser("publish", help="Publish a package into the local filesystem intent registry")
    pub.add_argument("project_dir", type=Path, nargs="?", default=Path("."))
    pub.add_argument("--registry-root", type=Path, default=None, help="Optional registry root (defaults to ./.vibe_registry or VIBE_REGISTRY_ROOT)")
    pub.add_argument("--report", choices=["human", "json"], default="human")

    srch = sub.add_parser("search", help="Search local intent registry entries")
    srch.add_argument("query", type=str)
    srch.add_argument("--tag", dest="tags", action="append", default=[], help="Filter by tag (can be repeated)")
    srch.add_argument("--domain", type=str, default=None, help="Filter by domain")
    srch.add_argument("--registry-root", type=Path, default=None, help="Optional registry root override")
    srch.add_argument("--report", choices=["human", "json"], default="human")

    insp = sub.add_parser("registry-inspect", help="Inspect a package entry in the local registry")
    insp.add_argument("package_ref", type=str, help="package[@version]")
    insp.add_argument("--registry-root", type=Path, default=None, help="Optional registry root override")
    insp.add_argument("--report", choices=["human", "json"], default="human")

    cmpa = sub.add_parser("compat", help="Compute deterministic compatibility hints between two registry packages")
    cmpa.add_argument("package_ref_a", type=str)
    cmpa.add_argument("package_ref_b", type=str)
    cmpa.add_argument("--registry-root", type=Path, default=None, help="Optional registry root override")
    cmpa.add_argument("--report", choices=["human", "json"], default="human")

    lsp = sub.add_parser("lsp", help="Run Vibe Language Server Protocol (LSP) server over stdio")
    lsp.add_argument("--check", action="store_true", help="Validate launch path and exit")

    cic = sub.add_parser("ci-check", help="Run deterministic CI-style bridge checks for .vibe files")
    cic.add_argument("--files", default="**/*.vibe", help="Glob pattern for .vibe files")
    cic.add_argument("--fail-on", default="", help="Comma-separated fail conditions (e.g. ENTROPY_NOISE,bridge_score_below_threshold:0.9)")
    cic.add_argument("--report-json-path", default=".vibe_ci/bridge_report.json")
    cic.add_argument("--backend", default="heuristic", help=f"Verification backend ({', '.join(available_backends())})")
    cic.add_argument("--fallback-backend", default=None, help="Optional fallback backend for unknown obligations")
    cic.add_argument("--with-proofs", action="store_true", help="Write proof artifacts for checked files")
    cic.add_argument("--with-tests", action="store_true", help="Generate intent-guided tests during check")
    cic.add_argument("--report", choices=["human", "json"], default="human")

    dom = sub.add_parser("domains", help="List available cross-domain intent profiles")
    dom.add_argument("--report", choices=["human", "json"], default="human")

    sh = sub.add_parser("self-check", help="Run Phase 8.1 bounded compiler self-hosting verification")
    sh.add_argument("--spec", type=Path, default=Path("self_hosting/vibec_core.vibe"))
    sh.add_argument(
        "--baseline-path",
        type=Path,
        default=Path(".vibe_self_hosting/compiler_self_bridge_baseline.json"),
    )
    sh.add_argument("--update-baseline", action="store_true", help="Write/update self-hosting baseline artifact")
    sh.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Fail when current self bridge score regresses below allowed threshold",
    )
    sh.add_argument("--max-bridge-drop", type=float, default=0.0, help="Allowed drop vs baseline before regression")
    sh.add_argument("--backend", default="heuristic", help=f"Verification backend ({', '.join(available_backends())})")
    sh.add_argument("--fallback-backend", default=None, help="Optional fallback backend for unknown obligations")
    sh.add_argument("--no-calibration", action="store_true", help="Disable empirical epsilon calibration")
    sh.add_argument("--no-proof", action="store_true", help="Do not write proof artifact for self-check")
    sh.add_argument("--report", choices=["human", "json"], default="human")

    sv = sub.add_parser("semver", help="Derive semver bump from semantic intent diff")
    sv.add_argument("old_path", type=Path)
    sv.add_argument("new_path", type=Path)
    sv.add_argument("--report", choices=["human", "json"], default="human")
    sv.add_argument("--current-version", default=None, help="Current semantic version (MAJOR.MINOR.PATCH)")
    sv.add_argument("--manifest-path", type=Path, default=None, help="Optional vibe.toml path for version read")
    sv.add_argument(
        "--apply-manifest",
        type=Path,
        default=None,
        help="Explicitly write recommended next version into manifest package.version",
    )
    sv.add_argument("--show-rules", action="store_true", help="Show semver classification rule IDs and conservative flags")

    ng = sub.add_parser("negotiate", help="Negotiate multiple intent contracts into a deterministic merged contract")
    ng.add_argument("paths", nargs="+", type=Path)
    ng.add_argument("--report", choices=["human", "json"], default="human")
    ng.add_argument("--write-negotiated", type=Path, default=None, help="Write negotiated .vibe contract when negotiation succeeds")
    ng.add_argument("--write-artifact", type=Path, default=None, help="Write deterministic negotiation JSON artifact")
    ng.add_argument("--fail-on-conflict", action="store_true", help="Return non-zero when conflicts/ambiguities are present")
    ng.add_argument("--show-conflicts", action="store_true", help="Show conflicts and ambiguous clauses in human output")
    ng.add_argument("--show-strengthening", action="store_true", help="Show strengthened clauses in human output")

    sl = sub.add_parser("stdlib-list", help="List built-in standard library packages")
    sl.add_argument("--report", choices=["human", "json"], default="human")

    it = sub.add_parser("interchange-from-text", help="Build deterministic NL->.vibe interchange scaffold artifact")
    it.add_argument("input_path", type=Path, help="Plain-text requirement file")
    it.add_argument("--report", choices=["human", "json"], default="human")
    it.add_argument("--write-output", type=Path, default=None, help="Optional JSON artifact path")

    ib = sub.add_parser("intent-brief", help="Build deterministic machine-readable brief from .vibe intent spec")
    ib.add_argument("path", type=Path)
    ib.add_argument("--report", choices=["human", "json"], default="human")
    ib.add_argument("--write-output", type=Path, default=None, help="Optional JSON brief path")

    pb = sub.add_parser("proof-brief", help="Build deterministic machine-readable consumer brief from .vibe.proof.json")
    pb.add_argument("path", type=Path)
    pb.add_argument("--report", choices=["human", "json"], default="human")
    pb.add_argument("--write-output", type=Path, default=None, help="Optional JSON brief path")

    mv = sub.add_parser("merge-verify", help="Three-way merge and verify Vibe specs")
    mv.add_argument("base_path", type=Path)
    mv.add_argument("left_path", type=Path)
    mv.add_argument("right_path", type=Path)
    mv.add_argument("--report", choices=["human", "json"], default="human")
    mv.add_argument("--write-merged", type=Path, default=None, help="Write merged .vibe file on successful merge")
    mv.add_argument("--write-merge-report", type=Path, default=None, help="Write machine-readable merge-verify JSON report")
    mv.add_argument(
        "--regression-top-n",
        type=int,
        default=None,
        help="Max number of regression_evidence top_problem_obligations rows to show (clamped to safe bounds)",
    )
    mv.add_argument(
        "--regression-include-evidence",
        action="store_true",
        help="Include compact evidence_text in regression_evidence rows when available",
    )
    mv.add_argument(
        "--require-merged-bridge",
        type=float,
        default=None,
        help="Fail with non-zero exit if merged bridge_score is below this threshold",
    )
    mv.add_argument(
        "--max-bridge-regression",
        type=_non_negative_float,
        default=None,
        help="Allow at most this much merged bridge_score regression vs base (delta must be >= -value)",
    )
    mv.add_argument(
        "--fail-on-intent-conflicts",
        action="store_true",
        help="Fail with non-zero exit if merged result contains any intent_conflicts",
    )
    sg = sub.add_parser("sigil-validate", help="Validate sigil notation obligations in a .vibe file")
    sg.add_argument("path", type=Path)
    sg.add_argument("--report", choices=["human", "json"], default="human")
    si = sub.add_parser("sigil-inspect", help="Inspect lowered canonical SigilGraph IR for a .vibe file")
    si.add_argument("path", type=Path)
    si.add_argument("--report", choices=["human", "json"], default="human")

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
            refine=args.refine,
            max_iters=args.max_iters,
        )
    if args.command == "explain":
        return _explain(
            args.path,
            show_types=args.show_types,
            show_effects=args.show_effects,
            show_resources=args.show_resources,
            show_inference=args.show_inference,
            show_agents=args.show_agents,
            show_agent_bridges=args.show_agent_bridges,
            show_delegation=args.show_delegation,
            show_domain=args.show_domain,
            show_hardware=args.show_hardware,
            show_simulation=args.show_simulation,
            show_compliance=args.show_compliance,
            show_genomics=args.show_genomics,
        )
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
            snapshot=args.snapshot,
            snapshot_store=args.snapshot_store,
        )
    if args.command == "snapshot-put":
        return _snapshot_put(args.path, args.report, snapshot_store=args.snapshot_store)
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
    if args.command == "sigil-validate":
        return _sigil_validate(args.path, args.report)
    if args.command == "sigil-inspect":
        return _sigil_inspect(args.path, args.report)
    if args.command in {"monitor-eval", "runtime-check"}:
        return _monitor_eval(args.proof_path, args.events_path, args.report, show_events=args.show_events)
    if args.command == "init":
        return _init_project(args.path)
    if args.command == "manifest-check":
        return _manifest_check(args.manifest_path, args.report)
    if args.command == "build":
        return _build_project(args.manifest_path, args.report)
    if args.command == "diff":
        return _diff(
            args.old_path,
            args.new_path,
            args.report,
            show_unchanged=args.show_unchanged,
            summary_only=args.summary_only,
            with_verification_context=args.with_verification_context,
        )
    if args.command == "publish":
        return _publish(args.project_dir, args.report, registry_root=args.registry_root)
    if args.command == "search":
        return _search(args.query, args.report, args.tags, args.domain, registry_root=args.registry_root)
    if args.command == "registry-inspect":
        return _registry_inspect(args.package_ref, args.report, registry_root=args.registry_root)
    if args.command == "compat":
        return _compat(args.package_ref_a, args.package_ref_b, args.report, registry_root=args.registry_root)
    if args.command == "lsp":
        return _lsp(check=args.check)
    if args.command == "ci-check":
        return _ci_check(
            files=args.files,
            fail_on=args.fail_on,
            report_json_path=args.report_json_path,
            backend=args.backend,
            fallback_backend=args.fallback_backend,
            with_proofs=args.with_proofs,
            with_tests=args.with_tests,
            report=args.report,
        )
    if args.command == "domains":
        return _domains(args.report)
    if args.command == "self-check":
        return _self_check(
            spec=args.spec,
            baseline_path=args.baseline_path,
            update_baseline=args.update_baseline,
            fail_on_regression=args.fail_on_regression,
            max_bridge_drop=args.max_bridge_drop,
            verification_backend=args.backend,
            fallback_backend=args.fallback_backend,
            use_calibration=not args.no_calibration,
            write_proof=not args.no_proof,
            report=args.report,
        )
    if args.command == "semver":
        return _semver(
            old_path=args.old_path,
            new_path=args.new_path,
            report=args.report,
            current_version=args.current_version,
            manifest_path=args.manifest_path,
            apply_manifest=args.apply_manifest,
            show_rules=args.show_rules,
        )
    if args.command == "negotiate":
        return _negotiate(
            paths=args.paths,
            report=args.report,
            write_negotiated=args.write_negotiated,
            write_artifact=args.write_artifact,
            fail_on_conflict=args.fail_on_conflict,
            show_conflicts=args.show_conflicts,
            show_strengthening=args.show_strengthening,
        )
    if args.command == "stdlib-list":
        return _stdlib_list(args.report)
    if args.command == "interchange-from-text":
        return _interchange_from_text(args.input_path, args.report, args.write_output)
    if args.command == "intent-brief":
        return _intent_brief(args.path, args.report, args.write_output)
    if args.command == "proof-brief":
        return _proof_brief(args.path, args.report, args.write_output)
    if args.command == "merge-verify":
        return _merge_verify(
            args.base_path,
            args.left_path,
            args.right_path,
            args.report,
            write_merged=args.write_merged,
            write_merge_report_path=args.write_merge_report,
            regression_top_n=args.regression_top_n,
            regression_include_evidence=args.regression_include_evidence,
            require_merged_bridge=args.require_merged_bridge,
            max_bridge_regression=args.max_bridge_regression,
            fail_on_intent_conflicts=args.fail_on_intent_conflicts,
        )

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
