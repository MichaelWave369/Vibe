import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const url = "/dist-qa-typing/index.html";
const passage = "Precision matters.  Two spaces are welcome here.";

test("Chromium: real keyboard input tracks exact spaces, completion and restart", async ({ page }) => {
  await page.goto(url);
  const input = page.getByRole("textbox", { name: "Type the lesson" });
  const status = page.locator("#vibe-typing-status");
  await expect(page.getByRole("heading", { name: "Keyboard Dojo · First Lesson" })).toBeVisible();
  await expect(input).toHaveValue("");
  await expect(status).toHaveText("Ready to type.");
  await input.focus();
  await input.pressSequentially("Precision matters.  ", { delay: 5 });
  await expect(input).toHaveValue("Precision matters.  ");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("0");
  await input.pressSequentially("Two spaces are welcome here.", { delay: 5 });
  await expect(input).toHaveValue(passage);
  await expect(status).toHaveText("Lesson complete! Great precision.");
  await expect(page.locator("#vibe-typing-accuracy")).toHaveText("100%");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("0");
  await expect(page.locator("#vibe-typing-progress")).toHaveJSProperty("value", passage.length);
  await expect(input).toBeDisabled();
  await page.getByRole("button", { name: "Restart lesson" }).click();
  await expect(input).toBeEnabled();
  await expect(input).toHaveValue("");
  await expect(status).toHaveText("Ready to type.");
  await expect(page.locator("#vibe-typing-progress")).toHaveJSProperty("value", 0);
});

test("Chromium: accuracy detects errors and Backspace corrects without losing double spaces", async ({ page }) => {
  await page.goto(url);
  const input = page.getByRole("textbox", { name: "Type the lesson" });
  await input.focus();
  await input.pressSequentially("Precix");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("1");
  await expect(page.locator("#vibe-typing-accuracy")).not.toHaveText("100%");
  await expect(page.locator("#vibe-typing-status")).toContainText("Mistakes highlighted");
  await input.press("Backspace");
  await expect(input).toHaveValue("Preci");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("0");
  await input.pressSequentially("sion matters. ");
  // One space is NOT enough to match the passage. The next character will mismatch.
  await input.pressSequentially("T");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("1");
  await input.press("Backspace");
  await input.press("Space");
  await input.press("T");
  await expect(page.locator("#vibe-typing-errors")).toHaveText("0");
});

test("Chromium: mobile view and axe accessibility scan of the typing game", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await expect(page.getByRole("textbox", { name: "Type the lesson" })).toBeVisible();
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
