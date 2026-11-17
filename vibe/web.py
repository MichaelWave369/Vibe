"""VibeWeb v0: bounded, dependency-free, reactive HTML emitter for Vibe.

The bounded `page` grammar is now recognized by Vibe's primary parser and
lowered into typed SSA IR. The standalone web build remains supported.
No arbitrary JavaScript expressions, templates, or imports are executed.
"""
from __future__ import annotations

import argparse
from .ast import WebButton as Button, WebPage, WebComponent, WebInput, WebStringField
from html import escape
import json
from pathlib import Path
import re
import sys


class WebSpecError(ValueError):
    """Invalid or unsupported VibeWeb source syntax."""


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BINDING = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ACTION = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(\+=|-=|=)\s*(-?\d+)$")
_PAGE = re.compile(r"^page ([A-Za-z_][A-Za-z0-9_]*):$")
_BUTTON = re.compile(r'^button\s+("(?:[^"\\]|\\.)*"):$')
_COMPONENT = re.compile(r"^component ([A-Za-z_][A-Za-z0-9_]*):$")


def _quoted(text: str, line: int) -> str:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WebSpecError(f"line {line}: expected a double-quoted JSON string") from exc
    if not isinstance(value, str):
        raise WebSpecError(f"line {line}: expected a string")
    if len(value) > 4000:
        raise WebSpecError(f"line {line}: string too long")
    return value


def _integer(text: str, line: int) -> int:
    if not re.fullmatch(r"-?\d{1,12}", text):
        raise WebSpecError(f"line {line}: expected a bounded integer literal")
    return int(text)


def _parse_use(text: str, line: int) -> tuple[str, dict[str, str]]:
    """Parse a component use and bounded JSON-quoted string properties."""
    match = re.fullmatch(r"use\s+([A-Za-z_][A-Za-z0-9_]*)(.*)", text)
    if not match:
        raise WebSpecError(f"line {line}: expected use ComponentName [prop=\\\"value\\\"]")
    name, rest = match.groups()
    args: dict[str, str] = {}
    decoder = json.JSONDecoder()
    while rest.strip():
        rest = rest.lstrip()
        prop = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*", rest)
        if prop is None or len(args) >= 16:
            raise WebSpecError(f"line {line}: invalid component prop assignment")
        key = prop.group(1)
        if key in args:
            raise WebSpecError(f"line {line}: duplicate component prop {key!r}")
        try:
            value, consumed = decoder.raw_decode(rest[prop.end():])
        except json.JSONDecodeError as exc:
            raise WebSpecError(f"line {line}: component prop must be a JSON-quoted string") from exc
        if not isinstance(value, str) or len(value) > 4000:
            raise WebSpecError(f"line {line}: component props must be bounded strings")
        rest = rest[prop.end() + consumed:]
        if rest and not rest[0].isspace():
            raise WebSpecError(f"line {line}: separate props with spaces")
        args[key] = value
    return name, args


def _parse_input(text: str, line: int) -> WebInput:
    match = re.fullmatch(r'input\s+("(?:[^"\\]|\\.)*"):\s*([A-Za-z_][A-Za-z0-9_]*)', text)
    if not match:
        raise WebSpecError(f"line {line}: expected input \"Label\": state_name")
    return WebInput(_quoted(match.group(1), line), match.group(2))


def _parse_string_field(text: str, line: int) -> WebStringField:
    head = re.fullmatch(r'(input_text|select)\s+("(?:[^"\\]|\\.)*"):\s*([A-Za-z_][A-Za-z0-9_]*)(.*)', text)
    if head is None:
        raise WebSpecError(f"line {line}: expected input_text/select \"Label\": state options")
    kind, raw_label, variable, suffix = head.groups()
    label = _quoted(raw_label, line)
    if not label.strip():
        raise WebSpecError(f"line {line}: field label must not be empty")
    if kind == "input_text":
        length = re.fullmatch(r"\s+min=(\d{1,3})\s+max=(\d{1,3})", suffix)
        if not length:
            raise WebSpecError(f"line {line}: input_text requires min=N max=N")
        minimum, maximum = (int(x) for x in length.groups())
        if not (0 <= minimum <= maximum <= 256) or maximum == 0:
            raise WebSpecError(f"line {line}: invalid text length bounds")
        return WebStringField(label, variable, "text", minimum, maximum)
    choices = re.fullmatch(r'\s+options=("(?:[^"\\]|\\.)*")', suffix)
    if not choices:
        raise WebSpecError(f"line {line}: select requires options=\"A|B|C\"")
    options = tuple(_quoted(choices.group(1), line).split("|"))
    if not (2 <= len(options) <= 16) or len(set(options)) != len(options) or any(
        not option.strip() or len(option) > 80 for option in options
    ):
        raise WebSpecError(f"line {line}: select options must be 2-16 distinct nonempty values")
    return WebStringField(label, variable, "select", options=options)


def parse_web_source(source: str) -> tuple[WebPage, str]:
    """Parse a *restricted* page block and return the standard Vibe contract.

    Unsupported constructs fail closed. The returned core source uses the
    existing TypeScript target solely for legacy parsing compatibility;
    Vibe's native parser records the page AST and the web emitter produces HTML.
    """
    raw = source.splitlines(keepends=True)
    start = None
    end = None
    name = None
    for i, line in enumerate(raw):
        text = line.strip()
        if line.startswith("page "):
            if start is not None:
                raise WebSpecError("only one page block is supported in v0")
            m = _PAGE.fullmatch(text)
            if not m:
                raise WebSpecError(f"line {i + 1}: expected `page Name:`")
            start, name = i, m.group(1)
        elif start is not None and end is None and i > start and text and not line[0].isspace() and not text.startswith("#"):
            end = i
    if start is None or name is None:
        raise WebSpecError("missing `page Name:` block")
    if end is None:
        end = len(raw)

    page = WebPage(name=name)
    section = ""
    pending_button: tuple[str, int] | None = None
    current_component: WebComponent | None = None
    for idx in range(start + 1, end):
        line = raw[idx].rstrip("\r\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        n = len(line) - len(line.lstrip(" "))
        value = line.strip()
        if n % 2:
            raise WebSpecError(f"line {idx + 1}: indent with multiples of two spaces")
        if n == 2:
            if pending_button:
                raise WebSpecError(f"line {pending_button[1]}: button missing action")
            pending_button = None
            current_component = None
            if value in {"state:", "text_state:", "view:", "bounds:", "components:"}:
                section = value[:-1]
                continue
            section = ""
            if value.startswith("title:"):
                page.title = _quoted(value.split(":", 1)[1].strip(), idx + 1)
            elif value.startswith("heading:"):
                page.heading = _quoted(value.split(":", 1)[1].strip(), idx + 1)
            elif value.startswith("layout:"):
                mode = value.split(":", 1)[1].strip()
                if mode not in {"stack", "grid"}:
                    raise WebSpecError(f"line {idx + 1}: layout must be stack or grid")
                page.layout = mode
            elif value.startswith("submit:"):
                if page.submit_label:
                    raise WebSpecError(f"line {idx + 1}: duplicate submit declaration")
                label = _quoted(value.split(":", 1)[1].strip(), idx + 1)
                if not label.strip() or len(label) > 80:
                    raise WebSpecError(f"line {idx + 1}: submit label must be 1-80 characters")
                page.submit_label = label
            elif value.startswith("persist:"):
                if page.persistence != "none":
                    raise WebSpecError(f"line {idx + 1}: duplicate persistence declaration")
                policy = value.split(":", 1)[1].strip()
                if policy not in {"local"}:
                    raise WebSpecError(f"line {idx + 1}: persist currently supports only local")
                page.persistence = policy
            else:
                raise WebSpecError(f"line {idx + 1}: unsupported page field {value!r}")
        elif n == 4 and section == "state":
            if ":" not in value:
                raise WebSpecError(f"line {idx + 1}: expected `name: integer`")
            key, number = (t.strip() for t in value.split(":", 1))
            if not _NAME.fullmatch(key) or key in page.state:
                raise WebSpecError(f"line {idx + 1}: invalid or repeated state name")
            page.state[key] = _integer(number, idx + 1)
        elif n == 4 and section == "text_state":
            if ":" not in value:
                raise WebSpecError(f"line {idx + 1}: expected name: \"string\"")
            key, raw_text = (t.strip() for t in value.split(":", 1))
            if not _NAME.fullmatch(key) or key in page.text_state or len(page.text_state) >= 64:
                raise WebSpecError(f"line {idx + 1}: invalid or repeated string state name")
            page.text_state[key] = _quoted(raw_text, idx + 1)
        elif n == 4 and section == "bounds":
            if ":" not in value:
                raise WebSpecError(f"line {idx + 1}: expected `name: min..max`")
            key, range_text = (t.strip() for t in value.split(":", 1))
            pair = re.fullmatch(r"(-?\d{1,12})\.\.(-?\d{1,12})", range_text)
            if not _NAME.fullmatch(key) or not pair or key in page.bounds:
                raise WebSpecError(f"line {idx + 1}: invalid or repeated bounds")
            lo, hi = (int(x) for x in pair.groups())
            if lo > hi:
                raise WebSpecError(f"line {idx + 1}: minimum exceeds maximum")
            page.bounds[key] = (lo, hi)
        elif n == 4 and section == "components":
            if pending_button:
                raise WebSpecError(f"line {pending_button[1]}: button missing action")
            match = _COMPONENT.fullmatch(value)
            if not match:
                raise WebSpecError(f"line {idx + 1}: expected component Name:")
            name = match.group(1)
            if name in page.components or len(page.components) >= 32:
                raise WebSpecError(f"line {idx + 1}: repeated component or component limit exceeded")
            current_component = WebComponent(name=name)
            page.components[name] = current_component
        elif n == 6 and section == "components" and current_component is not None:
            if pending_button:
                raise WebSpecError(f"line {pending_button[1]}: button missing action")
            if value.startswith("prop "):
                match = re.fullmatch(r"prop ([A-Za-z_][A-Za-z0-9_]*): string", value)
                if not match:
                    raise WebSpecError(f"line {idx + 1}: expected prop name: string")
                prop_name = match.group(1)
                if prop_name in current_component.props or len(current_component.props) >= 16:
                    raise WebSpecError(f"line {idx + 1}: duplicate prop or prop limit exceeded")
                current_component.props.append(prop_name)
            elif value.startswith("state "):
                match = re.fullmatch(r"state ([A-Za-z_][A-Za-z0-9_]*):\s*(-?\d{1,12})", value)
                if not match:
                    raise WebSpecError(f"line {idx + 1}: expected state name: integer")
                key, number = match.groups()
                if key in current_component.state or len(current_component.state) >= 32:
                    raise WebSpecError(f"line {idx + 1}: duplicate local state or state limit exceeded")
                current_component.state[key] = int(number)
            elif value.startswith("bounds "):
                match = re.fullmatch(r"bounds ([A-Za-z_][A-Za-z0-9_]*):\s*(-?\d{1,12})\.\.(-?\d{1,12})", value)
                if not match:
                    raise WebSpecError(f"line {idx + 1}: expected bounds name: min..max")
                key, lower, upper = match.groups()
                if key in current_component.bounds or int(lower) > int(upper):
                    raise WebSpecError(f"line {idx + 1}: duplicate or invalid local bounds")
                current_component.bounds[key] = (int(lower), int(upper))
            elif value.startswith("text_state "):
                match = re.fullmatch(r'text_state ([A-Za-z_][A-Za-z0-9_]*):\s*(.*)', value)
                if not match:
                    raise WebSpecError(f"line {idx + 1}: expected text_state name: \"string\"")
                key, raw_text = match.groups()
                if key in current_component.text_state or len(current_component.text_state) >= 32:
                    raise WebSpecError(f"line {idx + 1}: duplicate local string state")
                current_component.text_state[key] = _quoted(raw_text, idx + 1)
            elif value.startswith("text:"):
                current_component.texts.append(_quoted(value.split(":", 1)[1].strip(), idx + 1))
            elif value.startswith("input_text ") or value.startswith("select "):
                current_component.text_fields.append(_parse_string_field(value, idx + 1))
            elif value.startswith("input "):
                current_component.inputs.append(_parse_input(value, idx + 1))
            else:
                match = _BUTTON.fullmatch(value)
                if not match:
                    raise WebSpecError(f"line {idx + 1}: expected prop, state, bounds, component text or button")
                pending_button = (_quoted(match.group(1), idx + 1), idx + 1)
        elif n == 8 and section == "components" and current_component is not None and pending_button:
            if not value.startswith("action:"):
                raise WebSpecError(f"line {idx + 1}: expected action")
            match = _ACTION.fullmatch(value.split(":", 1)[1].strip())
            if not match:
                raise WebSpecError(f"line {idx + 1}: only integer state assignments supported")
            variable, operation, amount = match.groups()
            current_component.buttons.append(Button(pending_button[0], variable, operation, int(amount)))
            pending_button = None
        elif n == 4 and section == "view":
            if pending_button:
                raise WebSpecError(f"line {pending_button[1]}: button missing action")
            if value.startswith("text:"):
                page.texts.append(_quoted(value.split(":", 1)[1].strip(), idx + 1))
                pending_button = None
            elif value.startswith("input_text ") or value.startswith("select "):
                page.text_fields.append(_parse_string_field(value, idx + 1))
            elif value.startswith("input "):
                page.inputs.append(_parse_input(value, idx + 1))
            elif value.startswith("use "):
                name, props = _parse_use(value, idx + 1)
                if len(page.uses) >= 64:
                    raise WebSpecError(f"line {idx + 1}: component use limit exceeded")
                page.uses.append(name)
                page.use_props.append(props)
            else:
                m = _BUTTON.fullmatch(value)
                if not m:
                    raise WebSpecError(f"line {idx + 1}: expected `text:` or `button \"Label\":`")
                pending_button = (_quoted(m.group(1), idx + 1), idx + 1)
        elif n == 6 and section == "view" and pending_button:
            if not value.startswith("action:"):
                raise WebSpecError(f"line {idx + 1}: expected `action:`")
            m = _ACTION.fullmatch(value.split(":", 1)[1].strip())
            if not m:
                raise WebSpecError(f"line {idx + 1}: only `name += N`, `name -= N`, or `name = N` supported")
            variable, operator, amount = m.groups()
            page.buttons.append(Button(pending_button[0], variable, operator, int(amount)))
            pending_button = None
        else:
            raise WebSpecError(f"line {idx + 1}: invalid indentation or unsupported construct")
    if pending_button:
        raise WebSpecError(f"line {pending_button[1]}: button missing action")
    if not page.title or not page.heading:
        raise WebSpecError("page requires title and heading")
    if page.persistence != "none" and not page.submit_label:
        raise WebSpecError("persist local requires an explicit submit declaration")
    if not (page.state or page.text_state or any(component.state or component.text_state for component in page.components.values())):
        raise WebSpecError("page requires page or component state")
    if len(page.uses) != len(page.use_props):
        raise WebSpecError("component use/prop count mismatch")
    for name, props in zip(page.uses, page.use_props):
        if name not in page.components:
            raise WebSpecError(f"unknown component {name!r}")
        expected = set(page.components[name].props)
        if set(props) != expected:
            raise WebSpecError(f"component {name!r} requires exactly props {sorted(expected)}")
    active_components = [page.components[name] for name in page.uses]
    if not (page.texts or any(component.texts for component in active_components)):
        raise WebSpecError("page requires at least one visible text")
    if not (page.buttons or page.inputs or page.text_fields or any(component.buttons or component.inputs or component.text_fields for component in active_components)):
        raise WebSpecError("page requires at least one visible button or input")

    def check_text(template: str, allowed: set[str]) -> None:
        for ref in _BINDING.findall(template):
            if ref not in allowed:
                raise WebSpecError(f"text references unknown state or prop {ref!r}")
        if "{" in _BINDING.sub("", template) or "}" in _BINDING.sub("", template):
            raise WebSpecError("unsupported text interpolation; use {state_name}")

    def check_string_fields(fields: list[WebStringField], state: dict[str, str]) -> None:
        for item in fields:
            if item.variable not in state:
                raise WebSpecError(f"string field {item.label!r} references unknown text state {item.variable!r}")
            value = state[item.variable]
            if item.kind == "text":
                if not (item.minimum <= len(value) <= item.maximum):
                    raise WebSpecError(f"initial text state {item.variable!r} violates length bounds")
            elif item.kind == "select":
                if value not in item.options:
                    raise WebSpecError(f"initial selection {item.variable!r} is not an allowed option")
            else:
                raise WebSpecError(f"unsupported string field kind {item.kind!r}")

    if set(page.state) & set(page.text_state):
        raise WebSpecError("page numeric and text state names collide")
    check_string_fields(page.text_fields, page.text_state)
    for key, (lo, hi) in page.bounds.items():
        if key not in page.state:
            raise WebSpecError(f"bounds references unknown state {key!r}")
        if not (lo <= page.state[key] <= hi):
            raise WebSpecError(f"initial state {key} is outside bounds")
    for button in page.buttons:
        if button.variable not in page.state:
            raise WebSpecError(f"button {button.label!r} references unknown state {button.variable!r}")
    for item in page.inputs:
        if item.variable not in page.state:
            raise WebSpecError(f"input {item.label!r} references unknown state {item.variable!r}")
    for template in page.texts:
        check_text(template, set(page.state) | set(page.text_state))

    for component in page.components.values():
        if not component.texts and not component.buttons and not component.inputs and not component.text_fields:
            raise WebSpecError(f"component {component.name!r} cannot be empty")
        overlap = set(component.props) & (set(component.state) | set(page.state) | set(component.text_state) | set(page.text_state))
        if overlap:
            raise WebSpecError(f"component prop collides with state: {sorted(overlap)}")
        if set(component.state) & set(component.text_state):
            raise WebSpecError("component numeric and text state names collide")
        check_string_fields(component.text_fields, {**page.text_state, **component.text_state})
        for key, (lo, hi) in component.bounds.items():
            if key not in component.state:
                raise WebSpecError(f"component bounds references unknown local state {key!r}")
            if not (lo <= component.state[key] <= hi):
                raise WebSpecError(f"component initial state {key!r} outside bounds")
        writable = set(component.state) | set(page.state)
        for button in component.buttons:
            if button.variable not in writable:
                raise WebSpecError(f"button {button.label!r} references unknown state {button.variable!r}")
        for item in component.inputs:
            if item.variable not in writable:
                raise WebSpecError(f"input {item.label!r} references unknown state {item.variable!r}")
        for template in component.texts:
            check_text(template, writable | set(component.text_state) | set(page.text_state) | set(component.props))
    core = "".join(raw[:start] + raw[end:])
    if len(re.findall(r"(?m)^emit web\s*$", core)) != 1:
        raise WebSpecError("a web page needs exactly one `emit web` declaration")
    core = re.sub(r"(?m)^emit web\s*$", "emit typescript", core)
    return page, core


_STYLE = """
:root{color-scheme:light dark;font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;background:#0e1424;color:#f5f6fb}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:2rem;background:radial-gradient(ellipse at 20% 5%,#25395b,#0e1424 60%)}
main{width:min(100%,570px);padding:clamp(1.4rem,5vw,3rem);border:1px solid #40516c;border-radius:22px;background:#182238;box-shadow:0 20px 70px #0005}
.tag{font-size:.74rem;text-transform:uppercase;letter-spacing:.18em;color:#a5cdfb;font-weight:800}h1{font-size:clamp(2rem,6vw,3rem);line-height:1.1;margin:.6rem 0 1rem}p{font-size:1.14rem;color:#dbe5f5;overflow-wrap:anywhere}
.controls{display:flex;flex-wrap:wrap;gap:.65rem;margin-top:1.8rem}button{border:1px solid #7c99c5;color:white;background:#30466e;padding:.8rem 1.2rem;border-radius:12px;font:inherit;cursor:pointer;min-height:44px}
.vibe-page-grid{width:min(100%,980px)}
.vibe-layout-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,245px),1fr));gap:1rem;align-items:start}
.vibe-layout-grid .vibe-component{margin:0}
.vibe-fields{display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0}.vibe-field{display:flex;flex-direction:column;gap:.35rem}
.vibe-field label{font-size:.92rem;color:#dce8f8}.vibe-field input{max-width:100%;min-height:44px;border:1px solid #7c99c5;border-radius:10px;padding:.55rem;background:#0d1931;color:white;font:inherit}
.vibe-field input:focus-visible,.vibe-field select:focus-visible{outline:3px solid #f9d56e;outline-offset:2px}
.vibe-field select{max-width:100%;min-height:44px;border:1px solid #7c99c5;border-radius:10px;padding:.55rem;background:#0d1931;color:white;font:inherit}
.vibe-field input[aria-invalid="true"],.vibe-field select[aria-invalid="true"]{border-color:#ffa09b}
.vibe-error{font-size:.82rem;color:#ffb7b2;margin:.1rem 0;min-height:1.2em}
.vibe-component{border:1px solid #465d80;border-radius:14px;margin:1.2rem 0;padding:1.2rem;background:#131d32}.vibe-component h2{font-size:1.05rem;margin:0 0 .65rem;color:#b9dafa}
button:hover{background:#415e8e}button:focus-visible{outline:3px solid #f9d56e;outline-offset:3px}footer{margin-top:2rem;color:#a2aec5;font-size:.75rem}
@media(prefers-reduced-motion:no-preference){button{transition:background .15s ease,transform .15s ease}button:active{transform:scale(.98)}}
""".strip()

_SCRIPT = r"""
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('vibe-config').textContent);
  const state = Object.assign(Object.create(null), config.state);
  const textState = Object.assign(Object.create(null), config.text_state || {});
  const scopedTextStates = Object.create(null);
  Object.entries(config.scope_text_states || {}).forEach(([scope, values]) => {
    scopedTextStates[scope] = Object.assign(Object.create(null), values);
  });
  const scopedStates = Object.create(null);
  Object.entries(config.scope_states || {}).forEach(([scope, values]) => {
    scopedStates[scope] = Object.assign(Object.create(null), values);
  });
  const owns = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  const render = () => {
    document.querySelectorAll('[data-vibe-text]').forEach((node) => {
      const index = Number(node.dataset.vibeText);
      const template = config.texts[index];
      const scope = (config.text_scopes || [])[index];
      const props = (config.text_props || [])[index] || {};
      const local = scope == null ? null : scopedStates[scope];
      const localText = scope == null ? null : scopedTextStates[scope];
      node.textContent = template.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g,
        (_, key) => {
          if (owns(props, key)) return String(props[key]);
          if (local && owns(local, key)) return String(local[key]);
          if (localText && owns(localText, key)) return String(localText[key]);
          if (owns(state, key)) return String(state[key]);
          return String(textState[key]);
        });
    });
    if (config.inputs && config.inputs.length) {
      document.querySelectorAll('[data-vibe-input]').forEach((node) => {
        const field = config.inputs[Number(node.dataset.vibeInput)];
        const local = field.scope == null ? null : scopedStates[field.scope];
        const target = local && owns(local, field.variable) ? local : state;
        node.value = String(target[field.variable]);
      });
    }
    if (config.string_fields && config.string_fields.length) {
      document.querySelectorAll('[data-vibe-string]').forEach((node) => {
        const field = config.string_fields[Number(node.dataset.vibeString)];
        const local = field.scope == null ? null : scopedTextStates[field.scope];
        const target = local && owns(local, field.variable) ? local : textState;
        node.value = target[field.variable];
      });
    }
  };
  document.querySelectorAll('[data-vibe-button]').forEach((node) => {
    node.addEventListener('click', () => {
      const action = config.buttons[Number(node.dataset.vibeButton)];
      const scope = action.scope;
      const local = scope == null ? null : scopedStates[scope];
      const target = local && owns(local, action.variable) ? local : state;
      const old = target[action.variable];
      const next = action.operation === '=' ? action.value :
        action.operation === '+=' ? old + action.value : old - action.value;
      const bounds = target === state
        ? config.bounds[action.variable]
        : config.scope_bounds[scope][action.variable];
      target[action.variable] = bounds ? Math.max(bounds[0], Math.min(bounds[1], next)) : next;
      render();
    });
  });
  if (config.inputs && config.inputs.length) {
    document.querySelectorAll('[data-vibe-input]').forEach((node) => {
      node.addEventListener('change', () => {
        const field = config.inputs[Number(node.dataset.vibeInput)];
        const local = field.scope == null ? null : scopedStates[field.scope];
        const target = local && owns(local, field.variable) ? local : state;
        const raw = String(node.value).trim();
        if (!/^-?\d{1,12}$/.test(raw)) {
          node.value = String(target[field.variable]);
          return;
        }
        const parsed = Number(raw);
        if (!Number.isSafeInteger(parsed)) {
          node.value = String(target[field.variable]);
          return;
        }
        const bounds = target === state
          ? config.bounds[field.variable]
          : config.scope_bounds[field.scope][field.variable];
        target[field.variable] = bounds
          ? Math.max(bounds[0], Math.min(bounds[1], parsed))
          : parsed;
        render();
      });
    });
  }
  if (config.string_fields && config.string_fields.length) {
    document.querySelectorAll('[data-vibe-string]').forEach((node) => {
      const index = Number(node.dataset.vibeString);
      const field = config.string_fields[index];
      const errorNode = document.getElementById('vibe-string-error-' + index);
      const setError = (message) => {
        errorNode.textContent = message;
        node.setAttribute('aria-invalid', message ? 'true' : 'false');
      };
      node.addEventListener('change', () => {
        const local = field.scope == null ? null : scopedTextStates[field.scope];
        const target = local && owns(local, field.variable) ? local : textState;
        const value = String(node.value);
        if (field.kind === 'text') {
          const length = Array.from(value).length;
          if (length < field.minimum || length > field.maximum) {
            setError('Enter ' + field.minimum + ' to ' + field.maximum + ' characters.');
            return;
          }
        } else if (field.kind === 'select') {
          if (!field.options.includes(value)) {
            setError('Choose one of the available options.');
            return;
          }
        } else {
          setError('Unsupported field type.');
          return;
        }
        target[field.variable] = value;
        setError('');
        render();
      });
    });
  }
  render();
})();
""".strip()


def render_html(page: WebPage) -> str:
    """Generate deterministic HTML with no framework/runtime dependencies."""
    def field_markup(index: int, label: str, variable: str, bounds: dict[str, tuple[int, int]]) -> str:
        limits = bounds.get(variable)
        limits_attrs = f' min="{limits[0]}" max="{limits[1]}"' if limits else ""
        return (
            f'<div class="vibe-field"><label for="vibe-input-{index}">{escape(label)}</label>'
            f'<input type="number" inputmode="numeric" step="1" id="vibe-input-{index}"'
            f' data-vibe-input="{index}"{limits_attrs}></div>'
        )

    def string_field_markup(index: int, item: WebStringField) -> str:
        name = f"vibe-string-{index}"
        error_name = f"vibe-string-error-{index}"
        label = f'<label for="{name}">{escape(item.label)}</label>'
        if item.kind == "text":
            control = (
                f'<input type="text" id="{name}" data-vibe-string="{index}"'
                f' aria-describedby="{error_name}" aria-invalid="false" autocomplete="off">'
            )
        else:
            options = "".join(
                f'<option value="{escape(choice, quote=True)}">{escape(choice)}</option>'
                for choice in item.options
            )
            control = (
                f'<select id="{name}" data-vibe-string="{index}"'
                f' aria-describedby="{error_name}" aria-invalid="false">{options}</select>'
            )
        status = f'<p class="vibe-error" id="{error_name}" role="status" aria-live="polite"></p>'
        return f'<div class="vibe-field">{label}{control}{status}</div>'

    texts = list(page.texts)
    text_scopes: list[str | None] = [None] * len(page.texts)
    text_props: list[dict[str, str]] = [{} for _ in page.texts]
    buttons: list[dict[str, object]] = [
        {"label": action.label, "variable": action.variable,
         "operation": action.operation, "value": action.value, "scope": None}
        for action in page.buttons
    ]
    inputs: list[dict[str, str | None]] = [
        {"variable": item.variable, "scope": None} for item in page.inputs
    ]
    page_fields = "\n".join(
        field_markup(i, item.label, item.variable, page.bounds)
        for i, item in enumerate(page.inputs)
    )
    string_fields: list[dict[str, object]] = [
        {
            "kind": item.kind, "variable": item.variable, "scope": None,
            "minimum": item.minimum, "maximum": item.maximum, "options": list(item.options),
        }
        for item in page.text_fields
    ]
    page_string_fields = "\n".join(
        string_field_markup(i, item) for i, item in enumerate(page.text_fields)
    )
    scope_text_states: dict[str, dict[str, str]] = {}
    scope_states: dict[str, dict[str, int]] = {}
    scope_bounds: dict[str, dict[str, tuple[int, int]]] = {}
    component_sections: list[str] = []
    for instance_id, (name, props) in enumerate(zip(page.uses, page.use_props)):
        component = page.components[name]
        scope = f"instance_{instance_id}"
        scope_states[scope] = dict(component.state)
        scope_text_states[scope] = dict(component.text_state)
        scope_bounds[scope] = dict(component.bounds)
        body: list[str] = []
        for value in component.texts:
            index = len(texts)
            texts.append(value)
            text_scopes.append(scope)
            text_props.append(dict(props))
            body.append(f'      <p data-vibe-text="{index}" aria-live="polite"></p>')
        for item in component.inputs:
            index = len(inputs)
            inputs.append({"variable": item.variable, "scope": scope})
            local_bounds = component.bounds if item.variable in component.state else page.bounds
            body.append("      " + field_markup(index, item.label, item.variable, local_bounds))
        for item in component.text_fields:
            index = len(string_fields)
            string_fields.append({
                "kind": item.kind, "variable": item.variable, "scope": scope,
                "minimum": item.minimum, "maximum": item.maximum, "options": list(item.options),
            })
            body.append("      " + string_field_markup(index, item))
        actions: list[str] = []
        for action in component.buttons:
            index = len(buttons)
            buttons.append({
                "label": action.label, "variable": action.variable,
                "operation": action.operation, "value": action.value,
                "scope": scope,
            })
            actions.append(f'        <button type="button" data-vibe-button="{index}">{escape(action.label)}</button>')
        if actions:
            body.append('      <div class="controls" role="group" aria-label="Component actions">')
            body.extend(actions)
            body.append("      </div>")
        component_sections.append(
            '    <section class="vibe-component" aria-label="' + escape(name, quote=True) + '">\n'
            + '      <h2>' + escape(name.replace("_", " ")) + '</h2>\n'
            + '\n'.join(body) + '\n    </section>'
        )
    payload = {
        "state": page.state,
        "text_state": page.text_state,
        "texts": texts,
        "buttons": buttons,
        "bounds": page.bounds,
        "inputs": inputs,
        "string_fields": string_fields,
        "scope_text_states": scope_text_states,
        "text_scopes": text_scopes,
        "text_props": text_props,
        "scope_states": scope_states,
        "scope_bounds": scope_bounds,
    }
    raw_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    safe_json = (raw_json.replace("&", "\\u0026").replace("<", "\\u003c")
                 .replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    text_elements = "\n".join(f'    <p data-vibe-text="{i}" aria-live="polite"></p>' for i, _ in enumerate(page.texts))
    controls = "\n".join(f'      <button type="button" data-vibe-button="{i}">{escape(b.label)}</button>' for i, b in enumerate(page.buttons))
    component_markup = "\n".join(component_sections)
    grid_page_class = ' class="vibe-page-grid"' if page.layout == "grid" else ""
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Intent-driven page compiled by VibeWeb">
  <title>{escape(page.title)}</title>
  <style>{_STYLE}</style>
</head>
<body>
  <main{grid_page_class}>
    <div class="tag">Φ VibeWeb · experimental v0</div>
    <h1>{escape(page.heading)}</h1>
{text_elements}
    <div class="controls" role="group" aria-label="Page actions">
{controls}
    </div>
    <div class="vibe-fields">
{page_fields}
{page_string_fields}
    </div>
    <div class="vibe-layout vibe-layout-{page.layout}">
{component_markup}
    </div>
    <footer>Compiled from a .vibe intent. No React, Svelte, or client dependencies.</footer>
  </main>
  <script type="application/json" id="vibe-config">{safe_json}</script>
  <script>{_SCRIPT}</script>
</body>
</html>
'''


def build(source_path: Path, out_dir: Path) -> dict[str, object]:
    """Compile only if bounded VibeWeb checks AND Vibe bridge check pass."""
    from .ir import ast_to_ir
    from .parser import parse_source, ParseError
    from .verifier import verify

    try:
        program = parse_source(source_path.read_text(encoding="utf-8"))
    except ParseError as exc:
        raise WebSpecError(str(exc)) from exc
    if program.web_page is None:
        raise WebSpecError("a web build requires a page block")
    ir = ast_to_ir(program)
    from .emitter import emit_code
    markup, _ = emit_code(ir)
    verified = verify(ir, markup, use_calibration=False)
    if not verified.passed:
        raise WebSpecError(f"Vibe heuristic bridge rejected output (score={verified.bridge_score:.4f}); nothing emitted")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(markup, encoding="utf-8")
    report: dict[str, object] = {
        "schema": "vibeweb.bounded-build.v0",
        "source": str(source_path),
        "intent": program.intent.name,
        "target": "web",
        "result": "emitted",
        "checks": ["restricted page grammar", "state/action bindings", "numeric bounds", "Vibe heuristic bridge"],
        "bridge_score": round(float(verified.bridge_score), 6),
        "bridge_passed": bool(verified.passed),
        "limitations": "This is a bounded syntax/heuristic preservation report, not full formal equivalence or a browser accessibility certification.",
    }
    (out_dir / "vibeweb.report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vibe.web", description="Experimental VibeWeb page compiler")
    parser.add_argument("source", type=Path, help=".vibe intent with a bounded page block")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="output directory")
    args = parser.parse_args(argv)
    try:
        report = build(args.source, args.out)
    except (WebSpecError, OSError, ValueError) as exc:
        print(f"VibeWeb build failed: {exc}", file=sys.stderr)
        return 1
    print(f"VibeWeb emitted {args.out / 'index.html'}; bridge_score={report['bridge_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
