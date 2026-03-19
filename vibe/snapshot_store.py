"""Local content-addressed snapshot adapter for verify --snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re

from .cache import sha256_text

DEFAULT_SNAPSHOT_STORE = Path(".vibe_snapshots")


class SnapshotResolutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ResolvedSnapshot:
    snapshot_id: str
    store_path: Path
    blob_path: Path
    source_text: str


def default_snapshot_store() -> Path:
    env = os.environ.get("VIBE_SNAPSHOT_STORE", "").strip()
    return Path(env) if env else DEFAULT_SNAPSHOT_STORE


def _validate_snapshot_id(snapshot_id: str) -> str:
    sid = snapshot_id.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sid):
        raise SnapshotResolutionError("invalid_snapshot_id", "snapshot id must be a 64-char sha256 hex string")
    return sid


def resolve_snapshot(snapshot_id: str, store: Path | None = None) -> ResolvedSnapshot:
    sid = _validate_snapshot_id(snapshot_id)
    store_path = (store or default_snapshot_store()).resolve()
    candidates = [store_path / sid, store_path / f"{sid}.vibe"]
    blob_path = next((p for p in candidates if p.exists() and p.is_file()), None)
    if blob_path is None:
        raise SnapshotResolutionError(
            "snapshot_not_found",
            f"snapshot `{sid}` was not found in store `{store_path}`",
        )

    source_text = blob_path.read_text(encoding="utf-8")
    observed = sha256_text(source_text)
    if observed != sid:
        raise SnapshotResolutionError(
            "snapshot_hash_mismatch",
            f"snapshot hash mismatch: requested `{sid}`, observed `{observed}`",
        )

    return ResolvedSnapshot(snapshot_id=sid, store_path=store_path, blob_path=blob_path, source_text=source_text)
