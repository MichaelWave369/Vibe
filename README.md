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
vibec verify vibe/examples/payment_router.vibe --report json
vibec verify vibe/examples/sovereign_bridge.vibe --show-obligations
vibec verify vibe/examples/payment_router.vibe --backend heuristic
vibec verify vibe/examples/payment_router.vibe --backend smt
vibec verify vibe/examples/payment_router.vibe --backend smt --fallback-backend heuristic
vibec verify vibe/examples/payment_router.vibe --show-equivalence
vibec verify vibe/examples/payment_router.vibe --no-calibration
vibec compile vibe/examples/payment_router.vibe
vibec compile vibe/examples/payment_router.vibe --report json
vibec compile vibe/examples/payment_router.vibe --backend heuristic
vibec compile vibe/examples/payment_router.vibe --backend smt
vibec compile vibe/examples/payment_router.vibe --show-equivalence
vibec compile vibe/examples/payment_router.vibe --no-calibration
vibec compile vibe/examples/edge_contract_ts.vibe
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
