from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .artifacts import export_artifact_bundle
from .doctor import doctor_project, inspect_project as inspect_project_payload
from .errors import translate_python_error
from .explain import explain_python_source
from .fix import suggest_fixes_for_source, suggest_fixes_for_traceback
from .intent_scaffold import classify_intent_to_template, classify_intent_to_template_dict
from .patch import apply_safe_patch, list_patch_candidates, patch_from_traceback, preview_safe_patch
from .patch_plans import apply_patch_plan, list_patch_plans, preview_patch_plan
from .python_bridge import BridgeResult, PythonScaffoldIntent, bridge_intent_to_python_scaffold
from .scaffold_metadata import metadata_for_template, read_metadata, write_metadata
from .snippets import expand_snippet, list_snippets, snippet_as_dict
from .templates import list_templates, template_as_dict
from .traceback_utils import parse_traceback_text, summarize_traceback_chain


def list_template_names() -> list[str]:
    return [tpl.name for tpl in list_templates()]


def list_snippet_triggers() -> list[str]:
    return [snippet.trigger for snippet in list_snippets()]


def _write_scaffold_files(destination: Path, bridge: BridgeResult, features: tuple[str, ...]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for rel, body in bridge.files.items():
        out = destination / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
    reqs = bridge.files.get("requirements.txt", "")
    metadata = metadata_for_template(bridge.template, features=features, requirements_text=reqs)
    write_metadata(destination, metadata)


def init_template(template: str, destination: Path, project_name: str | None = None) -> BridgeResult:
    name = project_name or destination.name
    bridge = bridge_intent_to_python_scaffold(PythonScaffoldIntent(template=template, name=name))
    _write_scaffold_files(destination, bridge, features=())
    return bridge


def scaffold_from_intent(intent_text: str, destination: Path, project_name: str | None = None) -> dict[str, object]:
    match = classify_intent_to_template(intent_text)
    name = project_name or destination.name
    bridge = bridge_intent_to_python_scaffold(
        PythonScaffoldIntent(template=match.template, name=name, features=match.features)
    )
    _write_scaffold_files(destination, bridge, features=match.features)
    return {
        "intent": intent_text,
        "match": asdict(match),
        "template": bridge.template,
        "project_name": bridge.project_name,
        "destination": str(destination),
        "files": sorted(bridge.files),
        "note": "Scaffold-from-intent is bounded starter generation, not full semantic synthesis.",
    }


def explain_file(path: Path) -> dict[str, object]:
    result = explain_python_source(path.read_text(encoding="utf-8"))
    return asdict(result)


def explain_snippet(trigger: str) -> dict[str, object]:
    return snippet_as_dict(trigger)


def show_template(template: str) -> dict[str, object]:
    return template_as_dict(template)


def translate_error(exception_type: str, message: str) -> dict[str, object]:
    return asdict(translate_python_error(exception_type, message))


def suggest_fixes(path: Path) -> dict[str, object]:
    return suggest_fixes_for_source(path.read_text(encoding="utf-8"))


def suggest_fixes_for_traceback_text(traceback_text: str) -> dict[str, object]:
    summary = parse_traceback_text(traceback_text)
    payload = suggest_fixes_for_traceback(summary)
    payload["traceback_summary"] = asdict(summary)
    payload["traceback_chain"] = summarize_traceback_chain(traceback_text)
    return payload


def parse_traceback(traceback_text: str) -> dict[str, object]:
    return asdict(parse_traceback_text(traceback_text))


def classify_intent(intent_text: str) -> dict[str, object]:
    return classify_intent_to_template_dict(intent_text)


def snippet_preview(trigger: str, values: dict[str, str] | None = None) -> dict[str, object]:
    snippet = snippet_as_dict(trigger)
    snippet["expanded"] = expand_snippet(trigger, values=values)
    return snippet


def doctor(path: Path, template_profile: str | None = None) -> dict[str, object]:
    return doctor_project(path, template_profile=template_profile)


def inspect_project(path: Path) -> dict[str, object]:
    payload = inspect_project_payload(path)
    payload["metadata_exists"] = read_metadata(path) is not None
    return payload


def list_patch_candidates_for_file(path: Path, issue_type: str | None = None) -> dict[str, object]:
    return list_patch_candidates(path, issue_type=issue_type)


def preview_patch(path: Path, issue_type: str | None = None, select: str | None = None) -> dict[str, object]:
    return preview_safe_patch(path, issue_type=issue_type, select=select)


def run_patch(path: Path, issue_type: str | None = None, apply: bool = False, select: str | None = None) -> dict[str, object]:
    return apply_safe_patch(path, issue_type=issue_type, apply=apply, select=select)


def run_patch_traceback(
    traceback_path: Path,
    apply: bool = False,
    issue_type: str | None = None,
    interactive: bool = False,
    select: str | None = None,
) -> dict[str, object]:
    return patch_from_traceback(
        traceback_path,
        apply=apply,
        issue_type=issue_type,
        interactive=interactive,
        select=select,
    )


def list_patch_plans_for_file(path: Path) -> dict[str, object]:
    return list_patch_plans(path)


def preview_patch_plan_for_file(path: Path, plan_id: str) -> dict[str, object]:
    return preview_patch_plan(path, plan_id=plan_id)


def apply_patch_plan_for_file(path: Path, plan_id: str, apply: bool = False) -> dict[str, object]:
    return apply_patch_plan(path, plan_id=plan_id, apply=apply)


def export_artifacts(export_dir: Path, prefix: str, payload: dict[str, object], title: str) -> dict[str, object]:
    return export_artifact_bundle(export_dir=export_dir, prefix=prefix, payload=payload, title=title)
