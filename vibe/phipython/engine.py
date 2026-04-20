from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .errors import translate_python_error
from .explain import explain_python_source
from .fix import suggest_fixes_for_source, suggest_fixes_for_traceback
from .intent_scaffold import classify_intent_to_template, classify_intent_to_template_dict
from .python_bridge import BridgeResult, PythonScaffoldIntent, bridge_intent_to_python_scaffold
from .snippets import expand_snippet, get_snippet, list_snippets, snippet_as_dict
from .templates import list_templates, template_as_dict
from .traceback_utils import parse_traceback_text


def list_template_names() -> list[str]:
    return [tpl.name for tpl in list_templates()]


def list_snippet_triggers() -> list[str]:
    return [snippet.trigger for snippet in list_snippets()]


def init_template(template: str, destination: Path, project_name: str | None = None) -> BridgeResult:
    name = project_name or destination.name
    bridge = bridge_intent_to_python_scaffold(PythonScaffoldIntent(template=template, name=name))
    destination.mkdir(parents=True, exist_ok=True)
    for rel, body in bridge.files.items():
        out = destination / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
    return bridge


def scaffold_from_intent(intent_text: str, destination: Path, project_name: str | None = None) -> dict[str, object]:
    match = classify_intent_to_template(intent_text)
    name = project_name or destination.name
    bridge = bridge_intent_to_python_scaffold(
        PythonScaffoldIntent(template=match.template, name=name, features=match.features)
    )
    destination.mkdir(parents=True, exist_ok=True)
    for rel, body in bridge.files.items():
        out = destination / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
    return {
        "intent": intent_text,
        "match": asdict(match),
        "template": bridge.template,
        "project_name": bridge.project_name,
        "destination": str(destination),
        "files": sorted(bridge.files),
        "note": (
            "Scaffold-from-intent is bounded template selection and starter generation, not full semantic synthesis."
        ),
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
    return payload


def parse_traceback(traceback_text: str) -> dict[str, object]:
    return asdict(parse_traceback_text(traceback_text))


def classify_intent(intent_text: str) -> dict[str, object]:
    return classify_intent_to_template_dict(intent_text)


def snippet_preview(trigger: str, values: dict[str, str] | None = None) -> dict[str, object]:
    snippet = snippet_as_dict(trigger)
    snippet["expanded"] = expand_snippet(trigger, values=values)
    return snippet
