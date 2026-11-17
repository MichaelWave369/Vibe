# Φ VibeWeb v0: Intent-driven browser pages

VibeWeb is a **bounded, experimental** web page backend for the existing Vibe language.
It compiles an intent specification plus a `page` declaration to one dependency-free
`index.html` and a machine-readable build report. It does **not** replace React or
Svelte in general, nor does it support arbitrary HTML/CSS/JavaScript yet.

## Try it

```bash
python -m pip install -e .
python -m vibe.web vibe/examples/web_counter.vibe --out dist
python -m pytest -q tests/test_web.py
```

Open `dist/index.html`, or upload `dist/` to a static host such as GitHub Pages.

## Supported syntax

`intent`, `preserve`, `bridge` retain their existing meaning. A new **single**
`page Name:` declaration must have the same name as the `intent Name:` block.
Use `emit web` at the end of the source. The VibeWeb v0 page grammar supports:

- `title` and `heading`: JSON-style double-quoted strings
- `state:`: integer state variables
- `bounds:`: optional inclusive `minimum..maximum` per variable
- `view:` `text: "...{variable}..."` with safe text substitution
- `view:` `button "Label":` followed by `action: variable += N`, `-= N`, or `= N`

No arbitrary JavaScript expressions or `innerHTML` are used. State changes update
only the bound text nodes. Buttons are keyboard-accessible native HTML buttons.

## Integration with Vibe

The page declaration is parsed by a **sidecar parser**. The remaining source is
parsed with the existing Vibe parser and lowered into its typed IR. The generated
HTML is passed through the existing Vibe **heuristic** bridge verifier. Emission
is blocked if this check fails. The `emit web` declaration is internally mapped
onto a known target for base-language parsing only; it does not call the TypeScript
emitter. The web backend itself generates the HTML.

The report is a bounded compiler report, **not a mathematical proof** that the
browser app satisfies every intent or accessibility requirement. Future phases
should integrate a first-class web node into AST/IR, add contract-specific runtime
tests, improve formal obligations, and benchmark against React/Svelte.

## Roadmap

1. v0: integer state, safe text bindings, buttons, bounds, one standalone HTML page
2. typed first-class `page` AST/IR and `vibec compile` web target
3. components, inputs, lists, routing, deterministic CSS tokens, accessibility tests
4. independent bundle-size, performance, compatibility, and behavior benchmarks
5. optional WASM/WebGPU backends, without imposing them on simple pages

For now, treat this as a controlled experiment in intent-preserving compilation.


## Phase 2: native AST, typed IR, and a standard web emitter

Vibe's primary parser now recognizes the bounded `page` block, attaching a
typed WebPage object to Program. Title, heading, state, bounds, text and
button actions lower into typed SSA references. The normal emitter registry
supports `emit web`.

The existing standalone build still emits `dist/index.html` and a bounded
verification report:

```bash
python -m vibe.web vibe/examples/web_counter.vibe --out dist
```

The standard Vibe compile command now also handles the web target, producing
HTML beside the input `.vibe` file:

```bash
vibec compile vibe/examples/web_counter.vibe --no-cache
```

The HTML target is deterministic and deliberately bypasses the multi-candidate
synthesis pipeline, so `--with-tests` and `--refine` are not supported yet.
The preservation bridge is heuristic. Passing its gate is not a proof of
browser behavior, comprehensive security, or accessibility compliance.


## Phase 3A: reusable components (experimental)

A VibeWeb `page` can now declare bounded, reusable components under
`components:`, then instantiate them with `use ComponentName` in `view:`.
The same component can be used repeatedly. Every instance reads and updates
the enclosing page's **shared** state; text bindings and integer-only button
actions remain validated before emission.

Example: `vibe/examples/web_components.vibe` declares `CounterCard` once
and uses it twice, alongside a separate reset component.

```bash
vibec compile vibe/examples/web_components.vibe --no-cache
python -m vibe.web vibe/examples/web_components.vibe --out dist-components
```

The core parser, typed AST/IR, emitter, standalone build, and web tests all
support component declarations. This slice does **not** yet support component
props, isolated instance state, arbitrary DOM structure, styling parameters,
routing, or input controls. Components currently render after any direct
page text/buttons, in the order of their `use` declarations. This is a
bounded reuse mechanism, not framework feature parity.

## Phase 3B: isolated instance state and string props (experimental)

Reusable components can now declare required string props and bounded local
integer state. Multiple `use` instances each get separate local state; they
can still read or update shared page state.

```yaml
components:
  component CounterCard:
    prop label: string
    state count: 0
    bounds count: 0..9
    text: "{label}: {count}"
    button "Increment":
      action: count += 1
view:
  use CounterCard label="Alpha"
  use CounterCard label="Beta"
```

The actual full example is `vibe/examples/web_instances.vibe`:

```bash
vibec compile vibe/examples/web_instances.vibe --no-cache
python -m vibe.web vibe/examples/web_instances.vibe --out dist-instances
node tests/web_runtime_smoke.cjs dist-instances/index.html
```

Props are **required JSON-quoted strings**, are read-only, and cannot shadow
local or page state. Component-local integer state is independent for each
rendered instance. Local actions resolve local state first; actions targeting
page state remain shared. All interpolation is rendered using `textContent`,
and HTML output escapes serialized JSON to prevent script breakouts.

These are deliberate restrictions, not general JavaScript support. No
number/boolean/object props, computed expressions, slot trees, nested components,
per-instance storage, asynchronous effects, or arbitrary DOM structures yet.
The standard bridge remains a bounded heuristic check; the Node smoke test
covers one generated-runtime example, not all browsers.

## Phase 3C: responsive layouts and numeric forms (experimental)

VibeWeb pages now support `layout: stack` (the default) or `layout: grid`.
Grid layouts create responsive CSS grid columns for reusable component
instances. The renderer uses semantic native HTML inputs and labels.

Both the page `view:` and reusable component definitions can contain:

```yaml
input "Set shared value": shared
```

The bound variable must be declared writable integer state. For component
instances, local state is resolved first, and page state remains shared.
Input values are parsed as bounded decimal integers on `change`, clamped to
any declared state bounds, and rendered back into labels and inputs.
Invalid/empty/noninteger input is rejected and the prior state restored.
Native labels are associated with unique input IDs; page and component
labels are HTML-escaped.

```bash
vibec compile vibe/examples/web_forms_grid.vibe --no-cache
python -m vibe.web vibe/examples/web_forms_grid.vibe --out dist-forms
node tests/web_forms_runtime_smoke.cjs dist-forms/index.html
```

Current limitations: only numeric integer inputs, no freeform text state,
checkboxes, select controls, submit/network operations, validation messages
for end users, or data persistence yet. Grid layout is for the page's
reused component sections only. The bridge verifier remains heuristic;
the runtime test exercises generated JavaScript in a minimal simulated DOM,
not a production browser compatibility suite.

## Phase 3D: string state, text input, select controls, inline validation

VibeWeb now supports bounded string state alongside existing integers.

```yaml
page FormStudio:
  title: "Form Studio"
  heading: "Hello, forms"
  text_state:
    display_name: "Visitor"
    theme: "Teal"
  view:
    text: "Hello {display_name} in {theme}"
    input_text "Display name": display_name min=2 max=24
    select "Theme": theme options="Teal|Purple|Gold"
emit web
```

Reusable components may declare their own `text_state name: "Visitor"` and
use these controls with independent per-instance state. Global page string
state is shared. String field validation checks initial state during
compilation and checks changes at runtime. Invalid length or select values
show a visible, `aria-describedby`-associated status and set `aria-invalid`;
valid changes clear the status. Interpolation uses `textContent` and generated
options/labels are HTML-escaped. The serialized configuration is escaped against
script-tag injection.

```bash
vibec compile vibe/examples/web_text_forms.vibe --no-cache
python -m vibe.web vibe/examples/web_text_forms.vibe --out dist-textforms
node tests/web_string_forms_runtime_smoke.cjs dist-textforms/index.html
```

Limitations: this is not a general form submission system; no fetch/network
actions, async validation, passwords, uploads, rich text, checkbox state, or
persistent storage. The current `change` handler validates on committed edits.
Native accessibility and cross-browser behavior need browser-level testing;
our CI runtime uses a simulated DOM. The preservation bridge is heuristic.
