from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .errors import translate_python_error
from .explain import explain_python_source
from .python_bridge import BridgeResult, PythonScaffoldIntent, bridge_intent_to_python_scaffold
from .snippets import get_snippet, list_snippets
from .templates import list_templates


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


def explain_file(path: Path) -> dict[str, object]:
    result = explain_python_source(path.read_text(encoding="utf-8"))
    return asdict(result)


def explain_snippet(trigger: str) -> dict[str, object]:
    snippet = get_snippet(trigger)
    if snippet is None:
        raise KeyError(f"unknown snippet: {trigger}")
    return {
        "trigger": snippet.trigger,
        "description": snippet.description,
        "code": snippet.code,
        "educational_note": snippet.educational_note,
    }


def translate_error(exception_type: str, message: str) -> dict[str, object]:
    return asdict(translate_python_error(exception_type, message))
