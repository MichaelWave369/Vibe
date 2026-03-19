# Vibe

**Mission:** make intent the source of truth and preserve it through compilation.

**Vibe is an intent-first programming language and compiler prototype where compilation succeeds only when implementation preserves meaning above the bridge threshold.**

## What Vibe is

Vibe is a language-and-compiler layer built around `.vibe` source files. A Vibe compile pipeline is:

`source file -> parse -> IR -> verify -> emit -> report`

Vibe focuses on compiler law first:
- intent is source code
- preservation is compilation truth

## Why Vibe exists

Many generation workflows produce runnable code but cannot tell you whether intent drift occurred. Vibe addresses this by requiring a preservation check before emitting artifacts.

If bridge preservation is below threshold, compile fails.

## Nevora lineage (and how Vibe differs)

Nevora was an earlier translator layer centered on natural-language intent to starter code workflows.

Vibe is the language/compiler evolution of that direction. It borrows structural maturity lessons (packaging, examples, tests, CLI discipline) but is not a rename of Nevora. Vibe introduces:
- a dedicated `.vibe` language surface
- parser + AST + IR compiler phases
- preservation verifier and bridge report
- compile-law gatekeeping

## Founding law

Default bridge law for v0.1:

- `epsilon_floor = 0.02`
- `measurement_safe_ratio = 0.85`

Compile must fail when either condition is true:

- `epsilon_post <= epsilon_floor`
- `measurement_ratio < measurement_safe_ratio`

Where:

- `measurement_ratio = epsilon_post / max(epsilon_pre, epsilon_floor)`

## Language surface (v0.1)


## Parser Foundation (Phase 1.1)

Vibe now uses a **formal grammar-backed front end** as the syntax source of truth (`vibe/grammar.py`) with a PEG-style parser implementation in `vibe/parser.py`.

### `vibe_version`

`.vibe` files may optionally declare `vibe_version` at the top. If omitted, parsing remains backward-compatible with existing examples and defaults to current behavior.


### Typed SSA IR (Phase 1.2)

After parsing, Vibe now lowers AST into a **typed SSA-style IR**:

`.vibe -> parse -> AST -> typed SSA IR -> verify -> emit -> report`

Each IR value has a unique SSA ID, explicit type tag, and def-use references. Serialization is deterministic JSON for future incremental compilation workflows.


Supported top-level blocks:
- `intent`
- `preserve`
- `constraint`
- `bridge`
- `emit`

Example:

```vibe
intent PaymentRouter:
  goal: "Route payments to the cheapest valid processor."
  inputs:
    amount: number
    country: string
    card_brand: string
  outputs:
    processor: string
    total_fee: number

preserve:
  latency < 200ms
  failure_rate < 0.01
  compliance = strict
  readability = high
  testability = high

constraint:
  no hardcoded secrets
  deterministic fee selection
  graceful fallback on provider outage

bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
  mode = strict

emit python
```

## Install

```bash
python -m pip install -e .
```



## Formal verification surfaces (Phase 2.1)

Vibe now exposes explicit verification obligations as a proof-surface layer alongside bridge metrics.

Obligation categories currently include:
- preserve
- constraint
- bridge (including founding-law thresholds)
- sovereignty
- delegation

Each obligation includes stable ID, category, description, status, and evidence.

Statuses: `satisfied`, `violated`, `unknown`, `not_applicable`.

Current obligation discharge is operational/heuristic (not full SMT/theorem proving yet).

Unknown obligations are surfaced explicitly and are never silently treated as satisfied for critical layers.

## SMT-ready backend abstraction (Phase 2.2)

Verification is now split into explicit lifecycle stages:

1. obligation generation
2. obligation normalization
3. backend evaluation
4. result aggregation + preservation gating
5. reporting

The default backend is currently:

- `heuristic` (operational checks; existing behavior preserved)

Planned backend surfaces (architecture is present, implementation is stubbed):

- `symbolic` (placeholder)
- `smt` (placeholder)

Backends that are not implemented yet fail safely with a clear message and never bypass preservation law.

Normalized obligations now include solver-ready fields such as:
- `subject_ref`
- `expected_predicate`
- `severity`
- `critical`

Reports now include backend metadata:
- `verification_backend`
- `backend_version`
- `backend_mode`
- backend capabilities and backend errors (if any)

This is still an operational verification system (not full theorem proving yet).

## First symbolic/SMT adapter (Phase 2.3)

Vibe now includes its first real solver-style backend: `--backend smt`.

Current solver-supported subset is intentionally narrow:

- founding law bridge checks:
  - `epsilon_post > epsilon_floor`
  - `measurement_ratio >= measurement_safe_ratio`
- simple scalar comparisons (`>`, `>=`, `<`, `<=`)
- simple scalar/symbol equality (`=`)
- boolean assertions (`key: true|false` or `key = true|false`)

Unsupported predicates are surfaced as `unknown`/deferred with explicit evidence.
They are never silently marked as satisfied.

Optional hybrid mode is available through fallback:

- `--fallback-backend heuristic`

This allows unknown SMT results to be evaluated by a fallback backend, and reports record whether fallback was used.

This is a first proof-surface slice, not full theorem proving or full equivalence checking.

## Equivalence + intent-diff surfaces (Phase 2.4)

Vibe now reports a structural intent/emission correspondence layer in addition to obligation outcomes.

This phase is correspondence-oriented (not full behavioral equivalence proving). The report now includes:

- per-item correspondence statuses:
  - `matched`
  - `partially_matched`
  - `missing_in_output`
  - `extra_in_output`
  - `unknown`
- intent/diff summary metrics:
  - `intent_items_total`
  - `intent_items_matched`
  - `intent_items_partial`
  - `intent_items_missing`
  - `intent_items_extra`
  - `intent_items_unknown`
  - `intent_equivalence_score`
  - `drift_score`

Target-aware structural mapping is implemented for both Python and TypeScript emission surfaces.

This layer strengthens drift visibility and does not replace bridge truth:
- founding-law and critical obligations remain authoritative for pass/fail.
- equivalence/diff is an additional inspectable verification surface.

## Empirical epsilon calibration (Calibration as learning)

Vibe now supports an empirical calibration subsystem for epsilon estimation.

- Corpus location (seed): `vibe/calibration_corpus/seed_corpus.json`
- Calibration artifact (local deterministic output): `.vibe_calibration/bridge_calibration.json`
- Command: `vibec calibrate <corpus-path>`

Calibration is intentionally simple and inspectable (deterministic weighted linear adjustment), and it only refines epsilon surfaces:

- `epsilon_pre`
- `epsilon_post`

Safety rules:
- calibration never bypasses failed critical obligations/founding-law failures
- if artifact is missing/corrupt, verification falls back explicitly to default heuristic epsilon estimation
- reports always state whether calibration was applied

This is empirical calibration, not proof.

## Preservation proof artifacts

Vibe now supports deterministic preservation proof artifacts (`.vibe.proof.json`) that record verification context and outcomes.

Proof artifacts include:
- source + IR hashes
- backend and backend metadata
- calibration state and model metadata
- obligation summaries and full obligation rows
- equivalence/drift summaries and correspondence entries
- bridge/epsilon metrics
- final pass/fail + emission-blocked state

Commands:
- `vibec verify file.vibe --write-proof`
- `vibec compile file.vibe --write-proof`
- `vibec verify-proof file.vibe` (always writes proof)
- `vibec inspect-proof file.vibe.proof.json`

## Local-first intent registry (Phase 6.2)

Vibe now includes a **local-first intent registry** for indexing reusable intent contracts plus preservation metadata.

Pipeline surface:

`package/project -> manifest/proof/package metadata -> local registry entry -> search/inspect/compatibility -> build/use`

This phase is intentionally local and deterministic:
- registry root defaults to `./.vibe_registry` (or `VIBE_REGISTRY_ROOT`)
- entries are inspectable JSON files
- no hosted/public network registry, auth, or sync in this phase

Registry entries include:
- package identity (`name`, `version`, `description`)
- dependency and build summaries
- bridge defaults and emit defaults
- module inventory
- tags/domain metadata from `vibe.toml` `[metadata]`
- proof artifact presence/summary and proof-version metadata
- deterministic entry hash

CLI commands:
- `vibec publish <project-dir>`: publish into local registry only (honest local publication)
- `vibec search "<query>" [--tag ...] [--domain ...]`
- `vibec registry-inspect <package[@version]>`
- `vibec compat <package-ref-a> <package-ref-b>`

All registry commands support deterministic JSON output via `--report json`.

Compatibility output is a **deterministic hint matrix**, not a formal theorem of interchangeability.
Proof status is surfaced explicitly (`complete` / `partial` / `absent`) and never overclaimed.

These artifacts are deterministic and inspectable, but they are not overclaimed as full formal certificates.

## Language Server Protocol (Phase 6.3)

Vibe now includes an editor-native **Language Server Protocol** implementation.

Launch:
- `vibec lsp` (stdio server)
- `vibec lsp --check` (startup health check)

Current LSP surfaces:
- document sync (`didOpen`, `didChange`, `didSave`)
- diagnostics (parse + semantic/effect/resource/inference/agent/delegation + import checks)
- hover (intent-aware type/summary metadata)
- completion (keywords/blocks/bridge keys/import suggestions)
- go-to-definition (local symbols + basic module import targets)
- document symbols
- semantic tokens (major Vibe syntax classes)
- lightweight intent code lenses (bridge + semantic summaries)

Truthfulness boundaries:
- fast editor diagnostics are local and incremental
- deeper checks are save-oriented, not full heavy verification on each keystroke
- LSP hints do not replace compile-time preservation proof surfaces

## GitHub Actions native bridge check (Phase 6.4)

Vibe now includes an in-repo GitHub Action implementation for deterministic CI bridge gating.

Implemented action surfaces:
- root `action.yml` + local dogfood action at `.github/actions/bridge-check/action.yml`
- Python entrypoint: `.github/actions/bridge-check/run_bridge_check.py`
- local reproducible CLI helper: `vibec ci-check`

Core behavior:
- discovers `.vibe` files via configurable glob
- runs real Vibe verification per file
- writes deterministic JSON report + markdown summary
- appends markdown into `GITHUB_STEP_SUMMARY` when available
- supports merge-blocking fail-on gating (`verdict` rules and `bridge_score_below_threshold:<n>`)

Important truthfulness boundaries:
- this phase is native CI integration, not a hosted Vibe platform
- action is in-repo and publication as `vibe-lang/bridge-check@v1` is a future split/release step
- fail-on gating is implemented now; baseline-regression comparison remains optional future work

## Cross-domain intent architecture (Phase 7A)

Vibe now includes a shared **cross-domain architecture layer** for Phase 7 tracks:
- hardware
- scientific_simulation
- legal_compliance
- genomics

New architecture surfaces:
- domain profile subsystem: `vibe/domain_profiles.py`
- target plugin scaffolding: `vibe/target_plugins.py`
- IR domain metadata: active profile + domain summaries/issues/obligations + target metadata
- verifier/report/proof propagation of domain metadata
- CLI domain introspection: `vibec domains`, `vibec explain --show-domain`

Planned target scaffolds are now wired (truthfully marked as scaffold-level in this pass):
- `emit vhdl`
- `emit systemverilog`
- `emit julia`
- `emit compliance_report`
- `emit snakemake`
- `emit nextflow`

This pass establishes the shared foundation for parallel domain work; it does **not** claim full emitter/proof completeness for all domain targets yet.

## Multi-candidate synthesis (Phase 3.1)

Compile/verify can now generate and evaluate multiple deterministic candidate implementations from the same IR.

- default candidate count: `3`
- configurable via `--candidates N`
- strategies include standard, readability-biased, minimal-helper-light, and config-heavy variants
- every candidate is bridge-verified (obligations + backend + equivalence + calibration)

Selection behavior:
- rank candidates by an explicit deterministic formula
- select the best passing candidate for emission
- if none pass, emit nothing and fail compile

Reports and proof artifacts record:
- candidate count
- winning candidate
- ranking basis
- rejected candidate summaries

## Intent-guided test generation (Phase 3.2)

Compile and verify can now surface deterministic intent-guided test metadata, and compile can emit generated tests when requested.

- enable on compile: `--with-tests` (emits tests alongside generated code)
- enable on verify: `--with-tests` (reports projected deterministic test coverage without emitting files)
- deterministic output names:
  - Python: `test_<module>_intent.py`
  - TypeScript: `<module>.intent.test.ts`
- reports/proof artifacts include:
  - `test_generation_enabled`
  - `generated_test_files`
  - `preserve_rule_coverage`
  - `constraint_coverage`
  - `uncovered_items`
  - `partial_coverage_items`
  - `test_generation_notes`

## Bridge-gated refinement protocol (Phase 3.3)

Vibe compile now supports deterministic refinement rounds when initial synthesis fails preservation checks.

- enable with `--refine`
- bound rounds with `--max-iters N` (default `3`)
- refinement derives negative guidance from verifier/test surfaces:
  - violated or unknown-critical obligations
  - equivalence/drift misses
  - bridge/measurement shortfalls
  - uncovered/partial test-generation surfaces
  - backend error signals
- only passing refined candidates may emit
- when max iterations are exhausted without a pass, compile fails honestly and emits nothing

Reports and proof artifacts now include refinement metadata:
- `refinement_enabled`
- `refinement_iterations_run`
- `refinement_max_iterations`
- `refinement_success`
- `refinement_history`
- `refinement_failure_summary`
- `winning_iteration`

## Semantic intent diff (Phase 3.4)

Vibe now supports semantic diffing between two `.vibe` intent specs:

- `vibec diff old.vibe new.vibe`
- optional: `--report json`, `--show-unchanged`, `--summary-only`

This compares normalized semantic structures (IR-level intent surfaces), not emitted code.
It reports:

- semantic changes for goal/inputs/outputs/preserve/constraints/bridge/emit
- Tesla Victory Layer, Agentora, and AgentCeption deltas
- declaration deltas (`module`, `type`, `enum`, `interface`, `import`, `vibe_version`)
- deterministic change classifications and semantic polarity hints (`broadened`, `narrowed`, `unknown`)

Intent diff is a foundation for future semantic versioning; it does not replace bridge verification.

## Semantic types (Phase 4.1)

Vibe now includes a first-pass semantic type layer in addition to structural/base types.

- semantic qualifiers currently include:
  - `deterministic`
  - `secret_sensitive`
  - `latency_bounded`
  - `fallback_required`
  - `coherence_preserving`
  - `sovereignty_preserving`
  - `bridge_critical`
  - `intent_derived`
- qualifiers are derived from preserve/constraint/bridge/Tesla/Agentora/AgentCeption and intent IO roles
- qualifiers are serialized in IR and visible in verify/compile report surfaces
- qualifier-derived issues produce explicit semantic-type obligations; they do not replace bridge obligations

This is an intent-type foundation layer (not full theorem-proving or dependent typing).

## Effect types (Phase 4.2)

Vibe now adds first-pass effect types as a compile-time preservation surface.

- effect vocabulary includes:
  - `pure`
  - `io`
  - `stateful`
  - `nondeterministic`
  - `network`
  - `secret_exposing`
  - `fallback_path`
  - `bridge_critical_effect`
  - `unknown_effect`
- effects are inferred from preserve/constraints/bridge settings, semantic qualifiers, and orchestration surfaces
- effect mismatches (e.g. purity/stateless/determinism conflicts) produce explicit effect-type obligations
- effect summaries and issues are visible in IR, report, proof, and explain output

This is a deterministic compile-time effect profile, not full runtime behavioral proof.

## Resource types (Phase 4.3)

Vibe adds first-pass resource type profiling as another preservation surface.

- resource profiles are inferred from preserve/constraints/bridge/effect surfaces
- resource mismatch diagnostics become explicit resource-type obligations
- summaries/issues are visible in IR/report/proof/diff/explain

This is a deterministic estimate surface, not a runtime resource bound proof.

## Type inference from intent (Phase 4.4)

Vibe now performs deterministic type inference seeded from declared intent surfaces:

- intent input/output declarations
- preserve and constraint clauses
- bridge settings
- declaration surfaces (type/enum/interface/module where available)
- semantic/effect/resource summaries

Inference output is explicitly split into:

- declared types
- inferred bindings
- unresolved inference points
- inference-derived issues and obligations

Inference failures are preservation-surface diagnostics (intent violations), not opaque
internal compiler errors. This pass is intentionally partial and does not claim full
polymorphic/global theorem proving.

## Agent graphs as first-class syntax (Phase 5.1)

Vibe now supports first-class agent/orchestration syntax:

- `agent <Name>:` declarations with `role`, `receives`, `emits`, and per-agent `preserve`/`constraint`
- `orchestrate <Name>:` declarations with explicit graph edges and `on_error` fallback routing

This phase adds deterministic static graph modeling and checks:

- missing agent references and invalid edge targets
- boundary contract mismatch (`emits` vs downstream `receives`)
- fallback target validation (`fallback(TargetAgent)`)
- disconnected nodes and cycle detection (reported as unresolved runtime semantics in this phase)
- graph-derived obligations surfaced alongside existing preservation obligations

Agent orchestration is represented as inspectable compile-time metadata (IR/report/proof/diff/emitter),
not a full runtime autonomy implementation. This is the first formal Agentora/AgentCeption realization layer.

## Bridge propagation across agent boundaries (Phase 5.2)

Vibe now propagates preservation checks across agent edges (`A -> B`) with explicit boundary analysis.

- each edge computes deterministic boundary compatibility checks across:
  - emits/receives type contracts
  - semantic contract propagation
  - effect/resource compatibility
  - bridge-critical boundary conditions
- each edge receives a deterministic `edge_bridge_score`
- pipeline preservation uses a monotone aggregation rule:
  - `pipeline_bridge_score = product(edge_bridge_scores)`
- boundary issues become explicit `agent_boundary_*` obligations
- critical boundary failures block compile/emit through existing preservation gating

This phase is static bridge propagation for compile-time integrity, not runtime monitoring.

## AgentCeption: recursive delegation with proof inheritance (Phase 5.3)

Vibe now supports static recursive delegation declarations:

- `delegate Parent -> Child:` edges
- inheritance policy (`inherits: [preserve, constraint, bridge]`)
- optional recursion controls (`max_depth`, `stop_when`)

Proof inheritance model in this phase:

- child inherits parent preserve/constraint/bridge contracts by default
- child may strengthen inherited contracts
- child may not weaken critical inherited contracts (e.g. lower bridge thresholds, drop sovereignty guarantees)
- recursive chains without explicit depth/stop reasoning surface delegation risks

Delegation analysis is static and inspectable (IR/report/proof/diff/emitter metadata), and critical
contract-weakening violations participate in compile blocking through preservation gating.

## Runtime agent monitor / live bridge telemetry (Phase 5.4)

Vibe now emits runtime monitoring metadata and offline evaluation helpers:

- compile-time monitor config generated from agent graph/boundary/delegation contracts
- deterministic runtime event model (`agent_invocation_*`, `edge_transfer_observed`, `fallback_triggered`, etc.)
- runtime drift/threshold/fallback scoring against compiled contracts
- CLI evaluation via `vibec monitor-eval <proof> <events>` (alias: `vibec runtime-check`)

Important boundary:

- compile-time proof remains the governing truth surface
- runtime signals are observational drift checks against compiled contracts
- runtime evaluation does not rewrite compile-time obligations

This phase is monitor metadata + event evaluation (OpenTelemetry-compatible shape), not a full distributed runtime.

## Incremental compilation (Phase 1.4)

Vibe now includes deterministic local incremental compilation primitives for `compile`:

- cache directory: `.vibe_cache/` (next to source files)
- cache key material: source hash + typed SSA IR hash + emit target + compiler version
- cache reuse only when prior verification passed
- cache never overrides preservation truth

Compile flags:

- `--no-cache` disable cache for one compile
- `--clean-cache` clear the file cache record before compile

If cache metadata is corrupted, Vibe gracefully falls back to full revalidation and emission.

## Multi-target emission

Vibe now emits from the typed SSA IR through pluggable backends.

Current supported targets: `python`, `typescript`.

- Target selection comes from the source `emit` block.
- Experimental Tesla/Agentora/AgentCeption content lowers to structured config/stub output (no runtime autonomy).

## CLI usage

```bash
vibec explain vibe/examples/payment_router.vibe
vibec calibrate vibe/calibration_corpus/seed_corpus.json
vibec verify vibe/examples/payment_router.vibe
vibec verify vibe/examples/payment_router.vibe --write-proof
vibec verify vibe/examples/payment_router.vibe --candidates 3
vibec verify vibe/examples/payment_router.vibe --report json
vibec verify vibe/examples/sovereign_bridge.vibe --show-obligations
vibec verify vibe/examples/payment_router.vibe --backend heuristic
vibec verify vibe/examples/payment_router.vibe --backend smt
vibec verify vibe/examples/payment_router.vibe --backend smt --fallback-backend heuristic
vibec verify vibe/examples/payment_router.vibe --show-equivalence
vibec verify vibe/examples/payment_router.vibe --no-calibration
vibec verify vibe/examples/payment_router.vibe --with-tests --report json
vibec compile vibe/examples/payment_router.vibe
vibec compile vibe/examples/payment_router.vibe --report json
vibec compile vibe/examples/payment_router.vibe --backend heuristic
vibec compile vibe/examples/payment_router.vibe --backend smt
vibec compile vibe/examples/payment_router.vibe --show-equivalence
vibec compile vibe/examples/payment_router.vibe --no-calibration
vibec compile vibe/examples/payment_router.vibe --write-proof
vibec compile vibe/examples/payment_router.vibe --candidates 5
vibec compile vibe/examples/payment_router.vibe --with-tests
vibec compile vibe/examples/payment_router.vibe --refine
vibec compile vibe/examples/payment_router.vibe --refine --max-iters 5
vibec verify-proof vibe/examples/payment_router.vibe
vibec inspect-proof vibe/examples/payment_router.vibe.proof.json
vibec compile vibe/examples/edge_contract_ts.vibe --with-tests
vibec diff vibe/examples/payment_router.vibe vibe/examples/edge_contract_ts.vibe
vibec diff vibe/examples/payment_router.vibe vibe/examples/edge_contract_ts.vibe --report json
vibec explain vibe/examples/payment_router.vibe --show-types
vibec explain vibe/examples/payment_router.vibe --show-effects
```

## Bridge report output

Vibe reports:
- `epsilon_pre`, `epsilon_post`, `measurement_ratio`
- qixel metrics (`q_persistence`, `q_spatial_consistency`, `q_cohesion`, `q_alignment`, `q_intent_constant`)
- `petra_alignment`, `multimodal_resonance`
- `bridge_score`
- verdict class:
  - `FIELD_COLLAPSE_ERROR`
  - `ENTROPY_NOISE`
  - `EMPIRICAL_BRIDGE_ACTIVE`
  - `PETRA_BRIDGE_LOCK`
  - `MULTIMODAL_BRIDGE_STABLE`
- pass/fail

## Current limitations

- v0.1 grammar is intentionally small and hand-written.
- Emission currently supports `python` and `typescript` only.
- Verification is heuristic (deterministic and explainable), not a formal proof system.
- Generation includes TODO markers where ambiguity remains.

## Roadmap (short)

- richer grammar and diagnostics
- stronger semantic constraints and calibration hooks
- additional emit targets after compiler spine hardening
- optional hosted execution interfaces after core law stability

## Development

```bash
python -m pytest
```

## License

Vibe is licensed under **GNU AGPLv3 (AGPL-3.0-only)**.

This preserves reciprocity for modified versions, including when the software is offered as a hosted or network service.

Copyright (c) 2026 Michael Wave / Parallax


## GitHub Pages

Vibe includes a static public homepage under `docs/` for GitHub Pages deployment.

- Homepage source: `docs/index.html`
- Styles: `docs/styles.css`
- Favicon: `docs/assets/favicon.svg`

To publish manually in GitHub:
1. Go to **Settings → Pages**.
2. Set **Source** to **Deploy from a branch**.
3. Set **Branch** to `main` and **Folder** to `/docs`.
4. Save and wait for the publish URL.

> Note: the previous Actions-based Pages workflow has been disabled for now to avoid setup errors on repositories where Pages is not yet Actions-configured.



## Language Map

`Nevora -> Agentora -> AgentCeption -> Vibe`

- **Nevora**: translator lineage proving intent-to-starter-code workflows.
- **Agentora**: native orchestration layer for named specialist agents.
- **AgentCeption**: recursive delegation layer with inheritance and merge-preservation checks.
- **Vibe**: compiler-law system where emission is gated by bridge preservation.

## Experimental Modules

### Tesla Victory Layer (experimental.tesla.victory.layer)

Vibe includes an **experimental research/operational layer** for resonance-field modeling:
- `arc.tower.coherence`
- `life.ray.vitalize`
- `breath.cycle`

This module is bridge-gated and never bypasses founding-law checks. It adds Tesla-aware reporting fields (including sovereignty preservation) while remaining non-physical in emitted code (config/stubs only).

### Agentora + AgentCeption

As a tribute to the Agentora lineage and recursive agent-system influence:
- **Agentora** = native multi-agent orchestration declarations.
- **AgentCeption** = recursive delegation declarations with inheritance controls.

Both are Vibe-native and bridge-gated. Child delegation cannot bypass preservation law; verifier/report include delegation integrity metrics.
