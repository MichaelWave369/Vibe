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
