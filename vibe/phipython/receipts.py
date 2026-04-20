from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

RECEIPTS_DIR_NAME = ".phipython_receipts"
RECEIPT_VERSION = "1.0"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_patch_receipt(payload: dict[str, object], receipt_type: str, target: Path) -> dict[str, object]:
    preview = payload.get("preview", {"before": "", "after": ""})
    before = str(preview.get("before", ""))
    after = str(preview.get("after", ""))
    status = "rejected"
    if payload.get("can_apply"):
        status = "applied" if payload.get("applied") else "previewed"
    return {
        "receipt_type": receipt_type,
        "receipt_version": RECEIPT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": str(target),
        "patch_type": payload.get("patch_type", ""),
        "status": status,
        "confidence": payload.get("confidence", "low"),
        "notes": payload.get("notes", []),
        "before_hash": _sha(before),
        "after_hash": _sha(after),
        "preview": {"before": before, "after": after},
    }


def build_plan_receipt(payload: dict[str, object], target: Path) -> dict[str, object]:
    entries = []
    for file_entry in payload.get("files", []):
        preview = file_entry.get("preview", {"before": "", "after": ""})
        before = str(preview.get("before", ""))
        after = str(preview.get("after", ""))
        entries.append(
            {
                "path": file_entry.get("path", ""),
                "patch_type": file_entry.get("patch_type", ""),
                "before_hash": _sha(before),
                "after_hash": _sha(after),
            }
        )
    status = "rejected"
    if payload.get("can_apply"):
        status = "applied" if payload.get("applied") else "previewed"
    return {
        "receipt_type": "patch_plan",
        "receipt_version": RECEIPT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": str(target),
        "plan_id": payload.get("plan_id", ""),
        "status": status,
        "confidence": payload.get("confidence", "low"),
        "notes": payload.get("notes", []),
        "files": entries,
    }


def write_receipt(base_path: Path, receipt: dict[str, object]) -> Path:
    folder = base_path / RECEIPTS_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    key = f"{receipt.get('receipt_type','receipt')}_{receipt.get('status','unknown')}"
    out = folder / f"{key}.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def list_receipts(base_path: Path) -> list[dict[str, object]]:
    folder = base_path / RECEIPTS_DIR_NAME
    if not folder.exists():
        return []
    rows: list[dict[str, object]] = []
    for item in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(item.read_text(encoding="utf-8"))
            payload["_path"] = str(item)
            rows.append(payload)
        except json.JSONDecodeError:
            continue
    return rows
