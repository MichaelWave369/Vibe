# VibeWeb Phase 3F: real-browser QA and exploratory baselines

This directory adds independent checks to the **existing Vibe compiler**.
The generated HTML is tested in real Chromium with Playwright, including
keyboard-usable forms, mobile viewport sizing, browser-local draft restoration,
and automated WCAG A/AA checks with axe-core.

**A passing axe scan is not an accessibility certification.** Manual screen-reader,
keyboard-only, and real-device checks remain necessary. The existing bridge gate
is also heuristic and is not substituted for browser behavior tests.

## Local run

From the repository root, with Python 3.11+ and Node 22+:

```bash
python -m pip install -e .
python -m vibe.web vibe/examples/web_instances.vibe --out dist-qa-instances
python -m vibe.web vibe/examples/web_drafts.vibe --out dist-qa
npm install --prefix qa/vibeweb
npm run build:baselines --prefix qa/vibeweb
npm exec --prefix qa/vibeweb -- playwright install chromium
npm run test:browser --prefix qa/vibeweb
npm run bench --prefix qa/vibeweb
```

A server is started automatically for browser tests; the benchmark runs
its own ephemeral local HTTP server. CI installs Chromium system dependencies.

## Baseline methodology

The React, Svelte and VibeWeb apps implement the *same bounded counter task*:
two independent counters (0-9), a shared total (0-369), and shared reset.
React and Svelte baseline apps are built with Vite in production mode.
VibeWeb is compiled by the native `python -m vibe.web` command from
`vibe/examples/web_instances.vibe`. No application framework is loaded by
VibeWeb. Baseline apps are functional equivalents, **not visually identical**
or matched for all features.

The measurement script records seven cold-ish page navigations and twelve
dom-change timings after clicks for each app in sequence using headless Chromium
on a shared runner. It also records output HTML/CSS/JS bytes and approximate
per-file gzip bytes. Reports live at `qa/vibeweb/reports/phase3f-benchmark.json`
and are uploaded as an Actions artifact.

**Do not interpret one CI run as a framework speed ranking.** Real performance
comparisons require repeated measurements, randomized/interleaved run ordering,
warm/cold cache controls, controlled hardware, confidence intervals,
feature/style parity, and production workload coverage.

Dependencies are specified at known stable versions in package.json, but the
initial QA harness uses `npm install` rather than a committed transitive
lockfile. Record installed versions in CI and commit a lockfile for more
reproducible future comparisons.

## Native typing dojo application

Phase 3G adds `vibe/examples/web_typing_dojo.vibe` and a real-browser
Playwright suite under `tests/typing-dojo.spec.mjs`. The new tests operate
on actual keystrokes and verify two-space passages, correction, completion
and restart, plus axe and 360px mobile overflow. The existing React/Svelte
benchmark intentionally remains the **counter-only** comparison; keyboard
dojo results are not included in those framework performance figures.

```bash
python -m vibe.web vibe/examples/web_typing_dojo.vibe --out dist-qa-typing
npm run test:browser --prefix qa/vibeweb
```

## Phase 3H: full typing curriculum QA

`vibe/examples/web_typing_course.vibe` compiles three lesson levels and a
browser-local, opt-in progress store. The Playwright suite
`tests/typing-course.spec.mjs` checks actual lesson changes, exact double
spaces, score storage and reload, clearing progress, malformed-storage
rejection, mobile behavior and axe scanning.

```bash
python -m vibe.web vibe/examples/web_typing_course.vibe --out dist-qa-course
npm run test:browser --prefix qa/vibeweb
```

The existing React/Svelte performance benchmark still covers only the
original bounded counter. It does not imply typing-game framework parity.

## Phase 3I: source-authored lesson packs and practice-history tests

`vibe/examples/web_typing_packs.vibe` specifies bounded, named packs
directly in Vibe source. The Chromium suite in
`tests/typing-packs.spec.mjs` covers pack and difficulty filtering, missing
combinations, QWERTY-style trouble keys, historical attempt accuracy,
in-browser storage and clearing, old-record compatibility, and axe/mobile
checks.

```bash
python -m vibe.web vibe/examples/web_typing_packs.vibe --out dist-qa-packs
npm run test:browser --prefix qa/vibeweb
```

The existing React/Svelte benchmark still covers the bounded counter only.
These additional typing features are not yet subject to equivalent
cross-framework benchmark tasks.

## Phase 3J: native playground browser checks

The Playwright config now launches a second local-only Python server at
`http://127.0.0.1:4320/`, alongside the existing static QA server. The
`tests/playground.spec.mjs` suite verifies that real compiler output
appears in a sandboxed iframe, editable source is compiled and diagnosed,
HTML/report views render, generated HTML can be downloaded, dangerous
source strings do not turn into DOM markup, and the 360px editor layout
passes automated axe checks.

No new React/Svelte benchmark claims are made. The playground is a
developer tool, not a public code-execution website. Use
`python -m vibe.playground --port 4320` locally.

## Phase 3K editor intelligence

`tests/playground-editor.spec.mjs` exercises the existing native local
playground's editor enhancements with Chromium: Ctrl+Space completions,
click-to-source compiler errors, generated HTML line navigation,
and 360px mobile/axe checks. The source-to-output mapping is deliberately
partial. No new React/Svelte performance comparison is claimed.

```bash
npm run test:browser --prefix qa/vibeweb
```

## Phase 3L: local project file workflow

`tests/playground-projects.spec.mjs` verifies that the native local
playground supports opening a `.vibe` file, downloading exact edited
source, explicit local snapshots, confirmation-based restoration and
clearing, input/file-size limits, corrupt-storage rejection, mobile
layout and axe checks.

This remains an opt-in, browser-local workflow. The compiler backend
does **not** create or overwrite project files, and no cloud sync,
repository commit operation or public hosting is involved.

## Phase 3M: GitHub Pages project ZIP export QA

`tests/playground-pages.spec.mjs` verifies the loopback playground's
**Export Pages ZIP** action. The suite inspects the actual downloaded ZIP
using Python's standard `zipfile`, confirms exact Vibe source round trips,
checks the generated standalone site, the minimal GitHub Pages workflow,
compiler failures, filename safety, mobile layout, and axe accessibility.

`tests/test_playground.py` verifies deterministic in-memory ZIP creation,
bounded ZIP paths, metadata/headers, same-origin request guards and
failure-without-download behavior. No GitHub repository changes or actual
deployment are performed by the tests.

## Phase 3N: build-on-push ZIP QA

Exports now include a GitHub Pages workflow that checks out Vibe at a pinned
immutable public Git commit, recompiles exactly one `source/*.vibe` file,
verifies the native compiler report, and only then uploads the built `site/`.
Files in the `source/` directory are never served by the Pages artifact.

The Python regression in `tests/test_playground.py` extracts a generated ZIP
and runs the **exact Bash compile and verify run block** from its deployment
workflow on a temporary project. It tests a changed source, the presence of
a verified build report, refusal of invalid source, removal of stale HTML
before compilation, and refusal when multiple source files are present.

The browser ZIP test also checks the pinned compiler checkout, install
command, source-to-HTML build command, and the ordering of compilation
before Pages upload. These tests do not publish a site or require access
to the user's GitHub repositories.
