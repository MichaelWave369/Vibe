import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const url = "/dist-qa-packs/index.html";
const warmup = "Precision matters.  Two spaces are welcome here.";
const storageKey = "vibeweb:typing:v1:TypingPacks";

test("Chromium: lesson packs filter correctly and handle empty combinations", async ({ page }) => {
  await page.goto(url);
  const packs = page.getByRole("combobox", { name: "Lesson pack" });
  const difficulty = page.getByRole("combobox", { name: "Difficulty" });
  const lesson = page.getByRole("combobox", { name: "Lesson", exact: true });
  const input = page.getByRole("textbox", { name: "Type the lesson" });
  await expect(packs).toHaveValue("all");
  await expect(lesson).toHaveValue("0");
  await packs.selectOption("Symbols");
  await expect(lesson).toHaveValue("2");
  await expect(page.locator("#vibe-typing-readable")).toContainText("Caps LOCK?");
  await difficulty.selectOption("beginner");
  await expect(input).toBeDisabled();
  await expect(page.locator("#vibe-typing-status")).toContainText("No lessons match these filters");
  await difficulty.selectOption("intermediate");
  await expect(lesson).toHaveValue("3");
  await expect(input).toBeEnabled();
  await packs.selectOption("Foundations");
  await expect(lesson).toHaveValue("1");
  await difficulty.selectOption("beginner");
  await expect(lesson).toHaveValue("0");
  await expect(page.locator("#vibe-typing-readable")).toContainText(warmup);
});

test("Chromium: corrected errors remain in heatmap and historical attempt accuracy", async ({ page }) => {
  await page.goto(url);
  const input = page.getByRole("textbox", { name: "Type the lesson" });
  const spaceKey = page.locator('[data-vibe-key=" "]');
  await input.fill("Precision matters. T");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("1");
  await expect(spaceKey).toHaveClass(/vibe-key-error/);
  await expect(spaceKey).toHaveAttribute("aria-label", /1 errors/);
  const liveAttempt = await page.locator("#vibe-typing-attempt-accuracy").textContent();
  expect(liveAttempt).not.toBe("100%");
  await input.fill("Precision matters.  ");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("0");
  await input.fill(warmup);
  await expect(page.locator("#vibe-typing-status")).toContainText("Lesson complete");
  await expect(page.locator("#vibe-typing-accuracy")).toHaveText("100%");
  await expect(page.locator("#vibe-typing-attempt-accuracy")).not.toHaveText("100%");
  await expect(page.locator("#vibe-typing-history li")).toHaveCount(1);
  await expect(page.locator("#vibe-typing-history li")).toContainText(/attempt accuracy/);
  const saved = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), storageKey);
  expect(saved.completed["Double-Space Warmup"].history).toHaveLength(1);
  expect(saved.completed["Double-Space Warmup"].history[0].errors).toBeGreaterThanOrEqual(1);
  expect(saved.completed["Double-Space Warmup"].history[0].accuracy).toBeLessThan(100);
  expect(JSON.stringify(saved)).not.toContain(warmup);
  expect(JSON.stringify(saved)).not.toContain("Precision matters. T");

  await page.reload();
  await expect(page.locator("#vibe-typing-history li")).toHaveCount(1);
  await expect(page.locator("#vibe-typing-completed")).toHaveText("1 of 4 lessons completed");
  await page.getByRole("button", { name: "Clear saved progress" }).click();
  await expect(page.locator("#vibe-typing-history li")).toHaveCount(0);
  await page.reload();
  await expect(page.locator("#vibe-typing-completed")).toHaveText("0 of 4 lessons completed");
});

test("Chromium: old progress records migrate, malformed history is rejected", async ({ page }) => {
  await page.goto(url);
  await page.evaluate(key => localStorage.setItem(key, JSON.stringify({
    version: 1, page: "TypingPacks",
    completed: { "Double-Space Warmup": { bestWpm: 32 } }
  })), storageKey);
  await page.reload();
  await expect(page.locator("#vibe-typing-completed")).toHaveText("1 of 4 lessons completed");
  await expect(page.locator("#vibe-typing-best")).toContainText("32");
  await expect(page.locator("#vibe-typing-history li")).toHaveCount(0);

  await page.evaluate(key => localStorage.setItem(key, JSON.stringify({
    version: 1, page: "TypingPacks",
    completed: { "Double-Space Warmup": {
      bestWpm: 32, history: [{ wpm: 23, accuracy: 101, errors: 4 }]
    }}
  })), storageKey);
  await page.reload();
  await expect(page.locator("#vibe-typing-completed")).toHaveText("0 of 4 lessons completed");
  await expect(page.locator("#vibe-typing-save-status")).toContainText("unavailable or incompatible");
});

test("Chromium: 360px mobile packs and automated axe WCAG A/AA scan", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await expect(page.getByRole("combobox", { name: "Lesson pack" })).toBeVisible();
  await expect(page.locator("#vibe-typing-heatmap")).toBeVisible();
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map(item => ({
    id: item.id, impact: item.impact,
    nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary }))
  }))).toEqual([]);
});
