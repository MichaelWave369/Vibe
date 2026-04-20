from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .scaffold_metadata import read_metadata
from .templates import get_template, list_templates


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    id: str
    status: str
    summary: str
    details: str
    suggested_action: str


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


def doctor_project(path: Path) -> dict[str, object]:
    checks: list[DoctorCheck] = []
    metadata = read_metadata(path)
    guess = _guess_template(path, metadata)

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

    readme = path / "README.md"
    checks.append(
        DoctorCheck(
            id="readme.present",
            status="pass" if readme.exists() else "warn",
            summary="README presence check.",
            details="README.md found." if readme.exists() else "README.md missing.",
            suggested_action="Add README.md with quickstart instructions." if not readme.exists() else "None.",
        )
    )

    main_py = path / "main.py"
    checks.append(
        DoctorCheck(
            id="entrypoint.main",
            status="pass" if main_py.exists() else "fail",
            summary="Entrypoint presence check.",
            details="main.py found." if main_py.exists() else "main.py not found.",
            suggested_action="Add a minimal main.py entrypoint.",
        )
    )

    metadata_status = "pass" if metadata is not None else "warn"
    checks.append(
        DoctorCheck(
            id="metadata.present",
            status=metadata_status,
            summary="PhiPython scaffold metadata check.",
            details=".phipython.json found." if metadata else "No .phipython.json metadata file.",
            suggested_action="Regenerate scaffold or add .phipython.json manually for richer doctor checks.",
        )
    )

    req_text = (path / "requirements.txt").read_text(encoding="utf-8") if (path / "requirements.txt").exists() else ""
    if guess in {"api_tool", "scraper"} and "requests" not in req_text:
        checks.append(
            DoctorCheck(
                id="deps.requests",
                status="warn",
                summary="Potential missing requests dependency hint.",
                details="requirements.txt does not include requests.",
                suggested_action="Add requests>=2.31.0 to requirements.txt.",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                id="deps.requests",
                status="pass",
                summary="Dependency hint check completed.",
                details="No obvious requests dependency mismatch.",
                suggested_action="None.",
            )
        )

    if guess == "flask_app":
        env_ok = (path / ".env.example").exists()
        checks.append(
            DoctorCheck(
                id="env.example",
                status="pass" if env_ok else "warn",
                summary="Environment example file check.",
                details=".env.example found." if env_ok else "Expected .env.example for flask starter.",
                suggested_action="Add .env.example with starter Flask environment keys.",
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
            "Doctor validates bounded scaffold health only.",
            "It does not perform full packaging, runtime, or environment resolution.",
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
