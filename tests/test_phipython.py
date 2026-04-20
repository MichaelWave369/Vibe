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
    preview_patch_plan_for_file,
    run_patch,
    run_patch_traceback,
    suggest_fixes,
    suggest_fixes_for_traceback_text,
    summarize_traceback_chain,
    translate_error,
)
from vibe.phipython.patch_plans import list_patch_plans


def test_template_listing_and_richer_scaffold_generation(tmp_path: Path) -> None:
    templates = [tpl.name for tpl in list_templates()]
    assert templates == ["api_tool", "automation", "cli", "dashboard", "flask_app", "scraper"]

    for template in templates:
        out = tmp_path / template
        rc = main(["phipython", "init", template, "--output-dir", str(out)])
        assert rc == 0
        assert (out / "README.md").exists()
        assert (out / "main.py").exists()
        assert (out / ".phipython.json").exists()

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


def test_chained_traceback_summary() -> None:
    chained = """Traceback (most recent call last):
  File \"app.py\", line 3, in <module>
    int("nope")
ValueError: invalid literal for int() with base 10: 'nope'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File \"app.py\", line 6, in <module>
    raise RuntimeError("failed")
RuntimeError: failed
"""
    payload = summarize_traceback_chain(chained)
    assert payload["final_exception"] == "RuntimeError"
    assert len(payload["stages"]) >= 2


def test_intent_scaffold_classifier() -> None:
    result = classify_intent("build a flask starter app")
    assert result["template"] == "flask_app"
    assert result["confidence"] in {"high", "medium"}


def test_patch_preview_apply_and_rejection(tmp_path: Path) -> None:
    target = tmp_path / "patch_me.py"
    target.write_text("requests.get('https://example.com')\n", encoding="utf-8")

    preview = run_patch(target, issue_type="missing_import", apply=False)
    assert preview["can_apply"] is True
    assert "import requests" in preview["preview"]["after"]
    assert preview["applied"] is False

    applied = run_patch(target, issue_type="missing_import", apply=True)
    assert applied["applied"] is True
    assert target.read_text(encoding="utf-8").startswith("import requests")

    reject = run_patch(target, issue_type="unsupported_issue", apply=True)
    assert reject["can_apply"] is False
    assert reject["applied"] is False

    interactive = main(["phipython", "patch", str(target), "--interactive", "--report", "json"])
    assert interactive == 0


def test_multi_file_patch_plan_preview_and_apply(tmp_path: Path) -> None:
    target = tmp_path / "main.py"
    target.write_text("def main():\n    return 1\n", encoding="utf-8")
    plan = preview_patch_plan_for_file(target, "plan-002")
    assert plan["can_apply"] is True
    assert plan["files"]


def test_patch_plan_rejection_and_env_stub_generation(tmp_path: Path) -> None:
    target = tmp_path / "main.py"
    target.write_text("print('hello')\n", encoding="utf-8")
    empty = list_patch_plans(target)
    assert empty["plans"] == []
    assert "rejection_reason" in empty

    (tmp_path / ".phipython.json").write_text(json.dumps({"template": "api_tool"}), encoding="utf-8")
    target.write_text("def main():\n    return 1\n", encoding="utf-8")
    listing = list_patch_plans(target)
    plan_ids = {plan["plan_id"] for plan in listing["plans"]}
    assert "plan-003" in plan_ids


def test_cli_phipython_v12_commands(capsys, tmp_path: Path) -> None:
    code_file = tmp_path / "hello.py"
    code_file.write_text("requests.get('https://example.com')\n", encoding="utf-8")

    trace_file = tmp_path / "trace.txt"
    trace_file.write_text(
        "Traceback (most recent call last):\n  File \"main.py\", line 1, in <module>\n    requests.get('x')\nModuleNotFoundError: No module named 'requests'\n",
        encoding="utf-8",
    )

    project = tmp_path / "proj"
    assert main(["phipython", "init", "cli", "--output-dir", str(project)]) == 0
    capsys.readouterr()

    assert main(["phipython", "doctor", str(project), "--report", "json"]) == 0
    doctor_out = json.loads(capsys.readouterr().out)
    assert doctor_out["status"] in {"ok", "warn"}
    assert any(check["id"] == "cli.usage_example" for check in doctor_out["checks"])

    assert main(["phipython", "inspect-project", str(project), "--report", "json"]) == 0
    inspect_out = json.loads(capsys.readouterr().out)
    assert inspect_out["metadata_exists"] is True

    assert main(["phipython", "patch", str(code_file), "--preview", "--report", "json"]) == 0
    patch_out = json.loads(capsys.readouterr().out)
    assert "can_apply" in patch_out

    assert main(["phipython", "patch", str(code_file), "--apply", "--report", "json"]) == 0
    apply_out = json.loads(capsys.readouterr().out)
    assert apply_out["applied"] in {True, False}

    assert main(["phipython", "patch-traceback", str(trace_file), "--preview", "--report", "json"]) == 0
    trace_out = json.loads(capsys.readouterr().out)
    assert "traceback_summary" in trace_out

    assert main(["phipython", "patch", str(code_file), "--interactive", "--report", "json"]) == 0
    patch_list = json.loads(capsys.readouterr().out)
    assert patch_list["mode"] == "interactive_selection"

    if patch_list["candidates"]:
        first_id = patch_list["candidates"][0]["patch_id"]
        assert (
            main(
                [
                    "phipython",
                    "patch",
                    str(code_file),
                    "--select",
                    first_id,
                    "--preview",
                    "--report",
                    "json",
                ]
            )
            == 0
        )
        selected = json.loads(capsys.readouterr().out)
        assert selected["can_apply"] is True

    export_dir = tmp_path / "artifacts"
    assert main(["phipython", "doctor", str(project), "--export", str(export_dir), "--report", "json"]) == 0
    assert (export_dir / "phipython_doctor.json").exists()

    assert main(["phipython", "inspect-project", str(project), "--export", str(export_dir), "--report", "json"]) == 0
    assert (export_dir / "phipython_inspect_project.json").exists()


def test_phipython_v14_testgen_receipts_and_bundle(capsys, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    assert main(["phipython", "init", "cli", "--output-dir", str(project)]) == 0
    capsys.readouterr()

    assert main(["phipython", "testgen", str(project), "--preview", "--report", "json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["can_generate"] is True
    assert preview["applied"] is False

    assert main(["phipython", "testgen", str(project), "--apply", "--report", "json"]) == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["applied"] is True
    assert (project / ".phipython.tests.json").exists()

    code_file = project / "main.py"
    assert main(["phipython", "patch", str(code_file), "--preview", "--report", "json"]) == 0
    capsys.readouterr()
    assert main(["phipython", "receipts", str(project), "--report", "json"]) == 0
    receipts = json.loads(capsys.readouterr().out)
    assert receipts["receipts"]

    bundle_dir = tmp_path / "bundle"
    assert main(["phipython", "bundle", str(project), "--out", str(bundle_dir), "--report", "json"]) == 0
    bundle = json.loads(capsys.readouterr().out)
    assert Path(bundle["artifacts"]["doctor"]).exists()
    assert (bundle_dir / "test_manifest.json").exists()

    assert main(["phipython", "show-test-profile", "cli", "--report", "json"]) == 0
    profile = json.loads(capsys.readouterr().out)
    assert profile["template"] == "cli"

    assert main(["phipython", "doctor", str(project), "--report", "json"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    check_ids = {check["id"] for check in doctor["checks"]}
    assert "tests.present" in check_ids
    assert "tests.manifest_present" in check_ids


def test_patch_traceback_file_not_found(tmp_path: Path) -> None:
    trace_file = tmp_path / "trace_unknown.txt"
    trace_file.write_text(
        "Traceback (most recent call last):\n  File \"/no/such/file.py\", line 1, in <module>\n    x\nNameError: name 'x' is not defined\n",
        encoding="utf-8",
    )
    out = run_patch_traceback(trace_file, apply=True)
    assert out["can_apply"] is False


def test_cli_phipython_unknown_items_return_nonzero(capsys) -> None:
    assert main(["phipython", "init", "missing_template"]) == 1
    assert "unknown template" in capsys.readouterr().out

    assert main(["phipython", "show-snippet", "missing_trigger"]) == 1
    assert "unknown snippet" in capsys.readouterr().out
