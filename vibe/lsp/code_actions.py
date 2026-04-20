from __future__ import annotations

from pathlib import Path

from ..phipython import explanation_for_keyword, get_snippet
from ..phipython.fix import suggest_fixes_for_source
from ..phipython.patch import preview_safe_patch
from ..phipython.traceback_utils import parse_traceback_text


def _line_slice(text: str, line: int) -> str:
    lines = text.splitlines()
    if 0 <= line < len(lines):
        return lines[line]
    return ""


def python_code_actions(
    text: str,
    path: Path | None,
    start_line: int,
    end_line: int,
    start_character: int = 0,
    end_character: int = 0,
    selected_text: str | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Return bounded deterministic code actions for Python documents."""

    if path is None or path.suffix != ".py":
        return []

    actions: list[dict[str, object]] = []
    focus = selected_text if selected_text is not None else _line_slice(text, start_line).strip()

    snippet = get_snippet(focus)
    if snippet is not None:
        actions.append(
            {
                "title": f"PhiPython: expand snippet `{snippet.trigger}`",
                "kind": "quickfix",
                "edit": {
                    "changes": {
                        path.resolve().as_uri(): [
                            {
                                "range": {
                                    "start": {"line": start_line, "character": start_character},
                                    "end": {"line": end_line, "character": end_character or len(_line_slice(text, end_line))},
                                },
                                "newText": snippet.code,
                            }
                        ]
                    }
                },
            }
        )

    keyword_help = explanation_for_keyword(focus)
    if keyword_help is not None:
        actions.append(
            {
                "title": f"PhiPython: explain `{focus}`",
                "kind": "refactor.extract",
                "data": {"explanation": keyword_help, "token": focus},
            }
        )

    if "Traceback" in focus or "Error" in focus:
        summary = parse_traceback_text(focus)
        actions.append(
            {
                "title": "PhiPython: translate traceback snippet",
                "kind": "quickfix",
                "data": {
                    "exception_type": summary.exception_type,
                    "message": summary.message,
                    "line_number": summary.line_number,
                },
            }
        )

    fixes = suggest_fixes_for_source(text)
    if fixes["issues"]:
        top = fixes["issues"][0]
        actions.append(
            {
                "title": f"PhiPython: suggest fix for {top['issue_type']}",
                "kind": "quickfix",
                "data": {"issue": top},
            }
        )
        if path.exists():
            patch_preview = preview_safe_patch(path)
            if patch_preview["can_apply"]:
                actions.append(
                    {
                        "title": f"PhiPython: preview safe patch `{patch_preview['patch_type']}`",
                        "kind": "quickfix",
                        "data": {"patch_preview": patch_preview},
                    }
                )

    if diagnostics:
        for diag in diagnostics:
            code = str(diag.get("code", ""))
            if code.startswith("parse.") or "error" in code.lower():
                actions.append(
                    {
                        "title": "PhiPython: explain this error",
                        "kind": "quickfix",
                        "data": {"diagnostic": diag},
                    }
                )
                break

    return actions
