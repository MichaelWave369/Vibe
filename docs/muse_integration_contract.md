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

### Snapshot verification mode (Phase 3A)

`vibec verify` now supports local content-addressed verification:

- `vibec verify --snapshot <sha256> --snapshot-store <dir> --report json`

Snapshot adapter behavior:

- resolves blobs from local store paths `<dir>/<sha256>` or `<dir>/<sha256>.vibe`
- re-hashes loaded content and enforces exact sha256 match
- fails machine-readably for:
  - `snapshot_not_found`
  - `snapshot_hash_mismatch`
  - `parse_error` / other input-resolution errors

Additive verify JSON fields in both path and snapshot mode:

- `input_mode` (`path` or `snapshot`)
- `snapshot_id` (`null` in path mode)
- `snapshot_store` (`null` in path mode)
- `provenance` (shared provenance object)
  - `input_mode`
  - `spec_path`
  - `snapshot_id`
  - `snapshot_store`

Proof linkage fields are also available in both legacy and grouped form:

- `proof_artifact_path`
- `proof_sha256`
- `proof.artifact_path`
- `proof.sha256`

In snapshot mode:

- `spec_path` is `null` (input is blob-addressed, not filesystem-path addressed)
- proof artifact writing uses deterministic snapshot-scoped output path in the snapshot store (`<store>/<sha256>.vibe.proof.json`)

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
Phase 2B hardens structural coverage and CI report artifact output.

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

Normalized conflict address format:

- `intent::<intent_name>::<section>::<key>`

Examples:

- `intent::PaymentRouter::bridge::epsilon_floor`
- `intent::PaymentRouter::preserve::latency`
- `intent::PaymentRouter::agent::Router`

Currently supported structural merge regions in this phase:

- core intent fields (`name`, `goal`, `inputs`, `outputs`, `emit`)
- preserve / constraint / bridge
- top-level declarations (`vibe_version`, `import`, `module`, `type`, `enum`, `interface`)
- `agentora` agent definitions
- `agentception` config

Important contract semantics:

- `merge_status = conflict` means structural/semantic merge compatibility could not be defended.
- `merge_status = merged` + `verification.passed = false` means merge succeeded structurally, but preservation thresholds were not met.
- A merge conflict is not the same as a merged-but-verification-failed result.

`--write-merge-report <path>` behavior:

- writes the machine-readable merge-verify JSON report artifact to disk
- writes for merged, conflict, and error outcomes
- does not imply merge success; check `merge_status` and `verification`

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

Phase 3B adds deterministic input provenance:

- `provenance.input_mode` (`"path"` or `"snapshot"`)
- `provenance.spec_path` (path mode path, `null` in snapshot mode)
- `provenance.snapshot_id` (`null` in path mode)
- `provenance.snapshot_store` (`null` in path mode)

No synthetic path provenance is emitted for snapshot-mode verification.

## `vibec snapshot-put <path>`

Phase 3B adds a local snapshot writer command:

- `vibec snapshot-put <path> [--snapshot-store <dir>] [--report json]`

Machine-readable output (`--report json`) fields:

- `schema_version` (`"v1"`)
- `report_type` (`"snapshot_put"`)
- `snapshot_id`
- `snapshot_store`
- `blob_path`
- `already_present`

This command is local content-addressed storage only; it is not a remote Muse object-store API.

## Snapshot seam

`vibe.verification_flow.prepare_verification_input(...)` supports both:

- path-based source loading, and
- in-memory source loading (`source_text` + `source_name`)

This powers real local snapshot verification (`verify --snapshot ...`) and local snapshot writes (`snapshot-put`), while remaining explicitly local (not a remote object-store integration).

## External obligation registration seam (Phase 4A)

Vibe exposes a controlled Python-level registry for external obligation providers:

- `register_external_obligation_provider(category, provider, override=False)`
- `unregister_external_obligation_provider(category)`
- `list_external_obligation_categories()`

Provider shape:

- input: `ExternalObligationContext` (IR + generated code + observed scalar/bool/symbol facts)
- output: list of `ExternalObligation` rows (`obligation_id`, `category`, `description`, `status`, `source_location`, `evidence`, `critical`)

Contract behavior:

- external obligations flow through existing obligation surfaces (`verify` JSON `obligations[]`, proof artifact `obligations[]`, rollups),
- schema versions remain unchanged (`v1`) because this is additive and uses existing obligation row shape,
- registration is explicit and deterministic (category-keyed, duplicate rejection unless `override=True`),
- no auto-discovery, no remote plugin loading, no plugin marketplace semantics in this phase.

Current scoring scope:

- external obligations contribute to obligation rows and status counts,
- they only affect pass/fail where the existing verifier model already applies (`critical` violated/unknown obligations block pass),
- no additional bridge-score math is introduced for external obligations in this phase.
