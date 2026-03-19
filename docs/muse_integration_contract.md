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

Each `ops[]` row includes:

- `op`, `address`, `field`, `old_value`, `new_value`
- `semantic_polarity` (`broadened`, `narrowed`, `unknown`)
- `bridge_impact` (`null` when not derivable yet)
- `severity`

Legacy `summary` + `changes` are retained for compatibility.

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
