from __future__ import annotations

import json
from pathlib import Path

from .doctor import doctor_project, inspect_project
from .receipts import list_receipts
from .scaffold_metadata import PHIPYTHON_METADATA_FILE
from .test_profiles import TEST_MANIFEST_FILE
from .testgen import read_test_manifest


def create_review_bundle(project_path: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)

    doctor_payload = doctor_project(project_path)
    inspect_payload = inspect_project(project_path)
    receipts_payload = list_receipts(project_path)
    test_manifest = read_test_manifest(project_path)

    artifact_map = {
        "doctor": out_dir / "doctor.json",
        "inspect": out_dir / "inspect_project.json",
        "receipts": out_dir / "receipts.json",
        "test_manifest": out_dir / "test_manifest.json",
        "summary": out_dir / "review_summary.md",
    }

    artifact_map["doctor"].write_text(json.dumps(doctor_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_map["inspect"].write_text(json.dumps(inspect_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_map["receipts"].write_text(json.dumps(receipts_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_map["test_manifest"].write_text(json.dumps(test_manifest or {}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    metadata_snapshot = None
    metadata_path = project_path / PHIPYTHON_METADATA_FILE
    if metadata_path.exists():
        metadata_snapshot = out_dir / PHIPYTHON_METADATA_FILE
        metadata_snapshot.write_text(metadata_path.read_text(encoding="utf-8"), encoding="utf-8")

    summary = [
        "# PhiPython Review Bundle",
        "",
        "Local review artifacts only; not proof of correctness.",
        f"- project: {project_path}",
        f"- doctor status: {doctor_payload.get('status', 'unknown')}",
        f"- receipts: {len(receipts_payload)}",
        f"- has test manifest: {bool(test_manifest)}",
        f"- test manifest file: {TEST_MANIFEST_FILE}",
    ]
    artifact_map["summary"].write_text("\n".join(summary) + "\n", encoding="utf-8")

    return {
        "bundle_dir": str(out_dir),
        "artifacts": {k: str(v) for k, v in artifact_map.items()},
        "metadata_snapshot": str(metadata_snapshot) if metadata_snapshot else None,
        "notes": ["Bundle is local-only and intended for operator review."],
    }
