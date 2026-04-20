from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    summary: str
    details: tuple[str, ...]
    bounded_note: str


_HOVER_EXPLANATIONS = {
    "if": "`if` starts a conditional branch that runs only when the condition is truthy.",
    "else": "`else` runs when the prior `if` condition is false.",
    "for": "`for` loops iterate over each item in a sequence or iterable.",
    "while": "`while` loops repeat until the condition becomes false.",
    "def": "`def` defines a reusable function.",
    "import": "`import` loads names from another module.",
    "try": "`try` marks code that may fail and pairs with `except` handlers.",
    "except": "`except` handles errors raised in the matching `try` block.",
    "list": "A list is an ordered, mutable sequence type.",
    "dict": "A dict stores key/value pairs for fast lookup by key.",
}


def explain_python_source(source: str) -> ExplanationResult:
    """Explain a small Python source fragment using stdlib AST patterns."""

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ExplanationResult(
            summary="Could not parse Python source.",
            details=(f"SyntaxError near line {exc.lineno}: {exc.msg}",),
            bounded_note="This is a parser-level explanation only; runtime semantics were not evaluated.",
        )

    details: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = ", ".join(alias.name for alias in node.names)
            details.append(f"Import statement loads module(s): {names}.")
        elif isinstance(node, ast.ImportFrom):
            names = ", ".join(alias.name for alias in node.names)
            details.append(f"From-import loads {names} from {node.module or '<relative module>'}.")
        elif isinstance(node, ast.Assign):
            details.append("Variable assignment stores a computed value in one or more names.")
        elif isinstance(node, ast.If):
            details.append("If/else branch checks a condition and chooses one execution path.")
        elif isinstance(node, (ast.For, ast.While)):
            details.append("Loop construct repeats work across items or while a condition holds.")
        elif isinstance(node, ast.FunctionDef):
            details.append(f"Function `{node.name}` defines reusable logic with explicit parameters.")
        elif isinstance(node, ast.Try):
            details.append("Try/except block catches selected exceptions to handle failures gracefully.")
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.List):
            details.append("List literal creates an ordered collection of values.")
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            details.append("Dict literal creates key/value mappings.")

    if not details:
        details.append("Source parsed successfully, but this PhiPython slice only explains common beginner constructs.")

    return ExplanationResult(
        summary="Plain-English explanation generated from Python AST patterns.",
        details=tuple(details[:12]),
        bounded_note=(
            "Heuristic educational explanation only. PhiPython v1.0 does not prove runtime behavior or full program semantics."
        ),
    )


def explanation_for_keyword(token: str) -> str | None:
    """Provide deterministic hover help for a known Python keyword/construct."""

    return _HOVER_EXPLANATIONS.get(token.strip())
