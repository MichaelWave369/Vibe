import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const instancePage = "/dist-qa-instances/index.html";
const draftPage = "/dist-qa/index.html";

test("real Chromium: two independent component counters and one shared total", async ({ page }) => {
  await page.goto(instancePage);
  await expect(page.getByRole("heading", { name: "Two counters. One language." })).toBeVisible();
  const texts = page.locator("[data-vibe-text]");
  await expect(texts.nth(1)).toHaveText("Alpha: 0 clicks. Shared total: 0");
  await expect(texts.nth(2)).toHaveText("Beta: 0 clicks. Shared total: 0");
  await page.getByRole("button", { name: "Increment local" }).first().click();
  await expect(texts.nth(1)).toHaveText("Alpha: 1 clicks. Shared total: 0");
  await expect(texts.nth(2)).toHaveText("Beta: 0 clicks. Shared total: 0");
  await page.getByRole("button", { name: "Increment total" }).last().click();
  await expect(texts.nth(0)).toHaveText("Shared total across cards: 1");
  await expect(texts.nth(2)).toHaveText("Beta: 0 clicks. Shared total: 1");
  await page.getByRole("button", { name: "Reset shared total" }).click();
  await expect(texts.nth(0)).toHaveText("Shared total across cards: 0");
});

test("real Chromium: text validation, submit and reload saved draft", async ({ page }) => {
  await page.goto(draftPage);
  const name = page.getByRole("textbox", { name: "Display name" });
  await expect(name).toHaveValue("Mikey");
  await name.fill("X");
  await name.press("Tab");
  await expect(name).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#vibe-string-error-0")).toContainText("2 to 24 characters");

  await name.fill("Bridge");
  await name.press("Tab");
  await expect(name).toHaveAttribute("aria-invalid", "false");
  await page.getByRole("combobox", { name: "Theme" }).selectOption("Purple");
  const alpha = page.getByRole("textbox", { name: "Card name" }).first();
  await alpha.fill("Alice");
  await alpha.press("Tab");
  await expect(page.locator('[data-vibe-text="1"]')).toContainText("Alpha: Alice");
  await expect(page.locator('[data-vibe-text="2"]')).toContainText("Beta: Visitor");

  const outgoing = [];
  page.on("request", request => {
    if (request.method() !== "GET") outgoing.push(request.url());
  });
  await page.getByRole("button", { name: "Save local draft" }).click();
  await expect(page.locator("#vibe-form-status")).toHaveText("Draft saved locally in this browser.");
  expect(outgoing).toEqual([]);

  await page.reload();
  await expect(page.locator("#vibe-form-status")).toHaveText("Previous local draft restored.");
  await expect(page.getByRole("textbox", { name: "Display name" })).toHaveValue("Bridge");
  await expect(page.getByRole("combobox", { name: "Theme" })).toHaveValue("Purple");
  await expect(page.getByRole("textbox", { name: "Card name" }).first()).toHaveValue("Alice");
  await expect(page.getByRole("textbox", { name: "Card name" }).last()).toHaveValue("Visitor");
});

test("real Chromium: mobile viewport has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(draftPage);
  await expect(page.getByRole("heading", { name: "Reactive text forms and select controls" })).toBeVisible();
  const widths = await page.evaluate(() => ({
    page: document.documentElement.scrollWidth,
    screen: window.innerWidth,
  }));
  expect(widths.page).toBeLessThanOrEqual(widths.screen + 1);
});

test("axe-core: no automatically detected WCAG A/AA violations in generated form", async ({ page }) => {
  await page.goto(draftPage);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map(item => ({
    id: item.id, impact: item.impact,
    nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary }))
  }))).toEqual([]);
});

test("functional parity: React and Svelte reference counter apps behave identically", async ({ page }) => {
  for (const framework of ["react", "svelte"]) {
    await page.goto("/qa/vibeweb/dist-" + framework + "/index.html");
    await expect(page.getByRole("heading", { name: "Two counters. One language." })).toBeVisible();
    await expect(page.locator("[data-bench-shared]")).toHaveText("Shared total across cards: 0");
    await page.getByRole("button", { name: "Increment local" }).first().click();
    await expect(page.getByText("Alpha: 1 clicks. Shared total: 0")).toBeVisible();
    await expect(page.getByText("Beta: 0 clicks. Shared total: 0")).toBeVisible();
    await page.getByRole("button", { name: "Increment total" }).first().click();
    await expect(page.locator("[data-bench-shared]")).toHaveText("Shared total across cards: 1");
    await page.getByRole("button", { name: "Reset shared total" }).click();
    await expect(page.locator("[data-bench-shared]")).toHaveText("Shared total across cards: 0");
  }
});
