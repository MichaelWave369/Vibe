# Vibe

**Mission:** make intent the source code and preserve it through compilation.

Vibe is an **intent-first language and compiler**. A compile is accepted only when verification reports that emitted artifacts preserve intent above the configured bridge threshold.

---

## What Vibe is

Vibe is a local-first compiler toolchain around `.vibe` specs.

Pipeline:

`intent spec (.vibe) -> parse -> typed IR -> verify -> proof/report -> emit`

Core law:

- **Intention is source code.**
- **Preservation is compilation truth.**

If preservation checks fail, emission is blocked.

---

## Current status (implemented phases snapshot)

Vibe currently includes:

- **Phase 1.x** parser + typed IR foundations.
- **Phase 2.x** verification obligation surfaces, backend abstraction, SMT-ready slice, and semantic correspondence reporting.
- **Phase 3.x** deterministic emit targets and reporting improvements.
- **Phase 4.x** calibration and proof artifacts.
- **Phase 5.x** package manifest/build foundations.
- **Phase 6.2** local-first intent registry (`publish/search/registry-inspect/compat`).
- **Phase 6.3** local LSP server.
- **Phase 6.4** CI bridge-check integration (including GitHub Actions bridge-check action).
- **Phase 7A–7.4** cross-domain profiles and initial hardware/scientific/legal/genomics slices.
- **Phase 8.1** bounded self-hosting self-check.
- **Phase 8.2** semver derivation from semantic intent diff.
- **Phase 8.3** intent negotiation protocol.
- **Phase 8.4** intent-as-interchange layer (`interchange-from-text`, `intent-brief`, `proof-brief`) for bounded NL->`.vibe` scaffolding and machine-consumable proof summaries.
- Initial standard-library package set (`vibe_http`, `vibe_payment`, `vibe_vector`, `vibe_agent`) as reusable intent contracts.

This is still a prototype compiler with bounded slices, not complete language coverage.

---

## Quickstart

```bash
python -m pip install -e .
```

Verify an intent spec:

```bash
vibec verify vibe/examples/payment_router.vibe
```

Compile when preservation passes:

```bash
vibec compile vibe/examples/payment_router.vibe
```

Generate proof artifact explicitly:

```bash
vibec verify-proof vibe/examples/payment_router.vibe
```

Run tests:

```bash
python -m pytest -q
```

---

## CLI overview

Primary commands:

- `vibec compile <file.vibe>` — verify + emit when preservation passes.
- `vibec verify <file.vibe>` — verification only.
- `vibec verify-proof <file.vibe>` — verification + proof artifact write.
- `vibec inspect-proof <file.vibe.proof.json>` — inspect proof summary.
- `vibec diff <old.vibe> <new.vibe>` — semantic intent diff.
- `vibec merge-verify <base.vibe> <left.vibe> <right.vibe>` — conservative three-way merge + verification.
- `vibec semver <old.vibe> <new.vibe>` — derive recommended semver bump.
- `vibec negotiate <a.vibe> <b.vibe> ...` — deterministic contract negotiation.
- `vibec init` / `manifest-check` / `build` — package lifecycle.
- `vibec publish` / `search` / `registry-inspect` / `compat` — local registry operations.
- `vibec lsp` — local LSP server over stdio.
- `vibec ci-check` — deterministic CI bridge checks.
- `vibec self-check` — bounded self-hosting check.
- `vibec domains` — list domain profiles.
- `vibec stdlib-list` — list built-in standard-library packages in `stdlib/`.
- `vibec interchange-from-text <requirements.txt>` — deterministic NL-to-`.vibe` interchange scaffold artifact.
- `vibec intent-brief <file.vibe>` — deterministic machine-readable intent brief.
- `vibec proof-brief <file.vibe.proof.json>` — deterministic machine-readable consumer proof brief.

---

## Language pipeline and architecture

Current compile/report spine:

1. Parse `.vibe` source into AST.
2. Lower to typed IR.
3. Generate verification obligations from preserve/constraint/bridge/domain metadata.
4. Evaluate obligations with configured backend(s).
5. Compute bridge/preservation outcome.
6. Produce report + optional proof artifact.
7. Emit target artifact only when gate passes.

The architecture is deterministic-by-default for local reproducibility.

---

## Verification, proofs, and calibration (truthful scope)

What exists now:

- Machine-checkable obligation outcomes and preservation gate decisions.
- Deterministic proof artifact output (`.vibe.proof.json`) with hashes, backend metadata, summaries, and evidence surfaces.
- Optional empirical calibration path for epsilon estimation.
- Runtime monitor metadata surfaces.

What this is **not**:

- Not full formal verification of arbitrary program semantics.
- Not complete theorem proving across all language features.

When this README says “proof,” it refers to **current machine-checkable proof metadata produced by Vibe’s implemented verifier/proof pipeline**.

### Muse integration JSON contract (Issue #34 kickoff)

For the Vibe-side integration contract consumed by Muse (`verify --report json`, `diff --report json`, and `.vibe.proof.json` schema/versioning), see `docs/muse_integration_contract.md`.

---

## Package manager, registry, LSP, and CI

### Package manager

Vibe packages use `vibe.toml` and package-local module graphs.

Key flows:

- `vibec manifest-check <path-or-manifest>`
- `vibec build <path-or-manifest>`

### Local registry

Vibe includes a local-first filesystem registry.

Key flows:

- `vibec publish <project-dir>`
- `vibec search <query>`
- `vibec registry-inspect <package[@version]>`
- `vibec compat <packageA[@version]> <packageB[@version]>`

Registry entries include package metadata and proof-status surfaces from the current pipeline.

### LSP

Vibe includes a stdio Language Server for editor integration (diagnostics, symbols, completion/hover slices, semantic tokens).

### CI

`vibec ci-check` provides deterministic bridge-check outputs for local CI and GitHub Actions usage.

---

## Cross-domain support summary

Implemented domain profile slices include:

- hardware
- scientific simulation
- legal/compliance
- genomics

These currently provide bounded, deterministic metadata/check/emitter surfaces and are intended to expand iteratively.

---

## Ecosystem: initial standard library

Vibe now includes an initial **standard library of reusable intent packages** under `stdlib/`.

Current packages:

- `stdlib/vibe_http`
- `stdlib/vibe_payment`
- `stdlib/vibe_vector`
- `stdlib/vibe_agent`

Design intent:

- packages are reusable **intent contracts**, not generic helper-code dumps,
- packages participate in normal `manifest-check/build/verify-proof/publish` flows,
- package metadata is registry-visible,
- proof metadata is machine-checkable through the existing verifier/proof pipeline.

Example flows:

```bash
vibec manifest-check stdlib/vibe_http --report json
vibec build stdlib/vibe_http --report json
vibec verify-proof stdlib/vibe_http/src/main.vibe --report json
vibec publish stdlib/vibe_http --report json
vibec search http --report json
vibec registry-inspect vibe_http@0.1.0 --report json
vibec stdlib-list --report json
```

Scope note: this is an initial, bounded standard library. Coverage will expand in future phases.

---

## Intent as universal intermediate language (Phase 8.4 roadmap alignment)

Vibe now treats `.vibe` as an interchange contract between humans/LLMs/agents and downstream compilers/proof consumers.

Implemented bounded interchange slice:

- `vibec interchange-from-text <requirements.txt>` builds a deterministic NL-to-`.vibe` interchange artifact (scaffold, not autonomous correctness magic).
- `vibec intent-brief <file.vibe>` exports a deterministic machine-readable intent contract summary.
- `vibec proof-brief <file.vibe.proof.json>` exports a deterministic machine-readable consumer brief from proof data.

This enables the roadmap pipeline:

`natural language requirement -> interchange artifact -> .vibe intent contract -> verify/prove -> machine-consumable proof brief`.

Truthfulness boundaries:

- no live hosted LLM provider integration in this phase,
- no claim of perfect natural-language understanding,
- no claim that proof brief equals complete formal behavioral proof.

---

## Self-hosting, semver, and negotiation

- **Self-hosting (8.1):** bounded compiler self-check with baseline/regression surfaces.
- **Semver (8.2):** semantic intent diff drives recommended version bump categories.
- **Negotiation (8.3):** deterministic merged intent contracts + explicit conflict reporting.

These are integrated with the CLI and intended to support local-first release governance.

---

## Repository layout

- `vibe/` — compiler, verifier, emitters, registry, CLI, domain slices, LSP.
- `stdlib/` — standard-library packages (Phase 8.4).
- `tests/` — unit/integration tests.
- `.github/actions/bridge-check/` — native bridge-check action.
- `.github/workflows/` — CI workflow examples.
- `docs/` — project site (`docs/index.html`).
- `self_hosting/` — bounded self-hosting specs/artifacts.

---

## Current boundaries and non-goals

- Vibe is not claiming full formal verification across all emitted behaviors.
- Vibe is not claiming complete self-bootstrap yet.
- Vibe stdlib is intentionally small in this phase (4 packages).
- Domain slices are bounded and intentionally incremental.

The project prioritizes deterministic, inspectable preservation surfaces over broad but unverifiable feature claims.

---

## Roadmap / next steps

Near-term:

- Expand stdlib package set and inter-package contract surfaces.
- Broaden semver and compatibility rule coverage.
- Deepen negotiation rules for richer multi-party contracts.
- Continue hardening verifier backends and diagnostics.
- Expand bounded self-hosting slices toward fuller compiler coverage.

---

## License

See `LICENSE`.
