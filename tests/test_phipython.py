import json
from pathlib import Path

from vibe.cli import main
from vibe.phipython import (
    PythonScaffoldIntent,
    bridge_intent_to_python_scaffold,
    explain_python_source,
    get_snippet,
    list_snippets,
    list_templates,
    translate_error,
)


def test_template_listing_and_scaffold_generation(tmp_path: Path) -> None:
    templates = [tpl.name for tpl in list_templates()]
    assert templates == ["api_tool", "automation", "cli", "dashboard", "flask_app", "scraper"]

    for template in templates:
        out = tmp_path / template
        rc = main(["phipython", "init", template, "--output-dir", str(out)])
        assert rc == 0
        assert (out / "README.md").exists()
        assert (out / "main.py").exists()


def test_snippet_listing_and_lookup() -> None:
    triggers = [item.trigger for item in list_snippets()]
    assert triggers == ["api_get", "flask_app", "forloop", "readfile", "tryexcept", "writejson"]
    snippet = get_snippet("forloop")
    assert snippet is not None
    assert "enumerate" in snippet.code


def test_explain_simple_python_constructs() -> None:
    src = """import os\nitems = [1, 2]\nfor x in items:\n    print(x)\n"""
    explained = explain_python_source(src)
    assert "Plain-English explanation" in explained.summary
    assert any("Import" in row for row in explained.details)
    assert any("Loop construct" in row for row in explained.details)


def test_translate_common_exception_types() -> None:
    translated = translate_error("TypeError", "unsupported operand type(s)")
    assert translated["exception_type"] == "TypeError"
    assert translated["heuristic"] is True
    assert translated["likely_fixes"]


def test_bridge_intent_to_python_scaffold_is_bounded() -> None:
    result = bridge_intent_to_python_scaffold(
        PythonScaffoldIntent(template="api_tool", name="weather_client", features=("requests", "json_output"))
    )
    assert result.template == "api_tool"
    assert "main.py" in result.files
    assert "Bounded scaffold bridge only" in result.note


def test_cli_phipython_commands(capsys, tmp_path: Path) -> None:
    code_file = tmp_path / "hello.py"
    code_file.write_text("x = 1\nif x:\n    print(x)\n", encoding="utf-8")

    assert main(["phipython", "list-templates", "--report", "json"]) == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "cli" in parsed["templates"]

    assert main(["phipython", "list-snippets", "--report", "json"]) == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "forloop" in parsed["snippets"]

    assert main(["phipython", "explain", str(code_file)]) == 0
    assert "Plain-English explanation" in capsys.readouterr().out

    assert main(["phipython", "explain-snippet", "readfile"]) == 0
    assert "trigger: readfile" in capsys.readouterr().out

    assert (
        main(
            [
                "phipython",
                "translate-error",
                "--type",
                "TypeError",
                "--message",
                "unsupported operand type(s) for +",
            ]
        )
        == 0
    )
    assert "likely fixes:" in capsys.readouterr().out


def test_cli_phipython_unknown_items_return_nonzero(capsys) -> None:
    assert main(["phipython", "init", "missing_template"]) == 1
    assert "unknown template" in capsys.readouterr().out

    assert main(["phipython", "explain-snippet", "missing_trigger"]) == 1
    assert "unknown snippet" in capsys.readouterr().out
