// Reproducible, non-ranking experiment. Data is hardware/browser dependent.
// Functional parity is tested separately by Playwright; this script records measurements.
import { chromium } from "@playwright/test";
import { startServer } from "./serve.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { gzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";

const qaDir = fileURLToPath(new URL("./", import.meta.url));
const repoDir = fileURLToPath(new URL("../../", import.meta.url));
const scenarios = [
  { name: "VibeWeb", url: "/dist-qa-instances/index.html", directory: "dist-qa-instances",
    selector: '[data-vibe-text="0"]' },
  { name: "React", url: "/qa/vibeweb/dist-react/index.html", directory: "qa/vibeweb/dist-react",
    selector: "[data-bench-shared]" },
  { name: "Svelte", url: "/qa/vibeweb/dist-svelte/index.html", directory: "qa/vibeweb/dist-svelte",
    selector: "[data-bench-shared]" }
];

async function walk(folder) {
  const entries = await fs.readdir(folder, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolute = path.join(folder, entry.name);
    if (entry.isDirectory()) files.push(...await walk(absolute));
    else if (/\.(?:html|js|css)$/.test(entry.name)) files.push(absolute);
  }
  return files;
}
async function footprint(folder) {
  const files = await walk(path.join(repoDir, folder));
  let bytes = 0, gzipBytes = 0;
  for (const file of files) {
    const content = await fs.readFile(file);
    bytes += content.length;
    gzipBytes += gzipSync(content).length;
  }
  return { files: files.length, uncompressedBytes: bytes, gzipApproxBytes: gzipBytes };
}
function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return null;
  return Number((sorted.length % 2 ? sorted[(sorted.length - 1) / 2] :
    (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2).toFixed(3));
}
const server = await startServer({ port: 0 });
const base = "http://127.0.0.1:" + server.address().port;
const browser = await chromium.launch({ headless: true });
try {
  const results = [];
  for (const scenario of scenarios) {
    const domLoaded = [], fcp = [], interaction = [];
    for (let sample = 0; sample < 7; sample++) {
      const context = await browser.newContext();
      const page = await context.newPage();
      await page.goto(base + scenario.url, { waitUntil: "load" });
      await page.locator(scenario.selector).waitFor();
      const values = await page.evaluate(() => {
        const entry = performance.getEntriesByType("navigation")[0];
        const paint = performance.getEntriesByType("paint")
          .find(value => value.name === "first-contentful-paint");
        return {
          domContentLoadedMs: entry?.domContentLoadedEventEnd ?? null,
          firstContentfulPaintMs: paint?.startTime ?? null,
        };
      });
      if (values.domContentLoadedMs != null) domLoaded.push(values.domContentLoadedMs);
      if (values.firstContentfulPaintMs != null) fcp.push(values.firstContentfulPaintMs);
      if (sample === 0) {
        // Observe a DOM update after a real click, avoiding remote RPC overhead.
        // A MutationObserver sees the corresponding update in all three implementations.
        for (let i = 0; i < 12; i++) {
          const elapsed = await page.evaluate(async (selector) => {
            const target = document.querySelector(selector);
            const increment = [...document.querySelectorAll("button")]
              .find(button => button.textContent.trim() === "Increment total");
            if (!target || !increment) throw Error("missing comparable counter UI");
            const before = target.textContent;
            return await new Promise((resolve, reject) => {
              const started = performance.now();
              const timer = setTimeout(() => { observer.disconnect(); reject(Error("no DOM update")); }, 3000);
              const observer = new MutationObserver(() => {
                if (target.textContent !== before) {
                  clearTimeout(timer);
                  observer.disconnect();
                  resolve(performance.now() - started);
                }
              });
              observer.observe(target, { childList: true, characterData: true, subtree: true });
              increment.click();
            });
          }, scenario.selector);
          interaction.push(elapsed);
        }
      }
      await context.close();
    }
    results.push({
      framework: scenario.name,
      app: scenario.url,
      loadSamples: domLoaded.length,
      interactionSamples: interaction.length,
      domContentLoadedMedianMs: median(domLoaded),
      firstContentfulPaintMedianMs: median(fcp),
      domUpdateAfterClickMedianMs: median(interaction),
      assets: await footprint(scenario.directory),
    });
  }
  const report = {
    schema: "vibeweb.benchmark.exploratory.v1",
    generatedAt: new Date().toISOString(),
    context: {
      browser: "Chromium " + browser.version(), node: process.version,
      os: os.platform() + " " + os.release(), arch: os.arch(),
      cpuModel: os.cpus()[0]?.model ?? "unknown",
      samplesPerFramework: 7, updatesPerFramework: 12,
      staticServing: "localhost HTTP without caching or compression",
    },
    limitations: [
      "Non-production exploratory microbenchmark, NOT proof one framework is faster.",
      "Functional parity targets a bounded two-counter example only; visual styling is not matched.",
      "React and Svelte use Vite production bundles; VibeWeb uses one generated HTML document.",
      "Gzip sizes are per-file approximations, not actual transferred compressed bytes.",
      "Runs are sequential on shared CI hardware; no interleaving, CPU isolation, throttling, or statistical confidence intervals.",
      "DOM content loaded and first-contentful-paint do not measure user-perceived interactivity.",
      "Click timing observes DOM mutation; React/Svelte and VibeWeb update on different scheduling models.",
      "Repeat and analyze multiple CI runs before interpreting the measurements.",
    ],
    results,
  };
  const directory = path.join(qaDir, "reports");
  await fs.mkdir(directory, { recursive: true });
  const output = path.join(directory, "phase3f-benchmark.json");
  await fs.writeFile(output, JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify({ report: output, results }, null, 2));
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
