"""PhiPython: guided Python authoring layer inside Vibe (bounded slice)."""

from .engine import (
    classify_intent,
    explain_file,
    explain_snippet,
    init_template,
    list_snippet_triggers,
    list_template_names,
    parse_traceback,
    scaffold_from_intent,
    show_template,
    snippet_preview,
    suggest_fixes,
    suggest_fixes_for_traceback_text,
    translate_error,
)
from .errors import list_supported_error_types
from .explain import explain_python_source, explanation_for_keyword
from .fix import suggest_fixes_for_source, suggest_fixes_for_traceback
from .intent_scaffold import classify_intent_to_template
from .python_bridge import PythonScaffoldIntent, bridge_intent_to_python_scaffold
from .snippets import expand_snippet, get_snippet, list_snippets, snippet_completion_items
from .templates import get_template, list_templates, render_template_files
from .traceback_utils import parse_traceback_text

__all__ = [
    "PythonScaffoldIntent",
    "bridge_intent_to_python_scaffold",
    "classify_intent",
    "classify_intent_to_template",
    "explain_file",
    "explain_python_source",
    "explain_snippet",
    "explanation_for_keyword",
    "expand_snippet",
    "get_snippet",
    "get_template",
    "init_template",
    "list_snippet_triggers",
    "list_snippets",
    "list_supported_error_types",
    "list_template_names",
    "list_templates",
    "parse_traceback",
    "parse_traceback_text",
    "render_template_files",
    "scaffold_from_intent",
    "show_template",
    "snippet_completion_items",
    "snippet_preview",
    "suggest_fixes",
    "suggest_fixes_for_source",
    "suggest_fixes_for_traceback",
    "suggest_fixes_for_traceback_text",
    "translate_error",
]
