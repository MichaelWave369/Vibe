import json
from pathlib import Path

from vibe.cli import main
from vibe.phipython import (
    PythonScaffoldIntent,
    bridge_intent_to_python_scaffold,
    classify_intent,
    explain_python_source,
    get_snippet,
    list_snippets,
    list_templates,
    parse_traceback,
    suggest_fixes,
    suggest_fixes_for_traceback_text,
    translate_error,
)


def test_template_listing_and_richer_scaffold_generation(tmp_path: Path) -> None:
    templates = [tpl.name for tpl in list_templates()]
    assert templates == ["api_tool", "automation", "cli", "dashboard", "flask_app", "scraper"]

    for template in templates:
        out = tmp_path / template
        rc = main(["phipython", "init", template, "--output-dir", str(out)])
        assert rc == 0
        assert (out / "README.md").exists()
        assert (out / "main.py").exists()

    assert (tmp_path / "cli" / "tests" / "test_parser.py").exists()
    assert (tmp_path / "flask_app" / ".env.example").exists()


def test_snippet_listing_and_metadata_lookup() -> None:
    triggers = [item.trigger for item in list_snippets()]
    assert triggers == [
        "api_get",
        "argparse_cli",
        "env_var",
        "file_append",
        "flask_app",
        "forloop",
        "pandas_csv",
        "readfile",
        "requests_json",
        "tryexcept",
        "writejson",
    ]
    snippet = get_snippet("forloop")
    assert snippet is not None
    assert snippet.category == "loops"
    assert snippet.placeholders[0].name == "iterable"


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
        PythonScaffoldIntent(template="api_tool", name="weather_client", features=("requests", "json_output", "env_config"))
    )
    assert result.template == "api_tool"
    assert "main.py" in result.files
    assert ".env.example" in result.files
    assert "Bounded scaffold bridge only" in result.note


def test_fix_engine_and_traceback_helpers(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("if True\n    print('x')\n", encoding="utf-8")
    fixes = suggest_fixes(bad)
    issue_types = [issue["issue_type"] for issue in fixes["issues"]]
    assert "missing_colon" in issue_types or "syntax_error" in issue_types

    tb_text = """Traceback (most recent call last):
  File \"app.py\", line 9, in <module>
    print(1 + \"x\")
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""
    summary = parse_traceback(tb_text)
    assert summary["exception_type"] == "TypeError"
    assert summary["line_number"] == 9

    tb_fixes = suggest_fixes_for_traceback_text(tb_text)
    assert tb_fixes["issues"]


def test_intent_scaffold_classifier() -> None:
    result = classify_intent("build a flask starter app")
    assert result["template"] == "flask_app"
    assert result["confidence"] in {"high", "medium"}


def test_cli_phipython_v11_commands(capsys, tmp_path: Path) -> None:
    code_file = tmp_path / "hello.py"
    code_file.write_text("import argparse\nname + 'x'\n", encoding="utf-8")

    trace_file = tmp_path / "trace.txt"
    trace_file.write_text(
        "Traceback (most recent call last):\n  File \"main.py\", line 2, in <module>\n    name\nNameError: name 'name' is not defined\n",
        encoding="utf-8",
    )

    assert main(["phipython", "show-template", "flask_app", "--report", "json"]) == 0
    assert "flask_app" in capsys.readouterr().out

    assert main(["phipython", "show-snippet", "api_get", "--report", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["trigger"] == "api_get"
    assert "expanded" in out

    assert main(["phipython", "fix", str(code_file), "--report", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["issues"]

    assert main(["phipython", "fix-traceback", str(trace_file), "--report", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["traceback_summary"]["exception_type"] == "NameError"

    scaffold_dir = tmp_path / "from_intent"
    assert (
        main(
            [
                "phipython",
                "scaffold",
                "--from-intent",
                "create a requests-based API tool",
                "--output-dir",
                str(scaffold_dir),
            ]
        )
        == 0
    )
    assert (scaffold_dir / "main.py").exists()


def test_cli_phipython_unknown_items_return_nonzero(capsys) -> None:
    assert main(["phipython", "init", "missing_template"]) == 1
    assert "unknown template" in capsys.readouterr().out

    assert main(["phipython", "show-snippet", "missing_trigger"]) == 1
    assert "unknown snippet" in capsys.readouterr().out
