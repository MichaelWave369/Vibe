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

## Phase 3E: explicit submit and opt-in browser-local draft storage

Pages may declare an explicit form submission control and optional local
persistence policy. Neither is enabled by default.

```yaml
page FormStudio:
  title: "My Form"
  heading: "Local Draft Lab"
  submit: "Save local draft"
  persist: local
  text_state:
    display_name: "Visitor"
  view:
    text: "Welcome {display_name}"
    input_text "Display name": display_name min=2 max=24
emit web
```

Declaring `submit: "Label"` produces a native `<form>`, a submit control,
and an accessible status message. The JavaScript runtime prevents navigation,
checks for uncommitted invalid input, and dispatches a `vibe:submit`
`CustomEvent` carrying a local snapshot of the form state. It does not send
anything to a server.

`persist: local` requires `submit:` and explicitly enables saving the
snapshot to same-origin browser `localStorage` **only on submission**.
On reload, the compiler-generated runtime restores a compatible draft.
Restoration checks schema version, page name, exact state keys and scopes,
safe integer bounds, text lengths, and select options before accepting data.
Missing, unavailable, oversized, invalid, or incompatible stored data does
not overwrite current initial values. The page shows success, recovery,
or storage-failure status text.

Browser storage is shared with other scripts on the same origin and is **not**
appropriate for passwords, secrets, or sensitive personal data. Saving is
not encrypted, synced, backed up, or automatically exported. Clearing site
storage removes drafts. The event is local to the page and other page scripts
may observe its state snapshot.

```bash
vibec compile vibe/examples/web_drafts.vibe --no-cache
python -m vibe.web vibe/examples/web_drafts.vibe --out dist-drafts
node tests/web_draft_runtime_smoke.cjs dist-drafts/index.html
```

Phase 3E does not implement remote submission, authentication, database
storage, or cross-device synchronization. Validation and storage have a
bounded simulated-DOM runtime smoke test. Browser-specific behavior and
accessibility still need a real-browser test suite.

## Phase 3G: native keyboard dojo typing exercise

A VibeWeb page can now declare one bounded typing lesson directly in the
native `.vibe` page AST. The lesson is lowered as a typed string SSA reference
and compiled into dependency-free HTML/CSS/JavaScript:

```yaml
page TypingDojo:
  title: "VibeWeb Keyboard Dojo"
  heading: "Typing lesson"
  typing:
    passage: "Precision matters.  Two spaces are welcome here."
emit web
```

`typing:` is an independent interactive page feature. Unlike form-specific
examples, a typing-only page does not need artificial numeric page state,
a view button, or a form submission. The compiler requires exactly one literal
`passage:`, with 12–240 printable ASCII characters, no newline/control
characters and no leading/trailing whitespace. Interior spaces, including
double spaces, are preserved and checked exactly. Unsupported statements and
additional passages fail at compilation. No user-provided JavaScript is
executed.

The generated browser page includes a native textarea for keyboard input,
per-character correct/incorrect feedback, accessible instructions and
progress, current accuracy, estimated WPM, a current-mistake count, elapsed
time and a restart action. Characters are rendered with `textContent`.
The stopwatch starts on the first input, stops upon fully correct completion
and resets on restart. Backspace is supported. No data is stored or sent.

**Metrics are coaching estimates, not certified competitive scores.**
Accuracy is the percentage of *currently entered* characters matching the
lesson (corrected mistakes no longer count). WPM is matching characters
divided by five, scaled to elapsed time with a one-second minimum denominator.
The exercise has no cumulative error penalty, paste prevention, selectable
lessons, multiplayer, accounts or leaderboard. Non-ASCII and IME lesson
content are not supported in this initial slice.

```bash
vibec compile vibe/examples/web_typing_dojo.vibe --no-cache
python -m vibe.web vibe/examples/web_typing_dojo.vibe --out dist-typing
```

`qa/vibeweb/tests/typing-dojo.spec.mjs` exercises actual Chromium keyboard
entry, including exact double-space matching, mistakes, Backspace, completion,
restart, mobile overflow, and an automated axe WCAG A/AA scan. Automated
accessibility testing does not replace manual screen reader and device testing.

## Phase 3H: multi-lesson typing curriculum and opt-in progress

A typing section may contain one legacy `passage:` (backward-compatible) or
**2–12** named lessons, each with an explicit difficulty level:

```yaml
page TypingCourse:
  title: "Keyboard Dojo"
  heading: "Training Grounds"
  typing:
    progress: local
    lesson "Warmup" difficulty=beginner: "Precision matters.  Two spaces are welcome here."
    lesson "Flow State" difficulty=intermediate: "Spaces, commas, and periods.  Keep a steady rhythm."
    lesson "Symbol Sprint" difficulty=advanced: "Caps LOCK? No!  Symbols: @ # $ % & *; keep control."
emit web
```

Lessons are statically declared in Vibe, lowered through the typed AST/SSA IR
and rendered in a native HTML dropdown. The difficulty dropdown filters which
lessons can be selected. Choosing another lesson resets its typing timer,
accuracy, progress, text field, completion state, and character highlighting.
The original single-passage `typing: passage:` source remains supported.

Lesson names are unique, bounded plain strings (2–40 characters). All passages
are 12–240 printable ASCII characters with no leading/trailing whitespace,
and interior double spaces are preserved and tested exactly. The only levels
are beginner, intermediate, and advanced. The compiler fails on mixed
`passage:` and named lessons, duplicate lesson names, unknown levels,
malformed declarations, invalid text or excessive lesson counts.

**Local progress is optional and off by default.** A Vibe page must declare
`progress: local` to activate it. On a *fully correct completion*, the runtime
stores only a mapping from lesson names to best estimated WPM in the same
origin's `localStorage`, under `vibeweb:typing:v1:<page>`. Raw keystrokes,
typed text, mistakes, full passages, and the elapsed-time history are not
saved. The record is loaded only after a bounded schema/page/name/value
check; malformed or incompatible records are ignored. The user can clear
these saved records using a visible **Clear saved progress** button. No data
is transmitted to a server, encrypted, synchronized, or backed up. Scripts
on the same origin can read this storage; it must not hold secrets.

```bash
vibec compile vibe/examples/web_typing_course.vibe --no-cache
python -m vibe.web vibe/examples/web_typing_course.vibe --out dist-course
```

Playwright tests perform real keystrokes, selection, course-completion,
reload, record clearing, malformed-storage checks, mobile-overflow checks
and an automated axe WCAG A/AA scan. WPM is a training approximation;
accuracy reflects currently correct characters rather than historical errors.
No anti-paste checks, global leaderboard, user accounts, customizable drills,
Unicode/IME curriculum, progress export or cross-browser certification yet.

## Phase 3I: named lesson packs, keyboard trouble map, and practice history

Custom lesson packs are authored directly in the source `.vibe` page, compiled
into a bounded literal curriculum with no server or runtime code evaluation.

```yaml
typing:
  progress: local
  lesson "Double-Space Warmup" pack="Foundations" difficulty=beginner: "Precision matters.  Two spaces are welcome here."
  lesson "Symbol Sprint" pack="Symbols" difficulty=advanced: "Caps LOCK? No!  Symbols: @ # $ % & *; keep control."
```

The optional `pack="Name"` attribute is a 2–40-character plain name.
When omitted, its value defaults to `Core` for backward compatibility. Up
to 8 distinct packs and 12 lessons remain bounded at compile time. Multiple
packs add a **Lesson pack** dropdown; it combines with the existing difficulty
filter. When no lessons match, the typing input is disabled until a valid
filter is selected.

During a typing attempt, a keyboard trouble map highlights the *expected*
letters A–Z and Space when a user enters the wrong character. Corrections
clear the live text mismatch but do not erase counted mistakes. The display
also includes **Attempt accuracy**, which measures successful appended
character entries divided by all appended character entries; it differs
from the existing live **Accuracy** metric that reflects currently correct
characters. A corrected mistake is still visible in attempt accuracy and
the trouble map. Paste and mid-string replacement can affect this
approximate coaching metric, which is **not** a standardized typing score.
The heatmap is per-session only, resets when changing/restarting lessons,
and is never stored persistently.

When `progress: local` is declared, completing a lesson stores its previous
best WPM and the last **10 completed attempt summaries** for that lesson,
containing only WPM, attempt accuracy, and error count. Typed text, key
sequences, exact erroneous characters, and full passages are not stored.
Previous Phase 3H `{bestWpm}` records remain accepted; malformed historical
records fail closed. The existing **Clear saved progress** button removes the
history as well. Nothing is transmitted to a server. Same-origin JavaScript
can read localStorage and browser clearing removes it.

```bash
vibec compile vibe/examples/web_typing_packs.vibe --no-cache
python -m vibe.web vibe/examples/web_typing_packs.vibe --out dist-packs
```

Playwright verifies filters, no-match handling, the per-key heatmap, corrected
error metrics, persisted summaries, backward compatibility, corruption
rejection, mobile overflow, and automated axe WCAG A/AA checks. Automated
checks do not substitute for manual accessibility audits. Custom packs are
compile-time declarations, **not arbitrary runtime uploads**; no accounts,
telemetry, multiplayer, editable lesson authoring UI, or online catalog exists.

## Phase 3J: local native compiler playground

VibeWeb now includes a **local development playground** that uses the same
Python parser, typed SSA IR, web emitter and heuristic preservation gate as
the CLI. It is not a second/approximate JavaScript compiler.

From the Vibe repository (Python 3.11+):

```bash
python -m pip install -e .
python -m vibe.playground --port 4320
```

Then open **http://127.0.0.1:4320/**. You can start with a counter,
component, form, typing lesson, curriculum or lesson-pack example, edit the
source in the built-in editor, and click **Compile & preview** or press
**Ctrl+Enter**. The right panel displays the compiled page, generated HTML,
or a JSON verification report. Parser/binding diagnostics stay visible and
are linked to source line numbers where available. **Save HTML** downloads
only the generated standalone output to your own machine when requested.

The server binds only to `127.0.0.1`, rejects non-loopback Host headers,
does not provide cross-origin access, and requires a custom header plus
application/json for the compiler POST route. Requests are capped at 40 KB,
source at 20,000 characters, and example retrieval is allowlisted. No
arbitrary shell commands, user-provided file paths or network actions are
executed by the compiler service. Compiles are **in memory** and do not
write or modify repository files. No account, external API or online compiler
is required. Python dependencies remain standard-library-only beyond Vibe.

The browser preview uses `iframe sandbox="allow-scripts"` with an opaque
origin; it cannot access the playground's own origin/storage. An additional
CSP disables external connections, navigation-dependent forms and external
assets in the preview. Consequently, app features requiring same-origin
browser localStorage will not function normally inside the preview; download
the compiled HTML and serve it from a local web server for full storage
testing. A compiler bridge score is **heuristic**, not a formal guarantee
of security or browser behavior.

```bash
python -m pytest -q tests/test_playground.py
# Full real Chromium suite (Node 22+, Playwright dependencies required):
npm run test:browser --prefix qa/vibeweb
```

The Playwright browser QA workflow launches the separate local playground
server and tests editing, compilation, diagnostics, sandboxing, HTML
inspection, download, mobile layout and an axe WCAG A/AA scan. Automated
accessibility checks are not equivalent to a manual audit. This local
developer environment is not a public multi-tenant service and must not be
exposed directly to the internet; deploying a hosted compiler requires
additional authentication, process isolation, rate controls and security
review.

## Phase 3K: contextual completion, line diagnostics and source/output inspector

The local VibeWeb Playground from Phase 3J now provides **opt-in contextual
completion** with `Ctrl+Space` or the **Suggestions** button. Suggested
statements are intentionally curated and selected by the current Vibe
indentation/section (page, view, typing, components, state, bounds, etc.).
Use Arrow Up/Down and Enter/Tab to choose, or Escape to dismiss. The editor
still uses a dependency-free `textarea`, not a language server or a full
syntax-aware Monaco environment. Autocomplete never executes the suggestion.

Compile diagnostics now render line buttons for errors that the native
parser can locate. Clicking a line scrolls to and selects the corresponding
source, while the editor gutter marks that line. Edits clear the stale error
highlight. Some verifier or semantic failures do not include a precise
source line; these remain normal text diagnostics and are not falsely mapped.

The new **Source map** tab lists a bounded, best-effort outline of recognized
declarations, including their original line numbers, first matching
generated-HTML lines and escaped excerpts. Source line buttons jump to
the editor, and HTML line buttons highlight the generated markup inside
the HTML inspector. This is **not a full source map**. A generated component
may be used more than once, and certain metadata-only declarations have no
direct HTML node. The outline is a navigation aid for known constructs.
Neither compiler-provided source nor output HTML is inserted into the
playground DOM as executable markup.

```bash
python -m vibe.playground --port 4320
python -m pytest -q tests/test_playground.py
```

The Chromium QA suite covers completion, accepting/canceling suggestions,
line navigation on syntax errors, source-to-HTML inspection, mobile layout,
and automated axe accessibility checks. The compiler server remains bound
to localhost and all preview sandbox restrictions remain unchanged. No
network-connected autocomplete service, remote language model or third-party
editor dependency is added.

## Phase 3L: local source projects, file round trips and explicit snapshots

The existing loopback-native VibeWeb Playground now has a simple local
project workflow. It is still a **single-document editor**, rather than a
multi-file repository IDE.

- **Open .vibe** reads one explicitly selected file in your browser and
  compiles its contents with the existing native Vibe compiler. It never
  sends a file to a remote service or writes it to a repository.
- **Download .vibe**, or **Ctrl+S** while the editor is focused, requests a
  download of the exact current source text under the selected filename.
  The downloaded file is editable in any text editor or version-controlled
  normally. The playground does not silently replace an existing file on
  disk.
- **Save snapshot** explicitly stores the current filename and source
  in browser `localStorage` at
  `vibeweb:playground:source:v1`. There is **no autosave**. On reload,
  the editor still opens its standard starter example. A saved snapshot is
  offered for explicit restoration, not loaded without permission.
- **Restore snapshot** asks for confirmation before replacing the current
  editor contents; **Clear snapshot** deletes the browser-local copy but
  leaves the current editor text alone.
- The header shows whether source differs from the last opened/downloaded
  text. Loading an example also replaces editor text, and does not change
  files on disk. Download source before replacing an important edit.

Imports use bounded, safe `.vibe` basenames, a maximum file size of 40 KB,
and up to 20,000 source characters with no NUL bytes. Snapshots have the
same source/filename constraints, a versioned record structure, bounded
JSON size, and validation before restoration. Invalid or corrupt records
are ignored rather than silently applied. Source files are never evaluated
as JavaScript. The compiler server still provides only in-memory compilation
and allowlisted example reading.

**Privacy:** browser storage is same-origin, unencrypted, and visible to
other scripts served from the same origin. Do not place credentials, secrets,
or sensitive personal information in saved snapshots. Clearing site data
deletes them. Downloaded source files are the user's own responsibility.
The opt-in snapshot is not a backup, synchronization, Git commit, or
disk-write mechanism.

```bash
python -m vibe.playground --port 4320
```

The Playwright suite covers opening source, exact download round trips,
source dirty status, save/reload/restore/clear, invalid filenames and files,
corrupt storage, 360px mobile layout, and axe A/AA automated checks.

## Phase 3M: export a GitHub Pages-ready static project

The loopback VibeWeb Playground adds an explicit **Export Pages ZIP** button
beside the local project file tools. This is separate from **Save HTML** and
**Download .vibe**: it compiles the current editor source with the **same
native Vibe parser, typed SSA IR, web emitter and bridge gate**, and returns
a complete ZIP without writing files on the server.

The generated archive contains:

```text
site/index.html                          # Compiled standalone VibeWeb page
site/.nojekyll                           # Disable Jekyll processing
source/your-file.vibe                    # Original editable source
.github/workflows/deploy-pages.yml       # GitHub Pages Actions deployment
README.md                                # Step-by-step publish instructions
```

The included GitHub Actions workflow checks out the repository, configures
GitHub Pages, verifies the `site/index.html` file exists, uploads **only**
`site/` via `actions/upload-pages-artifact@v4`, and deploys it with
`actions/deploy-pages@v4`. It runs on pushes to `main` or manual
`workflow_dispatch`; its job needs `pages: write` and `id-token: write`.
The workflow intentionally serves the already-compiled static output: **if
you later change the `.vibe` source, compile it again and replace
`site/index.html`** before committing.

To publish, extract the downloaded ZIP into an empty local Git repository,
commit and push its contents to `main`, then select **GitHub Actions** in
that repository's **Settings → Pages**. The user must perform the GitHub
repository creation, commit, push and Pages settings. A ZIP export does
**not** publish, mutate the user's existing repositories, or authenticate to
GitHub automatically.

The exporter is restricted to a safe 6–80-character `.vibe` basename,
at most 20,000 source characters and a 40 KB JSON request body. It accepts
only validated source and produces compiled HTML after the native
preservation check; invalid input or failed compiles return JSON diagnostics,
**not** a half-built ZIP. ZIP entries are fixed, deterministic paths and
contain no user-controlled directory segments; the archive is bounded at
2 MB and generated entirely in memory. The endpoint preserves loopback
Host restrictions, CSRF header/Origin checks and no-CORS policy.

```bash
python -m vibe.playground --port 4320
python -m pytest -q tests/test_playground.py
```

The browser test suite downloads the ZIP, verifies its contents and
recompilation safety, checks invalid sources, tests the mobile toolbar, and
runs automated axe accessibility scans.

**Security and privacy:** Websites published to GitHub Pages are public
unless access restrictions apply through GitHub or another service. Public
repositories expose the included Vibe source. Never publish credentials,
private data, or anything you do not intend to share. A static VibeWeb site
has no authentication or database. Browser-local storage is origin-scoped and
is not secret or synchronized. The bundle is appropriate only for one
standalone static page, not an authenticated service or multi-page build.
