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
from .diff import compute_intent_diff, render_intent_diff_human, render_intent_diff_json
from .emitter import emit_code, output_path_for
from .ir import ast_to_ir, serialize_ir
from .parser import parse_source
from .package_manager import (
    apply_package_defaults_to_source,
    build_project,
    package_context_for_path,
    package_summary_json,
    validate_manifest_and_graph,
)
from dataclasses import asdict
from .manifest import VibeManifest
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
from .runtime_monitor import evaluate_runtime_events, load_runtime_events
from .refinement import (
    RefinementIterationSummary,
    extract_counterexample,
    refine_candidates,
    strategy_adjustments,
    to_history_row,
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
    refine: bool = False,
    max_iters: int = 3,
) -> int:
    source = _load(path)
    pkg_ctx = package_context_for_path(path)
    if pkg_ctx:
        source = apply_package_defaults_to_source(
            source,
            VibeManifest(
                package_name=str(pkg_ctx.get("package_name", "")),
                package_version=str(pkg_ctx.get("package_version", "")),
                description="",
                dependencies=dict(pkg_ctx.get("dependencies", {})),
                bridge_defaults=dict(pkg_ctx.get("bridge_defaults", {})),
                emit_defaults=dict(pkg_ctx.get("emit_defaults", {})),
            ),
        )
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
) -> int:
    source = _load(path)
    pkg_ctx = package_context_for_path(path)
    if pkg_ctx:
        source = apply_package_defaults_to_source(
            source,
            VibeManifest(
                package_name=str(pkg_ctx.get("package_name", "")),
                package_version=str(pkg_ctx.get("package_version", "")),
                description="",
                dependencies=dict(pkg_ctx.get("dependencies", {})),
                bridge_defaults=dict(pkg_ctx.get("bridge_defaults", {})),
                emit_defaults=dict(pkg_ctx.get("emit_defaults", {})),
            ),
        )
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
    pkg_ctx = package_context_for_path(path)
    if pkg_ctx:
        source = apply_package_defaults_to_source(
            source,
            VibeManifest(
                package_name=str(pkg_ctx.get("package_name", "")),
                package_version=str(pkg_ctx.get("package_version", "")),
                description="",
                dependencies=dict(pkg_ctx.get("dependencies", {})),
                bridge_defaults=dict(pkg_ctx.get("bridge_defaults", {})),
                emit_defaults=dict(pkg_ctx.get("emit_defaults", {})),
            ),
        )
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
) -> int:
    old_source = _load(old_path)
    new_source = _load(new_path)
    old_ir = ast_to_ir(parse_source(old_source))
    new_ir = ast_to_ir(parse_source(new_source))
    result = compute_intent_diff(old_ir, new_ir)
    if report == "json":
        print(render_intent_diff_json(result))
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
        )
    if args.command == "publish":
        return _publish(args.project_dir, args.report, registry_root=args.registry_root)
    if args.command == "search":
        return _search(args.query, args.report, args.tags, args.domain, registry_root=args.registry_root)
    if args.command == "registry-inspect":
        return _registry_inspect(args.package_ref, args.report, registry_root=args.registry_root)
    if args.command == "compat":
        return _compat(args.package_ref_a, args.package_ref_b, args.report, registry_root=args.registry_root)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
