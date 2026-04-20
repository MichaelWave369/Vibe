from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    id: str
    status: str
    summary: str
    details: str
    suggested_action: str


def baseline_checks(path: Path, metadata_present: bool) -> list[DoctorCheck]:
    readme = path / "README.md"
    main_py = path / "main.py"
    return [
        DoctorCheck(
            id="readme.present",
            status="pass" if readme.exists() else "warn",
            summary="README presence check.",
            details="README.md found." if readme.exists() else "README.md missing.",
            suggested_action="Add README.md with quickstart instructions." if not readme.exists() else "None.",
        ),
        DoctorCheck(
            id="entrypoint.main",
            status="pass" if main_py.exists() else "fail",
            summary="Entrypoint presence check.",
            details="main.py found." if main_py.exists() else "main.py not found.",
            suggested_action="Add a minimal main.py entrypoint.",
        ),
        DoctorCheck(
            id="metadata.present",
            status="pass" if metadata_present else "warn",
            summary="PhiPython scaffold metadata check.",
            details=".phipython.json found." if metadata_present else "No .phipython.json metadata file.",
            suggested_action="Regenerate scaffold or add .phipython.json for stronger profile checks.",
        ),
    ]


def template_profile_checks(path: Path, template: str, req_text: str) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    source = (path / "main.py").read_text(encoding="utf-8") if (path / "main.py").exists() else ""
    readme_text = (path / "README.md").read_text(encoding="utf-8") if (path / "README.md").exists() else ""
    req_lower = req_text.lower()

    if template == "cli":
        checks.append(
            DoctorCheck(
                id="cli.argparse",
                status="pass" if "argparse" in source else "warn",
                summary="CLI argparse starter sanity.",
                details="argparse usage detected." if "argparse" in source else "No argparse usage detected in main.py.",
                suggested_action="Add argparse parser setup for CLI starter.",
            )
        )
        checks.append(
            DoctorCheck(
                id="cli.main_guard",
                status="pass" if "if __name__ == \"__main__\":" in source else "warn",
                summary="CLI main guard check.",
                details="Main guard found." if "if __name__ == \"__main__\":" in source else "Missing main guard pattern.",
                suggested_action="Add `if __name__ == \"__main__\":` guard.",
            )
        )
        checks.append(
            DoctorCheck(
                id="cli.usage_example",
                status="pass" if "usage" in readme_text.lower() or "python main.py" in readme_text else "warn",
                summary="CLI usage example presence.",
                details="Usage example detected in README." if "usage" in readme_text.lower() or "python main.py" in readme_text else "No obvious usage example in README.",
                suggested_action="Add a short usage section (for example `python main.py --help`).",
            )
        )
    elif template == "api_tool":
        checks.extend(
            [
                DoctorCheck(
                    id="api.requests_import",
                    status="pass" if "import requests" in source else "warn",
                    summary="API tool requests import check.",
                    details="requests import detected." if "import requests" in source else "requests import missing.",
                    suggested_action="Add `import requests`.",
                ),
                DoctorCheck(
                    id="api.raise_for_status",
                    status="pass" if "raise_for_status" in source else "warn",
                    summary="API status handling check.",
                    details="raise_for_status detected." if "raise_for_status" in source else "No explicit HTTP status handling.",
                    suggested_action="Add `response.raise_for_status()` after requests call.",
                ),
                DoctorCheck(
                    id="api.dep_hint",
                    status="pass" if "requests" in req_text else "warn",
                    summary="API dependency hint check.",
                    details="requirements include requests." if "requests" in req_text else "requirements missing requests hint.",
                    suggested_action="Add requests>=2.31.0 to requirements.txt.",
                ),
                DoctorCheck(
                    id="api.json_hint",
                    status="pass" if ".json()" in source or "json.loads(" in source else "warn",
                    summary="API JSON parsing hint check.",
                    details="JSON parsing usage detected." if ".json()" in source or "json.loads(" in source else "No explicit JSON parsing hint in entry script.",
                    suggested_action="Parse API responses with `response.json()` (or json.loads) where expected.",
                ),
                DoctorCheck(
                    id="api.env_example",
                    status="pass" if (path / ".env.example").exists() else "warn",
                    summary="API env example check.",
                    details=".env.example present." if (path / ".env.example").exists() else ".env.example missing for API-key starter flows.",
                    suggested_action="Add .env.example with placeholder keys for local setup.",
                ),
            ]
        )
    elif template == "scraper":
        checks.extend(
            [
                DoctorCheck(
                    id="scraper.requests_hint",
                    status="pass" if "requests" in source or "requests" in req_lower else "warn",
                    summary="Scraper HTTP dependency/use hint check.",
                    details="requests usage or dependency hint detected." if "requests" in source or "requests" in req_lower else "No requests hint detected for scraper starter.",
                    suggested_action="Add requests usage/dependency if starter expects HTTP fetches.",
                ),
                DoctorCheck(
                    id="scraper.bs4_hint",
                    status="pass" if "beautifulsoup4" in req_lower or "BeautifulSoup" in source else "warn",
                    summary="Scraper parser dependency hint check.",
                    details="BeautifulSoup hint present." if "beautifulsoup4" in req_lower or "BeautifulSoup" in source else "BeautifulSoup hint missing.",
                    suggested_action="Add beautifulsoup4>=4.12.0 and parser usage when appropriate.",
                ),
                DoctorCheck(
                    id="scraper.output_example",
                    status="pass" if "output" in readme_text.lower() or (path / "output").exists() else "warn",
                    summary="Scraper output path/example check.",
                    details="Output example/path hint detected." if "output" in readme_text.lower() or (path / "output").exists() else "No output path/example hint detected.",
                    suggested_action="Document or create an output path/example for scraped data.",
                ),
            ]
        )
    elif template == "flask_app":
        app_src = (path / "app.py").read_text(encoding="utf-8") if (path / "app.py").exists() else ""
        checks.extend(
            [
                DoctorCheck(
                    id="flask.route_present",
                    status="pass" if "@app." in app_src else "warn",
                    summary="Flask route presence check.",
                    details="Route decorator found." if "@app." in app_src else "No route decorator detected.",
                    suggested_action="Add a basic route decorator and handler.",
                ),
                DoctorCheck(
                    id="flask.app_detect",
                    status="pass" if "Flask(" in app_src else "warn",
                    summary="Flask app object detectability.",
                    details="Flask app creation found." if "Flask(" in app_src else "Flask app creation not detected.",
                    suggested_action="Add `app = Flask(__name__)` or app factory.",
                ),
                DoctorCheck(
                    id="flask.run_pattern",
                    status="pass" if "if __name__ == \"__main__\":" in app_src or "flask run" in readme_text.lower() else "warn",
                    summary="Flask run entry pattern check.",
                    details="Run entry pattern detected." if "if __name__ == \"__main__\":" in app_src or "flask run" in readme_text.lower() else "No obvious Flask run entry pattern found.",
                    suggested_action="Add a main guard run block or document `flask run` usage.",
                ),
                DoctorCheck(
                    id="flask.dependency_hint",
                    status="pass" if "flask" in req_lower else "warn",
                    summary="Flask dependency hint check.",
                    details="requirements include flask." if "flask" in req_lower else "requirements missing flask dependency hint.",
                    suggested_action="Add Flask dependency to requirements.txt.",
                ),
            ]
        )
    elif template == "dashboard":
        checks.extend(
            [
                DoctorCheck(
                    id="dashboard.libs_hint",
                    status="pass" if any(lib in source or lib in req_lower for lib in ("pandas", "matplotlib")) else "warn",
                    summary="Dashboard data/viz dependency hint check.",
                    details="pandas/matplotlib hints detected." if any(lib in source or lib in req_lower for lib in ("pandas", "matplotlib")) else "No obvious dashboard library hints detected.",
                    suggested_action="Add pandas/matplotlib usage or dependency hints expected by the starter.",
                ),
                DoctorCheck(
                    id="dashboard.sample_data",
                    status="pass" if (path / "examples" / "sample.csv").exists() else "warn",
                    summary="Dashboard sample data check.",
                    details="Sample CSV exists." if (path / "examples" / "sample.csv").exists() else "No sample CSV found.",
                    suggested_action="Add examples/sample.csv for starter dashboard flow.",
                ),
                DoctorCheck(
                    id="dashboard.output_usage",
                    status="pass" if "output" in readme_text.lower() or "savefig(" in source else "warn",
                    summary="Dashboard output/example usage check.",
                    details="Output usage hint detected." if "output" in readme_text.lower() or "savefig(" in source else "No output/example usage hint detected.",
                    suggested_action="Document where charts/tables are written or displayed.",
                ),
            ]
        )
    elif template == "automation":
        checks.extend(
            [
                DoctorCheck(
                    id="automation.entry_script",
                    status="pass" if (path / "main.py").exists() else "fail",
                    summary="Automation entry script presence.",
                    details="main.py detected." if (path / "main.py").exists() else "main.py missing for automation starter.",
                    suggested_action="Add a main.py entry script for deterministic automation starter flow.",
                ),
                DoctorCheck(
                    id="automation.safety_comment",
                    status="pass" if "TODO" in source or "safety" in source.lower() else "warn",
                    summary="Automation safety guidance comment check.",
                    details="Guidance comments detected." if "TODO" in source or "safety" in source.lower() else "No obvious safety comment in entry script.",
                    suggested_action="Add bounded safety/TODO comments before destructive operations.",
                ),
                DoctorCheck(
                    id="automation.env_example",
                    status="pass" if (path / ".env.example").exists() else "warn",
                    summary="Automation env example check.",
                    details=".env.example present." if (path / ".env.example").exists() else ".env.example missing (needed when env vars are expected).",
                    suggested_action="Add .env.example when automation starter depends on environment variables.",
                ),
            ]
        )

    return checks
