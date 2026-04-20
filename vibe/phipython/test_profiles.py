from __future__ import annotations

from dataclasses import dataclass

TEST_PROFILE_VERSION = "1.4"
TEST_MANIFEST_FILE = ".phipython.tests.json"


@dataclass(frozen=True, slots=True)
class TestProfile:
    template: str
    test_files: tuple[str, ...]
    covered_signals: tuple[str, ...]
    skipped_areas: tuple[str, ...]
    notes: tuple[str, ...]


_PROFILES: dict[str, TestProfile] = {
    "cli": TestProfile(
        template="cli",
        test_files=("tests/test_cli_starter.py",),
        covered_signals=("entrypoint_import", "main_smoke", "argparse_hint"),
        skipped_areas=("full_cli_behavior",),
        notes=("Starter-oriented smoke tests only.",),
    ),
    "automation": TestProfile(
        template="automation",
        test_files=("tests/test_automation_starter.py",),
        covered_signals=("entrypoint_import", "main_smoke"),
        skipped_areas=("filesystem_side_effects",),
        notes=("No destructive operations are executed.",),
    ),
    "api_tool": TestProfile(
        template="api_tool",
        test_files=("tests/test_api_tool_starter.py",),
        covered_signals=("entrypoint_import", "response_helper_presence"),
        skipped_areas=("live_network_calls",),
        notes=("Network calls are intentionally excluded.",),
    ),
    "scraper": TestProfile(
        template="scraper",
        test_files=("tests/test_scraper_starter.py",),
        covered_signals=("entrypoint_import", "parser_hint"),
        skipped_areas=("live_http_fetch",),
        notes=("Inline deterministic parser smoke only.",),
    ),
    "flask_app": TestProfile(
        template="flask_app",
        test_files=("tests/test_flask_app_starter.py",),
        covered_signals=("app_object_import", "route_smoke"),
        skipped_areas=("full_integration_runtime",),
        notes=("Only deterministic test_client smoke checks.",),
    ),
    "dashboard": TestProfile(
        template="dashboard",
        test_files=("tests/test_dashboard_starter.py",),
        covered_signals=("entrypoint_import", "helper_smoke"),
        skipped_areas=("rendering_pipeline",),
        notes=("No heavy plotting/rendering execution.",),
    ),
}


def list_test_profiles() -> list[TestProfile]:
    return [_PROFILES[name] for name in sorted(_PROFILES)]


def get_test_profile(template: str) -> TestProfile | None:
    return _PROFILES.get(template)
