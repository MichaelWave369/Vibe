from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .doctor_profiles import DoctorCheck, baseline_checks, template_profile_checks
from .scaffold_metadata import read_metadata
from .templates import get_template, list_templates


def _guess_template(path: Path, metadata: dict[str, object] | None) -> str:
    if metadata and isinstance(metadata.get("template"), str):
        return str(metadata["template"])

    files = {p.name for p in path.glob("*")}
    if "app.py" in files and ".env.example" in files:
        return "flask_app"
    if "examples" in files and (path / "examples" / "sample.csv").exists():
        return "dashboard"
    if "requirements.txt" in files and "requests" in (path / "requirements.txt").read_text(encoding="utf-8"):
        return "api_tool"
    if "tests" in files and (path / "tests" / "test_parser.py").exists():
        return "cli"
    return "unknown"


def doctor_project(path: Path, template_profile: str | None = None) -> dict[str, object]:
    checks: list[DoctorCheck] = []
    metadata = read_metadata(path)
    guess = template_profile or _guess_template(path, metadata)

    if not path.exists() or not path.is_dir():
        checks.append(
            DoctorCheck(
                id="path.exists",
                status="fail",
                summary="Project path is missing or not a directory.",
                details=str(path),
                suggested_action="Run doctor on an existing scaffold directory.",
            )
        )
        return {
            "path": str(path),
            "template_guess": guess,
            "status": "fail",
            "checks": [asdict(c) for c in checks],
            "notes": ["Doctor is bounded scaffold validation only."],
        }

    checks.extend(baseline_checks(path, metadata_present=metadata is not None))

    req_text = (path / "requirements.txt").read_text(encoding="utf-8") if (path / "requirements.txt").exists() else ""
    checks.extend(template_profile_checks(path, template=guess, req_text=req_text))

    template = get_template(guess)
    if template is not None:
        missing = [rel for rel in template.files if not (path / rel).exists()]
        checks.append(
            DoctorCheck(
                id="template.expected_files",
                status="pass" if not missing else "warn",
                summary="Template file consistency check.",
                details="All expected template files present." if not missing else f"Missing files: {', '.join(sorted(missing))}",
                suggested_action="Restore missing scaffold files if still required.",
            )
        )

    status = "ok"
    if any(c.status == "fail" for c in checks):
        status = "fail"
    elif any(c.status == "warn" for c in checks):
        status = "warn"

    return {
        "path": str(path),
        "template_guess": guess,
        "status": status,
        "checks": [asdict(c) for c in checks],
        "notes": [
            "Doctor profiles are bounded starter/template checks only.",
            "Doctor does not provide full packaging, runtime, or semantic correctness guarantees.",
        ],
    }


def inspect_project(path: Path) -> dict[str, object]:
    metadata = read_metadata(path)
    guess = _guess_template(path, metadata)
    all_templates = [tpl.name for tpl in list_templates()]
    return {
        "path": str(path),
        "template_guess": guess,
        "metadata": metadata,
        "known_templates": all_templates,
        "files": sorted(str(p.relative_to(path)) for p in path.glob("**/*") if p.is_file()) if path.exists() else [],
        "notes": ["Project inspection is local-only metadata and file-structure introspection."],
    }
