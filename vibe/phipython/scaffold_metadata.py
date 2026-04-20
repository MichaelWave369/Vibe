from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

PHIPYTHON_METADATA_FILE = ".phipython.json"
PHIPYTHON_GENERATION_VERSION = "1.2"


@dataclass(frozen=True, slots=True)
class ScaffoldMetadata:
    template: str
    generated_features: tuple[str, ...]
    generation_version: str
    dependency_hints: tuple[str, ...]
    expected_checks: tuple[str, ...]


def metadata_for_template(template: str, features: tuple[str, ...], requirements_text: str = "") -> ScaffoldMetadata:
    deps = tuple(sorted(line.strip() for line in requirements_text.splitlines() if line.strip()))
    expected = ["readme_present", "entrypoint_present", "metadata_present"]
    if template in {"flask_app", "dashboard"}:
        expected.append("examples_or_tests_present")
    if "env_config" in features or template == "flask_app":
        expected.append("env_example_present")
    return ScaffoldMetadata(
        template=template,
        generated_features=tuple(sorted(features)),
        generation_version=PHIPYTHON_GENERATION_VERSION,
        dependency_hints=deps,
        expected_checks=tuple(sorted(set(expected))),
    )


def metadata_to_json(metadata: ScaffoldMetadata) -> str:
    return json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n"


def write_metadata(project_dir: Path, metadata: ScaffoldMetadata) -> Path:
    target = project_dir / PHIPYTHON_METADATA_FILE
    target.write_text(metadata_to_json(metadata), encoding="utf-8")
    return target


def read_metadata(project_dir: Path) -> dict[str, object] | None:
    target = project_dir / PHIPYTHON_METADATA_FILE
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
