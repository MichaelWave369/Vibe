from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .doctor_profiles import DoctorCheck, baseline_checks, template_profile_checks
from .scaffold_metadata import read_metadata
from .test_profiles import TEST_MANIFEST_FILE, get_test_profile
from .testgen import read_test_manifest
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
    tests_dir = path / "tests"
    has_tests = tests_dir.exists() and any(tests_dir.glob("test_*.py"))
    test_manifest = read_test_manifest(path)
    checks.append(
        DoctorCheck(
            id="tests.present",
            status="pass" if has_tests else "warn",
            summary="Starter-oriented test presence check.",
            details="At least one test file found in tests/." if has_tests else "No starter tests detected in tests/.",
            suggested_action="Run `vibec phipython testgen <path> --apply` to generate bounded starter tests.",
        )
    )
    profile = get_test_profile(guess)
    checks.append(
        DoctorCheck(
            id="tests.profile_coverage",
            status="pass" if profile is not None else "warn",
            summary="Template test-profile coverage check.",
            details="Template has bounded test profile coverage." if profile is not None else "No bounded test profile found for inferred template.",
            suggested_action="Use a supported template profile or generate tests manually.",
        )
    )
    if test_manifest is None:
        checks.append(
            DoctorCheck(
                id="tests.manifest_present",
                status="warn",
                summary="Test generation manifest check.",
                details=f"{TEST_MANIFEST_FILE} not found.",
                suggested_action="Generate starter tests to emit a manifest for local lifecycle tracking.",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                id="tests.manifest_present",
                status="pass",
                summary="Test generation manifest check.",
                details=f"{TEST_MANIFEST_FILE} present.",
                suggested_action="Regenerate starter tests when scaffold changes materially.",
            )
        )
        metadata_path = path / ".phipython.json"
        manifest_path = path / TEST_MANIFEST_FILE
        stale = metadata_path.exists() and manifest_path.exists() and manifest_path.stat().st_mtime < metadata_path.stat().st_mtime
        checks.append(
            DoctorCheck(
                id="tests.manifest_freshness",
                status="warn" if stale else "pass",
                summary="Starter test manifest freshness check.",
                details="Manifest appears older than scaffold metadata." if stale else "Manifest freshness looks consistent with scaffold metadata timestamps.",
                suggested_action="Re-run test generation if metadata/template changed.",
            )
        )

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
