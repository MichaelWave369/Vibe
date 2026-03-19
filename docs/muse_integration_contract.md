# Muse × Vibe kickoff contract (Issue #34, phase 1a)

This repository now exposes a **versioned machine-readable JSON contract** for Muse-side integration.

## `vibec verify --report json`

Top-level contract fields:

- `schema_version` (`"v1"`)
- `report_type` (`"verify"`)
- `spec_path`
- `bridge_score`
- `epsilon_post`
- `measurement_ratio`
- `epsilon_floor`
- `measurement_safe_ratio`
- `obligations_total`
- `obligations_satisfied`
- `obligations` (machine-readable rows)
- `proof_artifact_path` (if `--write-proof`)
- `proof_sha256` (if artifact exists)

Each `obligations[]` row includes:

- `id`, `category`, `address`, `status`, `message`, `severity`
- optional placeholders: `expected`, `observed`

The payload also preserves legacy top-level verification fields for compatibility.

## `vibec diff --report json`

Top-level contract fields:

- `schema_version` (`"v1"`)
- `report_type` (`"diff"`)
- `old_spec`, `new_spec`
- `drift_score`
- `ops`
- `verification_context`

Each `ops[]` row includes:

- `op`, `address`, `field`, `old_value`, `new_value`
- `semantic_polarity` (`broadened`, `narrowed`, `unknown`)
- `bridge_impact` (`null` when not derivable yet)
- `bridge_impact_source` (deterministic derivation source tag, or `null`)
- `severity`

Legacy `summary` + `changes` are retained for compatibility.

### Whole-spec `verification_context` (Phase 1C)

`verification_context` is **top-level old/new verification metadata**. It is not op-local causality.

Current shape:

- `verification_requested` (boolean)
- `available` (boolean)
- `reason` (`null` when available, explanatory string when unavailable)
- `old`/`new` summaries (`null` when unavailable)
- `bridge_score_delta` (`new.bridge_score - old.bridge_score`, or `null` when unavailable)

`old` and `new` summaries include:

- `bridge_score`
- `epsilon_post`
- `measurement_ratio`
- `epsilon_floor`
- `measurement_safe_ratio`
- `obligations_total`
- `obligations_satisfied`

Availability behavior:

- `vibec diff --report json --with-verification-context` => context attempted; if successful, `available = true`
- default (`vibec diff --report json` without flag) => `available = false` with explicit disabled reason
- internal verification failures are surfaced as `available = false` with an explanatory reason

## `vibec merge-verify <base> <left> <right>`

Phase 2A adds a first real three-way merge + verify surface.

Top-level JSON fields:

- `schema_version` (`"v1"`)
- `report_type` (`"merge_verify"`)
- `base_spec`, `left_spec`, `right_spec`
- `merge_status` (`merged`, `conflict`, `error`)
- `merged_text` (only when merged)
- `verification` (only when merged)
- `conflicts` (structured list on conflict)
- `error` (for parse/runtime failures)

Conflict rows include:

- `address`
- `conflict_type`
- `base_value`
- `left_value`
- `right_value`
- `message`
- `severity`

Important contract semantics:

- `merge_status = conflict` means structural/semantic merge compatibility could not be defended.
- `merge_status = merged` + `verification.passed = false` means merge succeeded structurally, but preservation thresholds were not met.
- A merge conflict is not the same as a merged-but-verification-failed result.

### `bridge_impact` semantics (Phase 1B)

`bridge_impact` is a deterministic signed delta where:

- positive => stronger bridge guarantees inferred
- negative => weakened bridge guarantees inferred
- `null` => Vibe cannot honestly attribute impact for that op yet

Currently populated for:

- bridge threshold deltas (`epsilon_floor`, `measurement_safe_ratio`)
- preserve add/remove and preserve modified with known broadened/narrowed polarity
- constraint add/remove (with stronger negative impact for sovereignty-like removals)

Still `null` for classes where Vibe cannot defensibly infer op-local bridge impact (for example some goal/shape changes without a grounded attribution path).

## `.vibe.proof.json`

Proof artifacts are now explicitly versioned with:

- `schema_version` (`"v1"`)
- `artifact_version` (`"v1"`)

Artifact metadata remains deterministic and includes source hashes, backend metadata, bridge/equivalence summaries, obligations, and subsystem summaries.

## Snapshot seam (future `--snapshot <hash>`)

`vibe.verification_flow.prepare_verification_input(...)` supports both:

- path-based source loading, and
- in-memory source loading (`source_text` + `source_name`)

This provides the internal seam required for future snapshot/object-store verification wiring, without shipping a fake object-store CLI feature in this pass.
