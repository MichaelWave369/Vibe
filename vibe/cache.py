"""Incremental compilation cache primitives for Vibe Phase 1.4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class CacheRecord:
    source_path: str
    source_hash: str
    ir_hash: str
    target: str
    compiler_version: str
    output_path: str
    verification_passed: bool
    bridge_score: float


@dataclass(slots=True)
class CacheDecision:
    status: str
    record: CacheRecord | None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_dir_for(source_path: Path) -> Path:
    return source_path.parent / ".vibe_cache"


def cache_key_for(source_path: Path) -> str:
    normalized = str(source_path.resolve())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def cache_record_path(source_path: Path) -> Path:
    return cache_dir_for(source_path) / f"{cache_key_for(source_path)}.json"


def load_cache_record(source_path: Path) -> CacheDecision:
    path = cache_record_path(source_path)
    if not path.exists():
        return CacheDecision(status="cache_miss", record=None)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        record = CacheRecord(**raw)
        return CacheDecision(status="cache_hit_metadata", record=record)
    except Exception:
        return CacheDecision(status="cache_corrupt", record=None)


def save_cache_record(source_path: Path, record: CacheRecord) -> None:
    cdir = cache_dir_for(source_path)
    cdir.mkdir(parents=True, exist_ok=True)
    cache_record_path(source_path).write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8"
    )


def clear_cache(source_path: Path) -> None:
    cpath = cache_record_path(source_path)
    if cpath.exists():
        cpath.unlink()
