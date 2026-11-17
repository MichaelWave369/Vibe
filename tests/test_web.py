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


COMPONENTS = Path("vibe/examples/web_components.vibe")


def test_reusable_components_roundtrip_and_shared_state():
    import re
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    source = COMPONENTS.read_text(encoding="utf-8")
    program = parse_source(source)
    assert program.web_page is not None
    assert program.web_page.uses == ["CounterCard", "CounterCard", "ResetCard"]
    assert set(program.web_page.components) == {"CounterCard", "ResetCard"}

    ir = ast_to_ir(program)
    assert ir.module.web_page is not None
    assert len(ir.module.web_page.components) == 2
    assert ir.web_page is not None
    assert ir.web_page.uses == program.web_page.uses
    assert "CounterCard" in serialize_ir(ir)

    html, backend = emit_code(ir)
    assert backend.target == "web"
    assert html.count('class="vibe-component"') == 3
    assert html.count("Shared count:") == 2
    match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert match is not None
    config = json.loads(match.group(1))
    assert config["state"] == {"count": 3}
    assert config["texts"].count("Shared count: {count}") == 2
    assert [button["variable"] for button in config["buttons"]] == ["count", "count", "count"]
    assert config["buttons"][2]["operation"] == "="


def test_component_references_fail_closed():
    source = COMPONENTS.read_text(encoding="utf-8").replace("use ResetCard", "use MissingCard")
    with pytest.raises(WebSpecError, match="unknown component"):
        parse_web_source(source)


def test_component_state_binding_fails_closed():
    source = COMPONENTS.read_text(encoding="utf-8").replace("Shared count: {count}", "Shared count: {password}")
    with pytest.raises(WebSpecError, match="unknown state"):
        parse_web_source(source)


def test_component_action_safety():
    source = COMPONENTS.read_text(encoding="utf-8").replace("count += 1", "eval(window.bad())")
    with pytest.raises(WebSpecError, match="only integer state assignments"):
        parse_web_source(source)


def test_compiler_emits_reusable_components(tmp_path):
    from vibe.cli import main

    source = tmp_path / "components.vibe"
    source.write_text(COMPONENTS.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(source), "--no-cache"]) == 0
    html = source.with_suffix(".html").read_text(encoding="utf-8")
    assert html.count('class="vibe-component"') == 3


INSTANCES = Path("vibe/examples/web_instances.vibe")


def _instance_config():
    import re
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    program = parse_source(INSTANCES.read_text(encoding="utf-8"))
    assert program.web_page is not None
    ir = ast_to_ir(program)
    assert ir.web_page is not None
    html, backend = emit_code(ir)
    assert backend.target == "web"
    assert "use_prop_refs" in serialize_ir(ir)
    match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert match is not None
    return program, ir, html, json.loads(match.group(1))


def test_component_props_and_local_state_roundtrip():
    program, ir, html, config = _instance_config()
    assert program.web_page.uses == ["CounterCard", "CounterCard"]
    assert program.web_page.use_props == [{"label": "Alpha"}, {"label": "Beta"}]
    assert program.web_page.components["CounterCard"].props == ["label"]
    assert ir.web_page.components["CounterCard"].state == {"count": 0}
    assert ir.web_page.components["CounterCard"].bounds == {"count": (0, 9)}
    assert ir.web_page.use_props == program.web_page.use_props
    assert config["scope_states"] == {
        "instance_0": {"count": 0}, "instance_1": {"count": 0},
    }
    assert config["scope_bounds"]["instance_1"] == {"count": [0, 9]}
    assert config["text_props"][1:] == [{"label": "Alpha"}, {"label": "Beta"}]
    assert config["text_scopes"] == [None, "instance_0", "instance_1"]
    assert len(set(action["scope"] for action in config["buttons"][1:])) == 2
    assert html.count('class="vibe-component"') == 2


def test_component_props_validation_fails_closed():
    source = INSTANCES.read_text(encoding="utf-8")
    with pytest.raises(WebSpecError, match="requires exactly props"):
        parse_web_source(source.replace('use CounterCard label="Alpha"', "use CounterCard"))
    with pytest.raises(WebSpecError, match="requires exactly props"):
        parse_web_source(source.replace('label="Alpha"', 'label="Alpha" unknown="x"'))
    with pytest.raises(WebSpecError, match="duplicate component prop"):
        parse_web_source(source.replace('label="Alpha"', 'label="Alpha" label="Again"'))
    with pytest.raises(WebSpecError, match="component props must be bounded strings"):
        parse_web_source(source.replace('label="Alpha"', "label=123"))


def test_component_local_state_bounds_and_bindings_fail_closed():
    source = INSTANCES.read_text(encoding="utf-8")
    with pytest.raises(WebSpecError, match="outside bounds"):
        parse_web_source(source.replace("state count: 0", "state count: 99"))
    with pytest.raises(WebSpecError, match="unknown state"):
        parse_web_source(source.replace("action: count += 1", "action: missing += 1"))
    with pytest.raises(WebSpecError, match="unknown state or prop"):
        parse_web_source(source.replace("{label}: {count}", "{unknown}: {count}"))
    with pytest.raises(WebSpecError, match="collides with state"):
        parse_web_source(
            source.replace("prop label: string", "prop count: string")
                  .replace('label="Alpha"', 'count="Alpha"')
                  .replace('label="Beta"', 'count="Beta"')
        )
    with pytest.raises(WebSpecError, match="only integer state assignments"):
        parse_web_source(source.replace("action: count += 1", "action: count += total"))


def test_component_string_props_escape_in_serialized_markup():
    source = INSTANCES.read_text(encoding="utf-8").replace('label="Alpha"', 'label="<script>alert(1)</script>"')
    page, _ = parse_web_source(source)
    html = render_html(page)
    assert "<script>alert(1)</script>" not in html
    assert r"\u003cscript\u003e" in html


def test_standard_compiler_builds_instance_page(tmp_path):
    from vibe.cli import main

    path = tmp_path / "instances.vibe"
    path.write_text(INSTANCES.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(path), "--no-cache"]) == 0
    assert "scope_states" in path.with_suffix(".html").read_text(encoding="utf-8")
