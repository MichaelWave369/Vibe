import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";

const url = "http://127.0.0.1:4320/";

async function openCounter(page) {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  await expect(source).toHaveValue(/intent CounterPage/);
  await expect(page.frameLocator("#preview").getByRole("heading", {
    name: "The first VibeWeb page",
  })).toBeVisible();
  return source;
}

function inspectZip(path) {
  const script = [
    "import json,sys,zipfile",
    "with zipfile.ZipFile(sys.argv[1]) as z:",
    " print(json.dumps({'names':z.namelist(),'source':z.read('source/counter.vibe').decode(),",
    "   'site':z.read('site/index.html').decode(),",
    "   'workflow':z.read('.github/workflows/deploy-pages.yml').decode()}))",
  ].join("\n");
  return JSON.parse(execFileSync("python", ["-c", script, path], { encoding: "utf8" }));
}

test("Phase 3M: export a complete GitHub Pages-ready project without publishing", async ({ page }) => {
  const source = await openCounter(page);
  const updated = (await source.inputValue()).replace(
    "The first VibeWeb page", "My Published Vibe Counter");
  await source.fill(updated);
  await expect(page.locator("#dirty-flag")).toHaveText("Unsaved edits");

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Pages ZIP" }).click();
  const item = await download;
  expect(item.suggestedFilename()).toBe("vibeweb-counter-pages.zip");
  const raw = await readFile(await item.path());
  expect(raw.subarray(0, 4).toString("hex")).toBe("504b0304");
  const archive = inspectZip(await item.path());
  expect(archive.names.sort()).toEqual([
    ".github/workflows/deploy-pages.yml",
    "README.md",
    "site/.nojekyll",
    "site/index.html",
    "source/counter.vibe",
  ]);
  expect(archive.source).toBe(updated);
  expect(archive.site).toContain("<!doctype html>");
  expect(archive.site).toContain("My Published Vibe Counter");
  expect(archive.workflow).toContain("actions/deploy-pages@v4");
  expect(archive.workflow).toContain("actions/upload-pages-artifact@v4");
  expect(archive.workflow).toContain("path: site");
  expect(archive.workflow).toContain("repository: MichaelWave369/Vibe");
  expect(archive.workflow).toContain("ref: 5ed4ef6108b86e3b91c0cb24c55b25576af0cffd");
  expect(archive.workflow).toContain("python -m pip install --no-deps ./.vibe-toolchain");
  expect(archive.workflow).toContain('python -m vibe.web "${sources[0]}" --out site');
  expect(archive.workflow).toContain("rm -f site/index.html site/vibeweb.report.json");
  expect(archive.workflow.indexOf("Rebuild and verify VibeWeb source"))
    .toBeLessThan(archive.workflow.indexOf("Upload compiled site only"));
  await expect(page.locator("#project-status")).toContainText("ZIP download requested");
  await expect(page.locator("#dirty-flag")).toHaveText("Unsaved edits");
});

test("Phase 3M: refused compilation or filename never produces a Pages ZIP", async ({ page }) => {
  const source = await openCounter(page);
  const original = await source.inputValue();
  await source.fill(original.replace("count += 1", "eval(1)"));
  await page.getByRole("button", { name: "Export Pages ZIP" }).click();
  await expect(page.locator("#project-status")).toContainText("Pages export failed");
  await expect(page.locator("#diagnostics")).toContainText("ERROR");

  await source.fill(original);
  await page.getByRole("textbox", { name: "Source file name" }).fill("../bad.vibe");
  await page.getByRole("button", { name: "Export Pages ZIP" }).click();
  await expect(page.locator("#project-status")).toContainText("valid .vibe filename");
  await expect(page.getByRole("button", { name: "Export Pages ZIP" })).toBeEnabled();
});

test("Phase 3M: Pages export toolbar works at mobile width and passes axe scan", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await expect(page.getByRole("button", { name: "Export Pages ZIP" })).toBeVisible();
  const scroll = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth, viewport: window.innerWidth,
  }));
  expect(scroll.document).toBeLessThanOrEqual(scroll.viewport + 1);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("#preview")
    .analyze();
  expect(results.violations.map(item => ({
    id: item.id, impact: item.impact,
    nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary })),
  }))).toEqual([]);
});
