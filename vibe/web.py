"""VibeWeb v0: bounded, dependency-free, reactive HTML emitter for Vibe.

The bounded `page` grammar is now recognized by Vibe's primary parser and
lowered into typed SSA IR. The standalone web build remains supported.
No arbitrary JavaScript expressions, templates, or imports are executed.
"""
from __future__ import annotations

import argparse
from .ast import WebButton as Button, WebPage, WebComponent
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


def parse_web_source(source: str) -> tuple[WebPage, str]:
    """Parse a *restricted* page block and return the standard Vibe contract.

    Unsupported constructs fail closed. The returned core source uses the
    existing typescript target only to pass through the normal Vibe parser;
    final output is produced by this web emitter, not the TS emitter.
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
            if value in {"state:", "view:", "bounds:", "components:"}:
                section = value[:-1]
                continue
            section = ""
            if value.startswith("title:"):
                page.title = _quoted(value.split(":", 1)[1].strip(), idx + 1)
            elif value.startswith("heading:"):
                page.heading = _quoted(value.split(":", 1)[1].strip(), idx + 1)
            else:
                raise WebSpecError(f"line {idx + 1}: unsupported page field {value!r}")
        elif n == 4 and section == "state":
            if ":" not in value:
                raise WebSpecError(f"line {idx + 1}: expected `name: integer`")
            key, number = (t.strip() for t in value.split(":", 1))
            if not _NAME.fullmatch(key) or key in page.state:
                raise WebSpecError(f"line {idx + 1}: invalid or repeated state name")
            page.state[key] = _integer(number, idx + 1)
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
            if value.startswith("text:"):
                current_component.texts.append(_quoted(value.split(":", 1)[1].strip(), idx + 1))
            else:
                match = _BUTTON.fullmatch(value)
                if not match:
                    raise WebSpecError(f"line {idx + 1}: expected component text or button")
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
    if not page.title or not page.heading or not page.state or not page.texts or not page.buttons:
        raise WebSpecError("page requires title, heading, state, text, and a button")
    for b in page.buttons:
        if b.variable not in page.state:
            raise WebSpecError(f"button {b.label!r} references unknown state {b.variable!r}")
    for key, (lo, hi) in page.bounds.items():
        if key not in page.state:
            raise WebSpecError(f"bounds references unknown state {key!r}")
        if not (lo <= page.state[key] <= hi):
            raise WebSpecError(f"initial state {key} is outside bounds")
    for value in page.texts:
        for ref in _BINDING.findall(value):
            if ref not in page.state:
                raise WebSpecError(f"text references unknown state {ref!r}")
        # Deny malformed variable expressions instead of silently rendering them.
        if "{" in _BINDING.sub("", value) or "}" in _BINDING.sub("", value):
            raise WebSpecError("unsupported text interpolation; use {state_name}")
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
button:hover{background:#415e8e}button:focus-visible{outline:3px solid #f9d56e;outline-offset:3px}footer{margin-top:2rem;color:#a2aec5;font-size:.75rem}
@media(prefers-reduced-motion:no-preference){button{transition:background .15s ease,transform .15s ease}button:active{transform:scale(.98)}}
""".strip()

_SCRIPT = r"""
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('vibe-config').textContent);
  const state = Object.assign(Object.create(null), config.state);
  const render = () => {
    document.querySelectorAll('[data-vibe-text]').forEach((node) => {
      const template = config.texts[Number(node.dataset.vibeText)];
      node.textContent = template.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g,
        (_, key) => String(state[key]));
    });
  };
  document.querySelectorAll('[data-vibe-button]').forEach((node) => {
    node.addEventListener('click', () => {
      const action = config.buttons[Number(node.dataset.vibeButton)];
      const old = state[action.variable];
      const next = action.operation === '=' ? action.value :
        action.operation === '+=' ? old + action.value : old - action.value;
      const bounds = config.bounds[action.variable];
      state[action.variable] = bounds ? Math.max(bounds[0], Math.min(bounds[1], next)) : next;
      render();
    });
  });
  render();
})();
""".strip()


def render_html(page: WebPage) -> str:
    """Generate deterministic HTML with no framework/runtime dependencies."""
    payload = {
        "state": page.state,
        "texts": page.texts,
        "buttons": [vars(b) if hasattr(b, "__dict__") else {"label": b.label, "variable": b.variable, "operation": b.operation, "value": b.value} for b in page.buttons],
        "bounds": page.bounds,
    }
    raw_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    safe_json = (raw_json.replace("&", "\\u0026").replace("<", "\\u003c")
                 .replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    text_elements = "\n".join(f'    <p data-vibe-text="{i}" aria-live="polite"></p>' for i, _ in enumerate(page.texts))
    controls = "\n".join(f'      <button type="button" data-vibe-button="{i}">{escape(b.label)}</button>' for i, b in enumerate(page.buttons))
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
  <main>
    <div class="tag">Φ VibeWeb · experimental v0</div>
    <h1>{escape(page.heading)}</h1>
{text_elements}
    <div class="controls" role="group" aria-label="Page actions">
{controls}
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
