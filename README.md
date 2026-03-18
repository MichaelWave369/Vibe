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
