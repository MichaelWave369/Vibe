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

## CLI usage

```bash
vibec explain vibe/examples/payment_router.vibe
vibec verify vibe/examples/payment_router.vibe
vibec verify vibe/examples/payment_router.vibe --report json
vibec compile vibe/examples/payment_router.vibe
vibec compile vibe/examples/payment_router.vibe --report json
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
- Only `emit python` is supported.
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
