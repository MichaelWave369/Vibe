# Vibe (v0.1)

**Vibe** is an intent-first programming language and compiler prototype.

Its governing philosophy is simple:

> A program is valid only if the generated implementation preserves intent above the bridge threshold.

Instead of treating code generation as complete once syntax is valid, Vibe treats compilation as an **intent preservation contract**.

## Why intent preservation matters

Traditional toolchains verify syntax and type correctness but often miss semantic drift between a specification and an implementation. Vibe adds a semantic bridge verifier that estimates whether generated output still respects the original intent, preservation rules, and constraints.

If the bridge fails, compile fails.

## Founding law

Vibe v0.1 bakes in two baseline thresholds:

- `epsilon_floor = 0.02`
- `measurement_safe_ratio = 0.85`

Compilation fails when either condition is true:

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

## CLI usage

Install in editable mode:

```bash
python -m pip install -e .
```

Compile:

```bash
vibec compile vibe/examples/payment_router.vibe
```

Explain (AST + normalized IR + preservation reasoning):

```bash
vibec explain vibe/examples/payment_router.vibe
```

Verify without emitting code:

```bash
vibec verify vibe/examples/payment_router.vibe
```

## Bridge report

Each verifier run prints:

- `eps_pre`
- `eps_post`
- `M_eps`
- qixel metrics (`q_persistence`, `q_spatial_consistency`, `q_cohesion`, `q_alignment`, `q_intent_constant`)
- `petra_alignment`
- `multimodal_resonance`
- `bridge_score`
- verdict classification:
  - `FIELD_COLLAPSE_ERROR`
  - `ENTROPY_NOISE`
  - `EMPIRICAL_BRIDGE_ACTIVE`
  - `PETRA_BRIDGE_LOCK`
  - `MULTIMODAL_BRIDGE_STABLE`
- pass/fail status

## Current limitations (v0.1)

- Hand-written parser with a deliberately small grammar.
- Only `emit python` is supported.
- Verifier metrics are deterministic heuristics, not formal proofs.
- Generated implementations include TODOs for unresolved ambiguity and deeper domain adapters.

## Roadmap (v0.2)

- More complete grammar and richer typing.
- Source spans + diagnostics with fix hints.
- Multiple emit targets (e.g., TypeScript).
- Constraint solver hooks and stronger semantic checks.
- Pluggable bridge metric calibrators for domain-specific validation.

## License

MIT — see LICENSE.

