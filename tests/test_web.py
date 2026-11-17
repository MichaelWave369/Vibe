"""VibeWeb v0 parser and renderer safety checks."""
import json
from pathlib import Path

import pytest

from vibe.web import WebSpecError, parse_web_source, render_html, build


EXAMPLE = Path("vibe/examples/web_counter.vibe")


def test_counter_compiles_to_independent_html(tmp_path):
    report = build(EXAMPLE, tmp_path)
    output = (tmp_path / "index.html").read_text()
    assert report["result"] == "emitted"
    assert report["bridge_passed"] is True
    assert "data-vibe-button=\"0\"" in output
    assert "JSON.parse" in output
    assert "Count: {count}" in output
    assert "react" not in output.lower().split("<script")[0].replace("no react, svelte", "")
    assert json.loads((tmp_path / "vibeweb.report.json").read_text())["bridge_passed"] is True


def test_unknown_variable_fails_closed():
    source = EXAMPLE.read_text().replace("Count: {count}", "Count: {secret}")
    with pytest.raises(WebSpecError, match="unknown state"):
        parse_web_source(source)


def test_unsupported_action_fails_closed():
    source = EXAMPLE.read_text().replace("count += 1", "eval(hack())")
    with pytest.raises(WebSpecError, match="only"):
        parse_web_source(source)


def test_html_injection_escaped_and_json_script_safe():
    source = EXAMPLE.read_text().replace('"Increase"', '"<img src=x onerror=alert(1)>"')
    source = source.replace('"Count: {count}"', '"</script><script>alert(1)</script> {count}"')
    page, _ = parse_web_source(source)
    output = render_html(page)
    assert "&lt;img" in output
    assert "\\u003c/script\\u003e" in output
    assert output.count("<script") == 2
    assert "<script>alert(1)</script>" not in output


def test_bounds_initial_state_checked():
    source = EXAMPLE.read_text().replace("count: 0..369", "count: 1..369")
    with pytest.raises(WebSpecError, match="outside bounds"):
        parse_web_source(source)


def test_page_name_must_match_intent(tmp_path):
    source = EXAMPLE.read_text().replace("page CounterPage:", "page Stranger:")
    path = tmp_path / "bad.vibe"
    path.write_text(source)
    with pytest.raises(WebSpecError, match="must match intent"):
        build(path, tmp_path / "output")


def test_native_parser_and_typed_web_ir():
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    program = parse_source(EXAMPLE.read_text(encoding="utf-8"))
    assert program.emit_target == "web"
    assert program.web_page is not None
    assert program.web_page.state["count"] == 0
    ir = ast_to_ir(program)
    assert ir.emit_target == "web"
    assert ir.module.web_page is not None
    assert ir.web_page.bounds["count"] == (0, 369)
    assert ir.web_page.buttons[0].operation == "+="
    html, backend = emit_code(ir)
    assert backend.extension == ".html"
    assert "The first VibeWeb page" in html
    assert '"web_page"' in serialize_ir(ir)


def test_native_parser_rejects_web_without_page():
    from vibe.parser import parse_source, ParseError

    source = EXAMPLE.read_text(encoding="utf-8")
    source = source.replace("page CounterPage:", "notpage CounterPage:")
    with pytest.raises(ParseError):
        parse_source(source)


def test_standard_vibec_compile_web(tmp_path):
    from vibe.cli import main

    source = tmp_path / "first_light.vibe"
    source.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(source), "--no-cache"]) == 0
    html = source.with_suffix(".html").read_text(encoding="utf-8")
    assert "data-vibe-button" in html
    assert "Count: {count}" in html
