from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorTranslation:
    exception_type: str
    plain_english: str
    likely_causes: tuple[str, ...]
    likely_fixes: tuple[str, ...]
    heuristic: bool


_TRANSLATIONS: dict[str, ErrorTranslation] = {
    "AttributeError": ErrorTranslation(
        exception_type="AttributeError",
        plain_english="Your code tried to use an attribute or method that does not exist on this object.",
        likely_causes=("Object type is not what you expected.", "Method/property name is misspelled."),
        likely_fixes=("Print type(value) right before the failing line.", "Check the API docs or dir(value) for valid attributes."),
        heuristic=True,
    ),
    "FileNotFoundError": ErrorTranslation(
        exception_type="FileNotFoundError",
        plain_english="Python could not find the file path you provided.",
        likely_causes=("Relative path is evaluated from a different working directory.",),
        likely_fixes=("Use pathlib.Path(...).resolve() to inspect the full path.", "Confirm the file exists before reading."),
        heuristic=False,
    ),
    "ImportError": ErrorTranslation(
        exception_type="ImportError",
        plain_english="Python could not complete the import statement.",
        likely_causes=("Package is missing.", "Import name does not match exported symbol."),
        likely_fixes=("Install dependency in the active environment.", "Check module and symbol spelling."),
        heuristic=True,
    ),
    "IndexError": ErrorTranslation(
        exception_type="IndexError",
        plain_english="Your code asked for a list/tuple index that is outside the valid range.",
        likely_causes=("Loop/index math overshot the sequence length.",),
        likely_fixes=("Check len(sequence) before indexing.", "Prefer iterating over items directly when possible."),
        heuristic=False,
    ),
    "KeyError": ErrorTranslation(
        exception_type="KeyError",
        plain_english="Dictionary lookup failed because the key is not present.",
        likely_causes=("Key spelling/casing mismatch.", "Dictionary was missing expected data."),
        likely_fixes=("Use dict.get(key) with defaults if key may be absent.", "Inspect available keys before lookup."),
        heuristic=False,
    ),
    "ModuleNotFoundError": ErrorTranslation(
        exception_type="ModuleNotFoundError",
        plain_english="Python could not find the module/package named in your import.",
        likely_causes=("Dependency is not installed in the environment.", "Import path is incorrect for project layout."),
        likely_fixes=("Install the package (for example with pip).", "Verify PYTHONPATH/project layout and module name."),
        heuristic=False,
    ),
    "NameError": ErrorTranslation(
        exception_type="NameError",
        plain_english="A variable or function name was used before Python could resolve it.",
        likely_causes=("Variable was never assigned.", "Name misspelling or scope mismatch."),
        likely_fixes=("Define the variable earlier in the same scope.", "Check spelling and indentation/scope."),
        heuristic=False,
    ),
    "SyntaxError": ErrorTranslation(
        exception_type="SyntaxError",
        plain_english="Python could not parse this code due to invalid syntax.",
        likely_causes=("Missing colon, parenthesis, or quote.", "Bad indentation around a block."),
        likely_fixes=("Read the exact line and one line above it.", "Run a formatter/linter to spot unmatched tokens."),
        heuristic=False,
    ),
    "TypeError": ErrorTranslation(
        exception_type="TypeError",
        plain_english="An operation received a value of an incompatible type.",
        likely_causes=("Mixed types in arithmetic/string operations.", "Function called with wrong argument types/count."),
        likely_fixes=("Check input types with type(...).", "Convert values explicitly (e.g., str(), int()) before combining."),
        heuristic=True,
    ),
}


def list_supported_error_types() -> list[str]:
    return sorted(_TRANSLATIONS)


def translate_python_error(exception_type: str, message: str = "") -> ErrorTranslation:
    """Translate common Python exceptions into bounded plain-English guidance."""

    normalized = exception_type.strip()
    if normalized in _TRANSLATIONS:
        return _TRANSLATIONS[normalized]
    return ErrorTranslation(
        exception_type=normalized or "UnknownError",
        plain_english="PhiPython does not have a specific translator for this exception yet.",
        likely_causes=("The failure may be specific to runtime data or third-party libraries.",),
        likely_fixes=(
            "Read the full traceback and identify the first frame in your own code.",
            "Reproduce with a minimal input and inspect variable types/values.",
            f"Raw message: {message}" if message else "Raw message unavailable.",
        ),
        heuristic=True,
    )
