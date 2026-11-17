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
