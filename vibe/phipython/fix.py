from __future__ import annotations

import ast
import builtins
import difflib
import re
from dataclasses import asdict, dataclass

from .traceback_utils import TracebackSummary


@dataclass(frozen=True, slots=True)
class CandidateFix:
    title: str
    explanation: str
    confidence: str
    patch_hint: str


@dataclass(frozen=True, slots=True)
class FixIssue:
    issue_type: str
    summary: str
    line: int | None
    candidate_fixes: tuple[CandidateFix, ...]
    notes: tuple[str, ...] = ()


def _parse_syntax_issue(source: str) -> FixIssue | None:
    try:
        ast.parse(source)
        return None
    except SyntaxError as exc:
        msg = exc.msg or "syntax issue"
        line = exc.lineno
        issue_type = "syntax_error"
        fixes: list[CandidateFix] = []
        if "expected ':'" in msg:
            issue_type = "missing_colon"
            fixes.append(
                CandidateFix(
                    title="Add missing colon",
                    explanation="Block starters like if/for/while/def/try/class require a trailing colon.",
                    confidence="high",
                    patch_hint="Add ':' at the end of the indicated statement line.",
                )
            )
        if "indent" in msg.lower() or isinstance(exc, IndentationError):
            issue_type = "indentation_mismatch"
            fixes.append(
                CandidateFix(
                    title="Normalize indentation",
                    explanation="Python block structure depends on consistent indentation depth.",
                    confidence="medium",
                    patch_hint="Use 4 spaces per block level; avoid mixing tabs and spaces.",
                )
            )
        if not fixes:
            fixes.append(
                CandidateFix(
                    title="Review parser location",
                    explanation="The parser found invalid syntax near this location.",
                    confidence="medium",
                    patch_hint="Check punctuation and structure at this line and the previous line.",
                )
            )
        return FixIssue(
            issue_type=issue_type,
            summary=f"Parser reported: {msg}",
            line=line,
            candidate_fixes=tuple(fixes),
            notes=("Heuristic suggestion from parser diagnostics.",),
        )


def _collect_imported_and_defined(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    imported: set[str] = set()
    defined: set[str] = set()
    loaded: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.update(alias.asname or alias.name for alias in node.names)
            if node.module:
                imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.FunctionDef):
            defined.add(node.name)
            defined.update(arg.arg for arg in node.args.args)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                loaded.add(node.id)
            elif isinstance(node.ctx, ast.Store):
                defined.add(node.id)
    return imported, defined, loaded


def _undefined_name_issues(tree: ast.AST) -> list[FixIssue]:
    imported, defined, loaded = _collect_imported_and_defined(tree)
    builtins_set = set(dir(builtins))
    issues: list[FixIssue] = []
    for name in sorted(loaded):
        if name in defined or name in imported or name in builtins_set:
            continue
        maybe = difflib.get_close_matches(name, sorted(defined | imported), n=1, cutoff=0.75)
        suggestions = [
            CandidateFix(
                title="Define missing name",
                explanation="This name is read before local definition/import in this source slice.",
                confidence="medium",
                patch_hint=f"Assign or import `{name}` before first use.",
            )
        ]
        if maybe:
            suggestions.append(
                CandidateFix(
                    title="Check for typo",
                    explanation="The undefined name is similar to an existing local/imported symbol.",
                    confidence="medium",
                    patch_hint=f"Rename `{name}` to `{maybe[0]}` if that matches intent.",
                )
            )
        issues.append(
            FixIssue(
                issue_type="undefined_name_typo",
                summary=f"Possible undefined symbol: `{name}`.",
                line=None,
                candidate_fixes=tuple(suggestions),
                notes=("Heuristic static check; dynamic scopes may differ.",),
            )
        )
    return issues


def _source_regex_issues(source: str) -> list[FixIssue]:
    issues: list[FixIssue] = []
    lines = source.splitlines()

    if re.search(r"\b\w+\s*\+\s*['\"]", source) or re.search(r"['\"]\s*\+\s*\w+", source):
        issues.append(
            FixIssue(
                issue_type="int_str_concat",
                summary="Possible mixed-type concatenation detected.",
                line=None,
                candidate_fixes=(
                    CandidateFix(
                        title="Convert values before concatenation",
                        explanation="String concatenation with numeric values raises TypeError.",
                        confidence="medium",
                        patch_hint="Wrap numeric operand with str(...) or use f-strings.",
                    ),
                ),
                notes=("Pattern-based heuristic; inspect operand types.",),
            )
        )

    bad_mode = re.search(r"open\([^\)]*,\s*['\"](rw|wr|ra)['\"]", source)
    if bad_mode:
        issues.append(
            FixIssue(
                issue_type="file_open_mode",
                summary="Suspicious file mode string in open(...).",
                line=source[: bad_mode.start()].count("\n") + 1,
                candidate_fixes=(
                    CandidateFix(
                        title="Use valid Python file mode",
                        explanation="Common modes are r, w, a, rb, wb, and combinations like r+.",
                        confidence="high",
                        patch_hint="Replace mode with one of: 'r', 'w', 'a', 'r+', 'rb', 'wb'.",
                    ),
                ),
            )
        )

    if "requests.get(" in source and "import requests" not in source:
        issues.append(
            FixIssue(
                issue_type="missing_import",
                summary="`requests.get` used without `import requests`.",
                line=None,
                candidate_fixes=(
                    CandidateFix(
                        title="Add requests import",
                        explanation="Calling requests.get requires importing the module first.",
                        confidence="high",
                        patch_hint="Add `import requests` near the top of the file.",
                    ),
                ),
            )
        )

    if "requests.get(" in source and "raise_for_status" not in source:
        issues.append(
            FixIssue(
                issue_type="requests_status_handling",
                summary="Requests call without explicit status check.",
                line=None,
                candidate_fixes=(
                    CandidateFix(
                        title="Check HTTP status",
                        explanation="Starter scripts are more robust when HTTP errors are surfaced explicitly.",
                        confidence="medium",
                        patch_hint="After requests.get(...), call response.raise_for_status().",
                    ),
                ),
            )
        )

    if "Flask(" in source and "@app." not in source:
        issues.append(
            FixIssue(
                issue_type="flask_route_missing",
                summary="Flask app detected without route decorator.",
                line=None,
                candidate_fixes=(
                    CandidateFix(
                        title="Add starter route",
                        explanation="Flask app starters usually define at least one route for quick verification.",
                        confidence="medium",
                        patch_hint="Add `@app.get('/')` above a simple view function.",
                    ),
                ),
            )
        )

    if "argparse" in source and "parse_args(" not in source:
        issues.append(
            FixIssue(
                issue_type="argparse_parse_missing",
                summary="argparse imported but parse_args() not used.",
                line=None,
                candidate_fixes=(
                    CandidateFix(
                        title="Parse CLI arguments",
                        explanation="Without parse_args(), arguments are declared but never consumed.",
                        confidence="medium",
                        patch_hint="Call parser.parse_args() before using CLI values.",
                    ),
                ),
            )
        )

    for idx, line in enumerate(lines, start=1):
        if re.match(r"\s*(if|for|while|def|try|class)\b[^:]*$", line.strip()) and not line.strip().endswith(":"):
            issues.append(
                FixIssue(
                    issue_type="missing_colon",
                    summary="Likely missing colon on control/function/class line.",
                    line=idx,
                    candidate_fixes=(
                        CandidateFix(
                            title="Add colon",
                            explanation="Python block statements require ':' to open an indented block.",
                            confidence="high",
                            patch_hint=f"Append ':' to line {idx}.",
                        ),
                    ),
                )
            )
            break

    return issues


def suggest_fixes_for_source(source: str) -> dict[str, object]:
    """Return deterministic candidate fixes for common Python starter mistakes."""

    issues: list[FixIssue] = []
    syntax_issue = _parse_syntax_issue(source)
    if syntax_issue is not None:
        issues.append(syntax_issue)
        # Parsing failed; still run regex heuristics for useful starter hints.
        issues.extend(_source_regex_issues(source))
    else:
        tree = ast.parse(source)
        issues.extend(_undefined_name_issues(tree))
        issues.extend(_source_regex_issues(source))

    return {
        "issues": [asdict(issue) for issue in issues],
        "notes": [
            "PhiPython v1.1 fix engine emits heuristic candidate fixes only.",
            "Review generated patch hints before applying changes.",
        ],
    }


def suggest_fixes_for_traceback(summary: TracebackSummary) -> dict[str, object]:
    """Return bounded candidate fixes driven by traceback exception classes."""

    issues: list[FixIssue] = []
    exc = summary.exception_type
    msg = summary.message.lower()

    if exc in {"NameError", "UnboundLocalError"}:
        issues.append(
            FixIssue(
                issue_type="undefined_name_typo",
                summary="Traceback indicates an unresolved name.",
                line=summary.line_number,
                candidate_fixes=(
                    CandidateFix(
                        title="Define or import missing symbol",
                        explanation="NameError usually means the symbol is out-of-scope or misspelled.",
                        confidence="medium",
                        patch_hint="Verify spelling and define/import the symbol before usage.",
                    ),
                ),
            )
        )
    elif exc == "TypeError" and "str" in msg and "int" in msg:
        issues.append(
            FixIssue(
                issue_type="int_str_concat",
                summary="Traceback suggests mixed int/str operation.",
                line=summary.line_number,
                candidate_fixes=(
                    CandidateFix(
                        title="Normalize operand types",
                        explanation="Mixed numeric/string operations commonly trigger this TypeError pattern.",
                        confidence="high",
                        patch_hint="Use explicit conversion (str/int) or f-strings.",
                    ),
                ),
            )
        )
    elif exc in {"ModuleNotFoundError", "ImportError"}:
        issues.append(
            FixIssue(
                issue_type="missing_import",
                summary="Traceback indicates import resolution failure.",
                line=summary.line_number,
                candidate_fixes=(
                    CandidateFix(
                        title="Install dependency or correct module path",
                        explanation="Imports fail when package is missing or module path is incorrect.",
                        confidence="high",
                        patch_hint="Install package in current environment and verify import name.",
                    ),
                ),
            )
        )

    intermediate = [stage.exception_type for stage in summary.chain[:-1]]
    notes = [
        "Traceback-driven fixes are heuristic candidates, not guaranteed patches.",
        summary.heuristic_note,
    ]
    if intermediate:
        notes.append(f"Observed chained exceptions before final error: {', '.join(intermediate)}.")

    return {
        "issues": [asdict(issue) for issue in issues],
        "notes": notes,
    }
