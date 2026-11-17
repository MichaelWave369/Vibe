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


FORM_GRID = Path("vibe/examples/web_forms_grid.vibe")


def test_phase3c_layout_and_inputs_roundtrip():
    import re
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    source = FORM_GRID.read_text(encoding="utf-8")
    program = parse_source(source)
    assert program.web_page is not None
    assert program.web_page.layout == "grid"
    assert program.web_page.inputs[0].variable == "shared"
    assert program.web_page.components["MeterCard"].inputs[0].variable == "meter"
    ir = ast_to_ir(program)
    assert ir.web_page is not None
    assert ir.web_page.layout == "grid"
    assert ir.web_page.components["MeterCard"].inputs[0].variable == "meter"
    assert '"layout_ref"' in serialize_ir(ir)
    html, backend = emit_code(ir)
    assert backend.target == "web"
    assert 'class="vibe-layout vibe-layout-grid"' in html
    assert html.count('type="number"') == 3
    assert html.count('data-vibe-input=') == 3
    assert 'for="vibe-input-1"' in html
    config_match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert config_match
    config = json.loads(config_match.group(1))
    assert config["inputs"] == [
        {"variable": "shared", "scope": None},
        {"variable": "meter", "scope": "instance_0"},
        {"variable": "meter", "scope": "instance_1"},
    ]


def test_phase3c_input_bindings_fail_closed():
    source = FORM_GRID.read_text(encoding="utf-8")
    with pytest.raises(WebSpecError, match="unknown state"):
        parse_web_source(source.replace('input "Set shared value": shared', 'input "Set shared value": missing'))
    with pytest.raises(WebSpecError, match="unknown state"):
        parse_web_source(source.replace('input "Set meter value": meter', 'input "Set meter value": missing'))
    with pytest.raises(WebSpecError, match="expected input"):
        parse_web_source(source.replace('input "Set shared value": shared', 'input "Set shared value": shared()'))
    with pytest.raises(WebSpecError, match="layout must be stack or grid"):
        parse_web_source(source.replace("layout: grid", "layout: javascript"))


def test_phase3c_input_label_escaped():
    source = FORM_GRID.read_text(encoding="utf-8").replace(
        'input "Set shared value": shared', 'input "<img src=x onerror=alert(1)>": shared'
    )
    page, _ = parse_web_source(source)
    html = render_html(page)
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '<img src=x onerror=alert(1)>' not in html


def test_phase3c_standard_compiler_emits_grid(tmp_path):
    from vibe.cli import main

    path = tmp_path / "forms.vibe"
    path.write_text(FORM_GRID.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(path), "--no-cache"]) == 0
    html = path.with_suffix(".html").read_text(encoding="utf-8")
    assert "vibe-layout-grid" in html
    assert 'data-vibe-input="2"' in html


TEXT_FORMS = Path("vibe/examples/web_text_forms.vibe")


def test_phase3d_text_and_select_roundtrip():
    import re
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    program = parse_source(TEXT_FORMS.read_text(encoding="utf-8"))
    assert program.web_page is not None
    assert program.web_page.text_state == {"display_name": "Mikey", "theme": "Teal"}
    assert program.web_page.text_fields[0].kind == "text"
    assert program.web_page.text_fields[0].maximum == 24
    assert program.web_page.text_fields[1].options == ("Teal", "Purple", "Gold")
    component = program.web_page.components["ProfileCard"]
    assert component.text_state == {"name": "Visitor", "mood": "Calm"}
    assert component.text_fields[1].kind == "select"
    ir = ast_to_ir(program)
    assert ir.web_page is not None
    assert ir.web_page.text_state == program.web_page.text_state
    assert ir.web_page.components["ProfileCard"].text_fields == component.text_fields
    assert "text_field_refs" in serialize_ir(ir)
    html, backend = emit_code(ir)
    assert backend.target == "web"
    assert html.count('data-vibe-string=') == 6
    assert html.count('<select ') == 3
    assert html.count('type="text"') == 3
    assert 'aria-describedby="vibe-string-error-0"' in html
    assert 'id="vibe-string-error-5" role="status"' in html
    match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert match is not None
    config = json.loads(match.group(1))
    assert config["text_state"] == {"display_name": "Mikey", "theme": "Teal"}
    assert config["scope_text_states"] == {
        "instance_0": {"name": "Visitor", "mood": "Calm"},
        "instance_1": {"name": "Visitor", "mood": "Calm"},
    }
    assert len(config["string_fields"]) == 6
    assert [item["scope"] for item in config["string_fields"]] == [
        None, None, "instance_0", "instance_0", "instance_1", "instance_1"
    ]


def test_phase3d_rejects_invalid_initial_string_and_missing_state():
    source = TEXT_FORMS.read_text(encoding="utf-8")
    with pytest.raises(WebSpecError, match="violates length bounds"):
        parse_web_source(source.replace('display_name: "Mikey"', 'display_name: "M"'))
    with pytest.raises(WebSpecError, match="not an allowed option"):
        parse_web_source(source.replace('theme: "Teal"', 'theme: "Undefined"'))
    with pytest.raises(WebSpecError, match="unknown text state"):
        parse_web_source(source.replace('input_text "Display name": display_name', 'input_text "Display name": missing'))
    with pytest.raises(WebSpecError, match="invalid text length bounds"):
        parse_web_source(source.replace("min=2 max=24", "min=27 max=24"))
    with pytest.raises(WebSpecError, match="distinct nonempty"):
        parse_web_source(source.replace('options="Teal|Purple|Gold"', 'options="Teal|Teal"'))
    with pytest.raises(WebSpecError, match="collide"):
        parse_web_source(source.replace('display_name: "Mikey"', 'total: "Mikey"'))
    with pytest.raises(WebSpecError, match="unknown state or prop"):
        parse_web_source(source.replace("{caption}: {name}", "{caption}: {password}"))


def test_phase3d_escapes_option_markup_and_labels():
    source = TEXT_FORMS.read_text(encoding="utf-8")
    source = source.replace('options="Teal|Purple|Gold"', 'options="Teal|<img src=x onerror=alert(1)>|Gold"')
    page, _ = parse_web_source(source)
    html = render_html(page)
    assert "&lt;img" in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert r"\u003cimg" in html


def test_phase3d_compiles_with_standard_vibec(tmp_path):
    from vibe.cli import main

    source = tmp_path / "text_forms.vibe"
    source.write_text(TEXT_FORMS.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(source), "--no-cache"]) == 0
    html = source.with_suffix(".html").read_text(encoding="utf-8")
    assert 'data-vibe-string="5"' in html


DRAFTS = Path("vibe/examples/web_drafts.vibe")


def test_phase3e_submit_and_persistence_roundtrip():
    import re
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    program = parse_source(DRAFTS.read_text(encoding="utf-8"))
    assert program.web_page is not None
    assert program.web_page.submit_label == "Save local draft"
    assert program.web_page.persistence == "local"
    ir = ast_to_ir(program)
    assert ir.web_page is not None
    assert ir.web_page.submit_label == program.web_page.submit_label
    assert ir.web_page.persistence == "local"
    assert '"submit_label_ref"' in serialize_ir(ir)
    assert '"persistence_ref"' in serialize_ir(ir)
    html, backend = emit_code(ir)
    assert backend.target == "web"
    assert html.count('<form id="vibe-form" novalidate>') == 1
    assert html.count('</form>') == 1
    assert 'id="vibe-form-status" role="status"' in html
    assert '<button type="submit">Save local draft</button>' in html
    match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert match
    config = json.loads(match.group(1))
    assert config["page_id"] == "FormStudio"
    assert config["persistence"] == "local"
    assert config["storage_key"] == "vibeweb:draft:v1:FormStudio"
    assert config["scope_text_states"]["instance_1"]["name"] == "Visitor"
    assert "vibe:submit" in html


def test_phase3e_submit_disabled_in_old_examples():
    import re
    page, _ = parse_web_source(TEXT_FORMS.read_text(encoding="utf-8"))
    assert page.submit_label == ""
    assert page.persistence == "none"
    html = render_html(page)
    assert 'id="vibe-form"' not in html
    match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert match
    config = json.loads(match.group(1))
    assert config["persistence"] == "none"
    assert config["storage_key"] is None


def test_phase3e_fails_closed_for_invalid_persistence():
    source = DRAFTS.read_text(encoding="utf-8")
    with pytest.raises(WebSpecError, match="supports only local"):
        parse_web_source(source.replace("persist: local", "persist: cloud"))
    with pytest.raises(WebSpecError, match="requires an explicit submit"):
        parse_web_source(source.replace('submit: "Save local draft"', ""))
    with pytest.raises(WebSpecError, match="duplicate submit"):
        parse_web_source(source.replace('submit: "Save local draft"', 'submit: "Save local draft"\n  submit: "Again"'))
    with pytest.raises(WebSpecError, match="duplicate persistence"):
        parse_web_source(source.replace("persist: local", "persist: local\n  persist: local"))


def test_phase3e_submit_label_escaped():
    source = DRAFTS.read_text(encoding="utf-8").replace(
        'submit: "Save local draft"', 'submit: "<img src=x onerror=alert(1)>"'
    )
    page, _ = parse_web_source(source)
    html = render_html(page)
    assert "&lt;img" in html
    assert "<img src=x onerror=alert(1)>" not in html


def test_phase3e_standard_compiler_builds_local_draft(tmp_path):
    from vibe.cli import main

    path = tmp_path / "draft.vibe"
    path.write_text(DRAFTS.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(path), "--no-cache"]) == 0
    assert 'id="vibe-form-status"' in path.with_suffix(".html").read_text(encoding="utf-8")


TYPING = Path("vibe/examples/web_typing_dojo.vibe")


def test_typing_dojo_round_trip_native_compiler():
    import re
    from vibe.parser import parse_source
    from vibe.ir import ast_to_ir, serialize_ir
    from vibe.emitter import emit_code

    source = TYPING.read_text(encoding="utf-8")
    program = parse_source(source)
    assert program.web_page is not None
    assert program.web_page.typing is not None
    passage = "Precision matters.  Two spaces are welcome here."
    assert program.web_page.typing.passage == passage
    assert program.web_page.state == {}
    ir = ast_to_ir(program)
    assert ir.web_page is not None
    assert ir.web_page.typing is not None
    assert ir.web_page.typing.passage == passage
    serialized = serialize_ir(ir)
    assert '"typing"' in serialized
    assert '"passage_ref"' in serialized
    html, backend = emit_code(ir)
    assert backend.target == "web"
    assert 'id="vibe-typing-input"' in html
    assert 'id="vibe-typing-progress"' in html
    assert 'id="vibe-typing-accuracy"' in html
    assert "Two spaces are welcome here." in html
    match = re.search(r'<script type="application/json" id="vibe-config">(.*?)</script>', html, re.S)
    assert match
    config = json.loads(match.group(1))
    assert config["typing"] == {"passage": passage}
    assert html.count('id="vibe-typing"') == 1
    assert html.count('id="vibe-typing-reset"') == 1


def test_typing_grammar_rejects_unsafe_and_malformed_passages():
    source = TYPING.read_text(encoding="utf-8")
    with pytest.raises(WebSpecError, match="12-240"):
        parse_web_source(source.replace("Precision matters.  Two spaces are welcome here.", "Short"))
    with pytest.raises(WebSpecError, match="12-240"):
        parse_web_source(source.replace("Precision matters.  Two spaces are welcome here.", " " * 15))
    with pytest.raises(WebSpecError, match="printable ASCII"):
        parse_web_source(source.replace("Precision matters.", "Precision ☃."))
    with pytest.raises(WebSpecError, match="expected one typing passage"):
        parse_web_source(source.replace('    passage: "Precision', '    passage: "Precision').replace(
            'passage: "Precision matters.  Two spaces are welcome here."',
            'passage: "Precision matters.  Two spaces are welcome here."\n    passage: "Another passage is not permitted"'
        ))
    with pytest.raises(WebSpecError, match="expected one typing passage"):
        parse_web_source(source.replace('passage: "Precision matters.  Two spaces are welcome here."',
                                        'script: "alert(1)"'))
    with pytest.raises(WebSpecError, match="invalid indentation or unsupported construct"):
        parse_web_source(source.replace('passage: "Precision matters.  Two spaces are welcome here."',
                                        'passage: "Precision matters.  Two spaces are welcome here."\n      js: "bad"'))


def test_typing_html_escapes_literal_script_attack():
    source = TYPING.read_text(encoding="utf-8")
    source = source.replace(
        "Precision matters.  Two spaces are welcome here.",
        "Enter </script><script>alert(1)</script> exactly."
    )
    page, _ = parse_web_source(source)
    html = render_html(page)
    assert "&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert r"\u003c/script\u003e" in html


def test_typing_standard_vibec_compile(tmp_path):
    from vibe.cli import main
    source = tmp_path / "dojo.vibe"
    source.write_text(TYPING.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(source), "--no-cache"]) == 0
    output = source.with_suffix(".html").read_text(encoding="utf-8")
    assert "Keyboard dojo" in output
    assert "vibe-typing-status" in output
