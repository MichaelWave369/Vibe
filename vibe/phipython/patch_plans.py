from __future__ import annotations

import json
from pathlib import Path

from .patch import preview_safe_patch
from .scaffold_metadata import PHIPYTHON_METADATA_FILE, read_metadata


def _file_entry(path: Path, patch_type: str, before: str, after: str) -> dict[str, object]:
    return {
        "path": str(path),
        "patch_type": patch_type,
        "preview": {"before": before, "after": after},
    }


def list_patch_plans(target_file: Path) -> dict[str, object]:
    plans: list[dict[str, object]] = []
    project_dir = target_file.parent
    source_text = target_file.read_text(encoding="utf-8")
    metadata = read_metadata(project_dir)

    single = preview_safe_patch(target_file)
    if single["can_apply"]:
        files = [_file_entry(target_file, str(single["patch_type"]), str(single["preview"]["before"]), str(single["preview"]["after"]))]
        if metadata is not None:
            before_meta = json.dumps(metadata, indent=2, sort_keys=True)
            updated = dict(metadata)
            updated.setdefault("last_patch_type", str(single["patch_type"]))
            after_meta = json.dumps(updated, indent=2, sort_keys=True)
            files.append(_file_entry(project_dir / PHIPYTHON_METADATA_FILE, "metadata_update", before_meta, after_meta))
        plans.append(
            {
                "plan_id": "plan-001",
                "can_apply": True,
                "summary": f"Apply `{single['patch_type']}` and optionally update scaffold metadata.",
                "files": files,
                "confidence": "high",
                "notes": ["Narrow deterministic plan with per-file previews."],
            }
        )

    if "def main(" in source_text and not (project_dir / "README.md").exists():
        plans.append(
            {
                "plan_id": "plan-002",
                "can_apply": True,
                "summary": "Add minimal README for main-entry scaffold.",
                "files": [
                    _file_entry(
                        project_dir / "README.md",
                        "readme_stub",
                        "",
                        "# Project\n\nGenerated README stub for bounded scaffold health checks.\n",
                    )
                ],
                "confidence": "high",
                "notes": ["Bounded README stub insertion."],
            }
        )

    env_expected = bool(metadata and any(tag in str(metadata.get("template", "")) for tag in ("api_tool", "flask_app", "automation")))
    if env_expected and not (project_dir / ".env.example").exists():
        plans.append(
            {
                "plan_id": "plan-003",
                "can_apply": True,
                "summary": "Add bounded .env.example stub for env-based starter scaffolds.",
                "files": [
                    _file_entry(
                        project_dir / ".env.example",
                        "env_example_stub",
                        "",
                        "API_KEY=replace_me\n",
                    )
                ],
                "confidence": "high",
                "notes": ["Generated because scaffold metadata indicates an env-based starter."],
            }
        )

    if not plans:
        return {
            "target": str(target_file),
            "plans": [],
            "rejection_reason": "No deterministic bounded multi-file plan matched this target.",
            "notes": ["No eligible multi-file safe patch plan found."],
        }

    return {
        "target": str(target_file),
        "plans": plans,
        "notes": ["Patch plans are narrow, preview-first, and deterministic."],
    }


def preview_patch_plan(target_file: Path, plan_id: str) -> dict[str, object]:
    listing = list_patch_plans(target_file)
    for plan in listing["plans"]:
        if plan["plan_id"] == plan_id:
            return plan
    return {
        "plan_id": plan_id,
        "can_apply": False,
        "summary": "Unknown patch plan id.",
        "files": [],
        "confidence": "low",
        "rejection_reason": "Requested plan id was not listed for this target.",
        "notes": ["Use --interactive to list available plan ids."],
    }


def apply_patch_plan(target_file: Path, plan_id: str, apply: bool = False) -> dict[str, object]:
    plan = preview_patch_plan(target_file, plan_id)
    plan["applied"] = False
    if apply and plan.get("can_apply"):
        for file_entry in plan.get("files", []):
            file_path = Path(str(file_entry["path"]))
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(str(file_entry["preview"]["after"]), encoding="utf-8")
        plan["applied"] = True
        plan.setdefault("notes", []).append("Plan applied with explicit --apply.")
    elif apply:
        plan.setdefault("notes", []).append("--apply requested for ineligible/unknown plan.")
    else:
        plan.setdefault("notes", []).append("Preview-only plan mode.")
    return plan
