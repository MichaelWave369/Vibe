from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PythonSnippet:
    """Deterministic snippet row for PhiPython suggestions and docs."""

    trigger: str
    description: str
    code: str
    placeholders: tuple[str, ...] = ()
    educational_note: str | None = None


_SNIPPETS: dict[str, PythonSnippet] = {
    "api_get": PythonSnippet(
        trigger="api_get",
        description="HTTP GET request with status handling.",
        code=(
            "import requests\n\n"
            "response = requests.get(\"https://api.example.com/data\", timeout=10)\n"
            "response.raise_for_status()\n"
            "payload = response.json()\n"
            "print(payload)\n"
        ),
        placeholders=("url",),
        educational_note="Use raise_for_status() to fail fast for non-2xx responses.",
    ),
    "flask_app": PythonSnippet(
        trigger="flask_app",
        description="Minimal Flask application with one route.",
        code=(
            "from flask import Flask\n\n"
            "app = Flask(__name__)\n\n"
            "@app.get(\"/\")\n"
            "def index() -> str:\n"
            "    return \"hello from PhiPython\"\n\n"
            "if __name__ == \"__main__\":\n"
            "    app.run(debug=True)\n"
        ),
        educational_note="Route decorators attach URL paths to Python callables.",
    ),
    "forloop": PythonSnippet(
        trigger="forloop",
        description="For-loop over a list with index and value.",
        code=(
            "items = [\"a\", \"b\", \"c\"]\n"
            "for index, item in enumerate(items):\n"
            "    print(index, item)\n"
        ),
        placeholders=("items",),
        educational_note="enumerate() yields both the index and current item.",
    ),
    "readfile": PythonSnippet(
        trigger="readfile",
        description="Read a UTF-8 text file.",
        code=(
            "from pathlib import Path\n\n"
            "text = Path(\"input.txt\").read_text(encoding=\"utf-8\")\n"
            "print(text)\n"
        ),
        placeholders=("path",),
    ),
    "tryexcept": PythonSnippet(
        trigger="tryexcept",
        description="Catch and handle one expected exception type.",
        code=(
            "try:\n"
            "    value = int(user_input)\n"
            "except ValueError as exc:\n"
            "    print(f\"Invalid integer: {exc}\")\n"
        ),
        placeholders=("exception_type",),
        educational_note="Catch the narrowest exception type you can explain and recover from.",
    ),
    "writejson": PythonSnippet(
        trigger="writejson",
        description="Serialize data to a JSON file.",
        code=(
            "import json\n"
            "from pathlib import Path\n\n"
            "data = {\"status\": \"ok\"}\n"
            "Path(\"output.json\").write_text(json.dumps(data, indent=2), encoding=\"utf-8\")\n"
        ),
        placeholders=("data", "path"),
        educational_note="Use indent for human-readable JSON output.",
    ),
}


def list_snippets() -> list[PythonSnippet]:
    """Return snippet rows in deterministic trigger order."""

    return [_SNIPPETS[key] for key in sorted(_SNIPPETS)]


def get_snippet(trigger: str) -> PythonSnippet | None:
    """Lookup a snippet by exact trigger."""

    return _SNIPPETS.get(trigger)


def snippet_completion_items(prefix: str = "") -> list[dict[str, object]]:
    """Completion rows compatible with the Vibe LSP completion surface."""

    norm = prefix.strip().lower()
    rows: list[dict[str, object]] = []
    for snippet in list_snippets():
        if norm and not snippet.trigger.startswith(norm):
            continue
        rows.append(
            {
                "label": snippet.trigger,
                "kind": 15,
                "detail": "PhiPython snippet",
                "documentation": snippet.description,
                "insertText": snippet.code,
            }
        )
    return rows
