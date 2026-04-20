"""PhiPython: guided Python authoring layer inside Vibe (bounded v1.0 slice)."""

from .engine import explain_file, explain_snippet, init_template, list_snippet_triggers, list_template_names, translate_error
from .errors import list_supported_error_types
from .explain import explain_python_source, explanation_for_keyword
from .python_bridge import PythonScaffoldIntent, bridge_intent_to_python_scaffold
from .snippets import get_snippet, list_snippets, snippet_completion_items
from .templates import get_template, list_templates, render_template_files

__all__ = [
    "PythonScaffoldIntent",
    "bridge_intent_to_python_scaffold",
    "explain_file",
    "explain_python_source",
    "explain_snippet",
    "explanation_for_keyword",
    "get_snippet",
    "get_template",
    "init_template",
    "list_snippet_triggers",
    "list_snippets",
    "list_supported_error_types",
    "list_template_names",
    "list_templates",
    "render_template_files",
    "snippet_completion_items",
    "translate_error",
]
