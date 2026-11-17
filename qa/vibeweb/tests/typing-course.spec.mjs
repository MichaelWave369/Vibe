import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const url = "/dist-qa-course/index.html";
const warmup = "Precision matters.  Two spaces are welcome here.";
const advanced = "Caps LOCK? No!  Symbols: @ # $ % & *; keep control.";

test("Chromium: select difficulty, complete lessons and retain local-only progress", async ({ page }) => {
  await page.goto(url);
  const entry = page.getByRole("textbox", { name: "Type the lesson" });
  const difficulty = page.getByRole("combobox", { name: "Difficulty" });
  const lesson = page.getByRole("combobox", { name: "Lesson" });
  await expect(lesson).toHaveValue("0");
  await expect(page.locator("#vibe-typing-completed")).toHaveText("0 of 3 lessons completed");
  await entry.focus();
  await entry.pressSequentially(warmup, { delay: 1 });
  await expect(page.locator("#vibe-typing-status")).toHaveText("Lesson complete! Great precision.");
  await expect(page.locator("#vibe-typing-accuracy")).toHaveText("100%");
  await expect(page.locator("#vibe-typing-completed")).toHaveText("1 of 3 lessons completed");
  await expect(page.locator("#vibe-typing-save-status")).toHaveText("Lesson progress saved in this browser.");
  const saved = await page.evaluate(() => localStorage.getItem("vibeweb:typing:v1:TypingCourse"));
  expect(saved).toContain('"Warmup"');
  expect(saved).not.toContain(warmup); // Save metrics, never typed content

  await page.reload();
  await expect(page.locator("#vibe-typing-save-status")).toHaveText("Previous lesson progress restored.");
  await expect(page.locator("#vibe-typing-completed")).toHaveText("1 of 3 lessons completed");
  await expect(entry).toHaveValue("");
  await difficulty.selectOption("advanced");
  await expect(lesson).toHaveValue("2");
  await expect(page.locator("#vibe-typing-readable")).toContainText(advanced);
  await expect(entry).toHaveAttribute("maxlength", String(advanced.length));
  await entry.fill(advanced);
  await expect(page.locator("#vibe-typing-completed")).toHaveText("2 of 3 lessons completed");
  await expect(page.locator("#vibe-typing-status")).toHaveText("Lesson complete! Great precision.");
  await expect(page.locator("#vibe-typing-best")).toContainText("Best WPM for Symbol Sprint:");
  await page.getByRole("button", { name: "Clear saved progress" }).click();
  await expect(page.locator("#vibe-typing-completed")).toHaveText("0 of 3 lessons completed");
  await page.reload();
  await expect(page.locator("#vibe-typing-completed")).toHaveText("0 of 3 lessons completed");
});

test("Chromium: filter resets active lesson, retains double spaces and validates stored scores", async ({ page }) => {
  await page.goto(url);
  const entry = page.getByRole("textbox", { name: "Type the lesson" });
  const difficulty = page.getByRole("combobox", { name: "Difficulty" });
  const lesson = page.getByRole("combobox", { name: "Lesson" });
  await entry.fill("Precision");
  await expect(entry).toHaveValue("Precision");
  await difficulty.selectOption("intermediate");
  await expect(lesson).toHaveValue("1");
  await expect(entry).toHaveValue("");
  await expect(page.locator("#vibe-typing-progress")).toHaveJSProperty("value", 0);
  await difficulty.selectOption("beginner");
  await expect(lesson).toHaveValue("0");
  await entry.fill("Precision matters. T");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("1");

  await page.evaluate(() => localStorage.setItem("vibeweb:typing:v1:TypingCourse",
    JSON.stringify({ version: 1, page: "TypingCourse", completed: {
      Warmup: { bestWpm: "invalid" }
    }})));
  await page.reload();
  await expect(page.locator("#vibe-typing-completed")).toHaveText("0 of 3 lessons completed");
  await expect(page.locator("#vibe-typing-save-status"))
    .toContainText("unavailable or incompatible");
});

test("Chromium: curriculum mobile layout and axe WCAG A/AA scan", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await expect(page.getByRole("combobox", { name: "Difficulty" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Lesson" })).toBeVisible();
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
