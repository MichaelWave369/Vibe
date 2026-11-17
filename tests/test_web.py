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
