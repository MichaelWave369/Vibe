import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";

const url = "http://127.0.0.1:4320/";
const key = "vibeweb:playground:source:v1";

async function openCounter(page) {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  const editor = page.getByRole("textbox", { name: "Vibe source code" });
  await expect(editor).toHaveValue(/intent CounterPage/);
  await expect(page.frameLocator("#preview").getByRole("heading", {
    name: "The first VibeWeb page",
  })).toBeVisible();
  return editor;
}

test("Phase 3L: import a local .vibe file, edit, then download exact source", async ({ page }) => {
  const editor = await openCounter(page);
  const original = await editor.inputValue();
  await page.locator("#open-source-file").setInputFiles({
    name: "local-counter.vibe",
    mimeType: "text/plain",
    buffer: Buffer.from(original, "utf8"),
  });
  await expect(page.getByRole("textbox", { name: "Source file name" }))
    .toHaveValue("local-counter.vibe");
  await expect(editor).toHaveValue(original);
  await expect(page.locator("#dirty-flag")).toHaveText("Unchanged");
  await expect(page.locator("#project-status")).toContainText("Opened local source");

  const updated = original.replace("The first VibeWeb page", "My Edited Counter");
  await editor.fill(updated);
  await expect(page.locator("#dirty-flag")).toHaveText("Unsaved edits");
  await editor.press("Control+s");
  const downloadFromButton = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download .vibe" }).click();
  const downloaded = await downloadFromButton;
  expect(downloaded.suggestedFilename()).toBe("local-counter.vibe");
  expect(await readFile(await downloaded.path(), "utf8")).toBe(updated);
  await expect(page.locator("#dirty-flag")).toHaveText("Unchanged");
  await expect(page.locator("#project-status")).toContainText("download requested");
});

test("Phase 3L: snapshots are explicit, not restored automatically and can be cleared", async ({ page }) => {
  const editor = await openCounter(page);
  const original = await editor.inputValue();
  const edited = original.replace("The first VibeWeb page", "Saved Snapshot Page");
  await editor.fill(edited);
  await expect(page.locator("#dirty-flag")).toHaveText("Unsaved edits");
  await page.getByRole("button", { name: "Save snapshot" }).click();
  await expect(page.locator("#project-status")).toContainText("Snapshot saved");
  const stored = await page.evaluate(storageKey => window.localStorage.getItem(storageKey), key);
  expect(stored).toBeTruthy();
  expect(JSON.parse(stored)).toEqual({ version: 1, filename: "counter.vibe", source: edited });
  await page.reload();
  await expect(page.locator("#state")).toContainText("Compiled");
  await expect(editor).toHaveValue(/intent TypingPacks/);
  await expect(page.getByRole("button", { name: "Restore snapshot" })).toBeEnabled();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Restore snapshot" }).click();
  await expect(editor).toHaveValue(edited);
  await expect(page.getByRole("textbox", { name: "Source file name" })).toHaveValue("counter.vibe");
  await expect(page.locator("#project-status")).toContainText("Local snapshot restored");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Clear snapshot" }).click();
  await expect(page.getByRole("button", { name: "Restore snapshot" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Clear snapshot" })).toBeDisabled();
  await expect(editor).toHaveValue(edited);
  await page.reload();
  await expect(page.getByRole("button", { name: "Restore snapshot" })).toBeDisabled();
  expect(await page.evaluate(storageKey => window.localStorage.getItem(storageKey), key)).toBeNull();
});

test("Phase 3L: rejects invalid extensions, oversized imports, filenames and corrupted snapshots", async ({ page }) => {
  const editor = await openCounter(page);
  const original = await editor.inputValue();
  await page.locator("#open-source-file").setInputFiles({
    name: "malicious.js",
    mimeType: "text/javascript",
    buffer: Buffer.from("alert(1)"),
  });
  await expect(page.locator("#project-status")).toContainText("Only .vibe files");
  await expect(editor).toHaveValue(original);
  await page.locator("#open-source-file").setInputFiles({
    name: "huge.vibe",
    mimeType: "text/plain",
    buffer: Buffer.from("x".repeat(40001)),
  });
  await expect(page.locator("#project-status")).toContainText("40 KB or smaller");
  await expect(editor).toHaveValue(original);
  await page.getByRole("textbox", { name: "Source file name" }).fill("../outside.vibe");
  await page.getByRole("button", { name: "Save snapshot" }).click();
  await expect(page.locator("#project-status")).toContainText("Fix the filename");
  expect(await page.evaluate(storageKey => window.localStorage.getItem(storageKey), key)).toBeNull();
  await page.evaluate(storageKey => localStorage.setItem(storageKey,
    JSON.stringify({ version: 1, filename: "../bad.vibe", source: "bad" })), key);
  await page.reload();
  await expect(page.getByRole("button", { name: "Restore snapshot" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Clear snapshot" })).toBeEnabled();
  await expect(page.locator("#project-status")).toContainText("incompatible");
});

test("Phase 3L: local project toolbar fits mobile viewport and passes axe WCAG A/AA scan", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await expect(page.getByRole("button", { name: "Open .vibe" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save snapshot" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("#preview")
    .analyze();
  expect(result.violations.map(item => ({
    id: item.id, impact: item.impact,
    nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary })),
  }))).toEqual([]);
});
