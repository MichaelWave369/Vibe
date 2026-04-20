from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True, slots=True)
class SnippetPlaceholder:
    name: str
    description: str
    default: str = ""


@dataclass(frozen=True, slots=True)
class PythonSnippet:
    """Deterministic snippet row for PhiPython suggestions and docs."""

    trigger: str
    category: str
    description: str
    code: str
    placeholders: tuple[SnippetPlaceholder, ...] = ()
    template_variables: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    educational_note: str | None = None
    related_templates: tuple[str, ...] = ()


def _p(name: str, description: str, default: str = "") -> SnippetPlaceholder:
    return SnippetPlaceholder(name=name, description=description, default=default)


_SNIPPETS: dict[str, PythonSnippet] = {
    "api_get": PythonSnippet(
        trigger="api_get",
        category="api",
        description="HTTP GET request with timeout and status handling.",
        code=(
            "import requests\n\n"
            "url = \"${url}\"\n"
            "response = requests.get(url, timeout=${timeout})\n"
            "response.raise_for_status()\n"
            "payload = response.json()\n"
            "print(payload)\n"
        ),
        placeholders=(_p("url", "Request URL", "https://api.example.com/data"), _p("timeout", "HTTP timeout seconds", "10")),
        template_variables={"url": "https://api.example.com/data", "timeout": "10"},
        tags=("api", "requests", "json"),
        educational_note="Use raise_for_status() to fail fast for non-2xx responses.",
        related_templates=("api_tool",),
    ),
    "argparse_cli": PythonSnippet(
        trigger="argparse_cli",
        category="cli",
        description="Small argparse command-line starter.",
        code=(
            "import argparse\n\n"
            "parser = argparse.ArgumentParser(description=\"${description}\")\n"
            "parser.add_argument(\"name\")\n"
            "args = parser.parse_args()\n"
            "print(f\"hello {args.name}\")\n"
        ),
        placeholders=(_p("description", "CLI description text", "PhiPython CLI"),),
        template_variables={"description": "PhiPython CLI"},
        tags=("cli", "argparse"),
        related_templates=("cli",),
    ),
    "env_var": PythonSnippet(
        trigger="env_var",
        category="config",
        description="Read an environment variable with fallback.",
        code=(
            "import os\n\n"
            "api_key = os.getenv(\"${key}\", \"${default}\")\n"
            "print(api_key)\n"
        ),
        placeholders=(_p("key", "Environment variable name", "API_KEY"), _p("default", "Fallback value", "")),
        template_variables={"key": "API_KEY", "default": ""},
        tags=("config", "environment"),
    ),
    "file_append": PythonSnippet(
        trigger="file_append",
        category="files",
        description="Append one line to a text file.",
        code=(
            "from pathlib import Path\n\n"
            "with Path(\"${path}\").open(\"a\", encoding=\"utf-8\") as handle:\n"
            "    handle.write(${line})\n"
        ),
        placeholders=(_p("path", "File path", "output.log"), _p("line", "Line expression", "\"new entry\\n\"")),
        template_variables={"path": "output.log", "line": '"new entry\\n"'},
        tags=("files",),
    ),
    "flask_app": PythonSnippet(
        trigger="flask_app",
        category="web",
        description="Minimal Flask app with a health route.",
        code=(
            "from flask import Flask\n\n"
            "app = Flask(__name__)\n\n"
            "@app.get(\"/${route}\")\n"
            "def ${handler}() -> str:\n"
            "    return \"ok\"\n\n"
            "if __name__ == \"__main__\":\n"
            "    app.run(debug=True)\n"
        ),
        placeholders=(_p("route", "Route suffix", "health"), _p("handler", "Handler function name", "health")),
        template_variables={"route": "health", "handler": "health"},
        tags=("web", "flask"),
        educational_note="Route decorators attach URL paths to Python callables.",
        related_templates=("flask_app",),
    ),
    "forloop": PythonSnippet(
        trigger="forloop",
        category="loops",
        description="For-loop over iterable with index and value.",
        code=(
            "for index, item in enumerate(${iterable}):\n"
            "    print(index, item)\n"
        ),
        placeholders=(_p("iterable", "Iterable expression", "items"),),
        template_variables={"iterable": "items"},
        tags=("loops",),
        educational_note="enumerate() yields both index and current item.",
    ),
    "pandas_csv": PythonSnippet(
        trigger="pandas_csv",
        category="data",
        description="Read CSV and print quick summary with pandas.",
        code=(
            "import pandas as pd\n\n"
            "frame = pd.read_csv(\"${path}\")\n"
            "print(frame.head())\n"
            "print(frame.describe(include=\"all\"))\n"
        ),
        placeholders=(_p("path", "CSV path", "data.csv"),),
        template_variables={"path": "data.csv"},
        tags=("data", "csv", "pandas"),
        related_templates=("dashboard",),
    ),
    "readfile": PythonSnippet(
        trigger="readfile",
        category="files",
        description="Read a UTF-8 text file.",
        code=(
            "from pathlib import Path\n\n"
            "text = Path(\"${path}\").read_text(encoding=\"utf-8\")\n"
            "print(text)\n"
        ),
        placeholders=(_p("path", "Input path", "input.txt"),),
        template_variables={"path": "input.txt"},
        tags=("files",),
    ),
    "requests_json": PythonSnippet(
        trigger="requests_json",
        category="api",
        description="GET JSON payload and print selected key.",
        code=(
            "import requests\n\n"
            "response = requests.get(\"${url}\", timeout=10)\n"
            "response.raise_for_status()\n"
            "payload = response.json()\n"
            "print(payload.get(\"${key}\"))\n"
        ),
        placeholders=(_p("url", "API URL", "https://api.example.com/data"), _p("key", "JSON key", "status")),
        template_variables={"url": "https://api.example.com/data", "key": "status"},
        tags=("api", "requests", "json"),
        related_templates=("api_tool",),
    ),
    "tryexcept": PythonSnippet(
        trigger="tryexcept",
        category="errors",
        description="Catch and handle one expected exception type.",
        code=(
            "try:\n"
            "    ${operation}\n"
            "except ${exception_type} as exc:\n"
            "    print(f\"Handled error: {exc}\")\n"
        ),
        placeholders=(_p("operation", "Operation that might fail", "value = int(user_input)"), _p("exception_type", "Exception class", "ValueError")),
        template_variables={"operation": "value = int(user_input)", "exception_type": "ValueError"},
        tags=("errors",),
        educational_note="Catch the narrowest exception type you can explain and recover from.",
    ),
    "writejson": PythonSnippet(
        trigger="writejson",
        category="files",
        description="Serialize data to JSON file.",
        code=(
            "import json\n"
            "from pathlib import Path\n\n"
            "data = ${data_expr}\n"
            "Path(\"${path}\").write_text(json.dumps(data, indent=2), encoding=\"utf-8\")\n"
        ),
        placeholders=(_p("data_expr", "Python expression that returns serializable data", '{"status": "ok"}'), _p("path", "Output path", "output.json")),
        template_variables={"data_expr": '{"status": "ok"}', "path": "output.json"},
        tags=("files", "json"),
        educational_note="Use indent for human-readable JSON output.",
    ),
}


def list_snippets() -> list[PythonSnippet]:
    return [_SNIPPETS[key] for key in sorted(_SNIPPETS)]


def get_snippet(trigger: str) -> PythonSnippet | None:
    return _SNIPPETS.get(trigger)


def expand_snippet(trigger: str, values: dict[str, str] | None = None) -> str:
    snippet = get_snippet(trigger)
    if snippet is None:
        raise KeyError(f"unknown snippet: {trigger}")
    expanded = snippet.code
    data = dict(snippet.template_variables)
    if values:
        data.update(values)
    for key in sorted(data):
        expanded = expanded.replace(f"${{{key}}}", data[key])
    return expanded


def snippet_completion_items(prefix: str = "") -> list[dict[str, object]]:
    norm = prefix.strip().lower()
    rows: list[dict[str, object]] = []
    for snippet in list_snippets():
        if norm and not snippet.trigger.startswith(norm):
            continue
        placeholder_blob = ", ".join(p.name for p in snippet.placeholders) or "none"
        rows.append(
            {
                "label": snippet.trigger,
                "kind": 15,
                "detail": f"PhiPython {snippet.category} snippet",
                "documentation": f"{snippet.description} (placeholders: {placeholder_blob})",
                "insertText": snippet.code,
            }
        )
    return rows


def snippet_as_dict(trigger: str) -> dict[str, object]:
    snippet = get_snippet(trigger)
    if snippet is None:
        raise KeyError(f"unknown snippet: {trigger}")
    payload = asdict(snippet)
    payload["expanded_default"] = expand_snippet(trigger)
    return payload
