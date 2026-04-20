from __future__ import annotations

from dataclasses import dataclass

from .templates import get_template, render_template_files


@dataclass(frozen=True, slots=True)
class PythonScaffoldIntent:
    """Bounded intent payload for PhiPython scaffold emission."""

    template: str
    name: str
    features: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BridgeResult:
    project_name: str
    template: str
    files: dict[str, str]
    note: str


def bridge_intent_to_python_scaffold(intent: PythonScaffoldIntent) -> BridgeResult:
    """Bridge bounded intent fields into starter Python project files."""

    template = get_template(intent.template)
    if template is None:
        raise KeyError(f"unknown template: {intent.template}")

    files = render_template_files(intent.template, intent.name)
    feature_set = set(intent.features)
    if "json_output" in feature_set and "main.py" in files:
        files["main.py"] += "\n# json_output feature: starter already emits JSON-ready structures where applicable.\n"
    if "requests" in feature_set:
        reqs = files.get("requirements.txt", "")
        if "requests" not in reqs:
            files["requirements.txt"] = (reqs + "requests>=2.31.0\n").lstrip("\n")

    return BridgeResult(
        project_name=intent.name,
        template=template.name,
        files=files,
        note=(
            "Bounded scaffold bridge only: PhiPython v1.0 maps small structured intent inputs to starter files. "
            "It does not claim full semantic preservation of arbitrary Python programs."
        ),
    )
