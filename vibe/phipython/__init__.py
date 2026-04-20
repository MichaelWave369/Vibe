"""PhiPython: guided Python authoring layer inside Vibe (bounded slice)."""

from .artifacts import export_artifact_bundle
from .doctor import doctor_project
from .engine import (
    apply_patch_plan_for_file,
    classify_intent,
    doctor,
    explain_file,
    explain_snippet,
    export_artifacts,
    init_template,
    inspect_project,
    list_patch_candidates_for_file,
    list_patch_plans_for_file,
    list_snippet_triggers,
    list_template_names,
    parse_traceback,
    preview_patch,
    preview_patch_plan_for_file,
    run_patch,
    run_patch_traceback,
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
from .patch import apply_safe_patch, list_patch_candidates, patch_from_traceback, preview_safe_patch
from .patch_plans import apply_patch_plan, list_patch_plans, preview_patch_plan
from .python_bridge import PythonScaffoldIntent, bridge_intent_to_python_scaffold
from .scaffold_metadata import read_metadata
from .snippets import expand_snippet, get_snippet, list_snippets, snippet_completion_items
from .templates import get_template, list_templates, render_template_files
from .traceback_utils import parse_traceback_text, summarize_traceback_chain

__all__ = [
    "PythonScaffoldIntent",
    "apply_patch_plan",
    "apply_patch_plan_for_file",
    "apply_safe_patch",
    "bridge_intent_to_python_scaffold",
    "classify_intent",
    "classify_intent_to_template",
    "doctor",
    "doctor_project",
    "explain_file",
    "explain_python_source",
    "explain_snippet",
    "explanation_for_keyword",
    "expand_snippet",
    "export_artifact_bundle",
    "export_artifacts",
    "get_snippet",
    "get_template",
    "init_template",
    "inspect_project",
    "list_patch_candidates",
    "list_patch_candidates_for_file",
    "list_patch_plans",
    "list_patch_plans_for_file",
    "list_snippet_triggers",
    "list_snippets",
    "list_supported_error_types",
    "list_template_names",
    "list_templates",
    "parse_traceback",
    "parse_traceback_text",
    "patch_from_traceback",
    "preview_patch",
    "preview_patch_plan",
    "preview_patch_plan_for_file",
    "preview_safe_patch",
    "read_metadata",
    "render_template_files",
    "run_patch",
    "run_patch_traceback",
    "scaffold_from_intent",
    "show_template",
    "snippet_completion_items",
    "snippet_preview",
    "suggest_fixes",
    "suggest_fixes_for_source",
    "suggest_fixes_for_traceback",
    "suggest_fixes_for_traceback_text",
    "summarize_traceback_chain",
    "translate_error",
]
