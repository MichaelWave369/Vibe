import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const url = "http://127.0.0.1:4320/";

test("Phase 3K: editor offers context-aware keyboard completions", async ({ page }) => {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  await expect(source).toHaveValue(/intent CounterPage/);
  const previous = await source.inputValue();
  await source.fill(previous.replace('  heading: "The first VibeWeb page"', "  hea"));
  await source.evaluate(element => {
    const point = element.value.indexOf("  hea\n") + "  hea".length;
    element.focus();
    element.setSelectionRange(point, point);
  });
  await source.press("Control+Space");
  await expect(page.locator("#suggestions")).toBeVisible();
  await expect(page.getByRole("option", { name: 'heading: "Page heading"' })).toBeVisible();
  await source.press("Enter");
  await expect(source).toHaveValue(/  heading: "Page heading"/);
  await expect(page.locator("#suggestions")).toBeHidden();
  await source.press("Control+Enter");
  await expect(page.locator("#state")).toContainText("Compiled");
  await expect(page.frameLocator("#preview").getByRole("heading", { name: "Page heading" })).toBeVisible();

  // The touch-accessible Suggest button uses the same grammar-aware choices.
  await source.evaluate(element => {
    const point = element.value.indexOf('  heading: "Page heading"') + 2;
    element.focus();
    element.setSelectionRange(point, point);
  });
  await page.getByRole("button", { name: "Suggestions" }).click();
  await expect(page.locator("#suggestions")).toBeVisible();
  await source.press("Escape");
  await expect(page.locator("#suggestions")).toBeHidden();
});

test("Phase 3K: line-specific error is clickable and selects the failing source line", async ({ page }) => {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  await expect(source).toHaveValue(/intent CounterPage/);
  const previous = await source.inputValue();
  await source.fill(previous.replace('  heading: "The first VibeWeb page"',
    '   heading: "The first VibeWeb page"'));
  await page.getByRole("button", { name: "Compile & preview" }).click();
  await expect(page.locator("#state")).toContainText("Compilation failed");
  await expect(page.locator("#diagnostics")).toContainText("indent with multiples of two spaces");
  const goToLine = page.locator("#diagnostics button");
  await expect(goToLine).toHaveCount(1);
  await expect(goToLine).toContainText(/Line \d+/);
  await expect(page.locator("#line-numbers .gutter-marked")).toHaveCount(1);
  await goToLine.click();
  const selected = await source.evaluate(element =>
    element.value.slice(element.selectionStart, element.selectionEnd));
  expect(selected).toContain('heading: "The first VibeWeb page"');
  await expect(source).toHaveClass(/source-has-error/);

  await source.press("End");
  await source.press("Space");
  await expect(page.locator("#line-numbers .gutter-marked")).toHaveCount(0);
});

test("Phase 3K: source map jumps to validated source and emitted HTML lines", async ({ page }) => {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.getByRole("textbox", { name: "Vibe source code" })).toHaveValue(/intent CounterPage/);
  await expect(page.frameLocator("#preview").getByRole("heading", { name: "The first VibeWeb page" })).toBeVisible();
  await page.getByRole("tab", { name: "Source map" }).click();
  const map = page.locator("#map-output");
  await expect(map.locator(".map-entry")).not.toHaveCount(0);
  const heading = map.locator(".map-entry").filter({ hasText: "heading · heading" });
  await expect(heading).toHaveCount(1);
  await heading.getByRole("button", { name: /^Source line \d+$/ }).click();
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  const selected = await source.evaluate(element =>
    element.value.slice(element.selectionStart, element.selectionEnd));
  expect(selected).toContain('heading: "The first VibeWeb page"');
  await heading.getByRole("button", { name: /^HTML line \d+$/ }).click();
  await expect(page.getByRole("tab", { name: "HTML" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#html-output .html-focus-line")).toContainText("<h1>");
  await expect(page.locator("#html-output")).toContainText('id="vibe-config"');
});

test("Phase 3K: mobile output inspector and editor pass axe WCAG A/AA automated checks", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("tab", { name: "Source map" }).click();
  await expect(page.locator(".map-entry")).not.toHaveCount(0);
  const widths = await page.evaluate(() => ({
    window: window.innerWidth, scroll: document.documentElement.scrollWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.window + 1);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("#preview")
    .analyze();
  expect(result.violations.map(item => ({
    id: item.id, impact: item.impact,
    nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary }))
  }))).toEqual([]);
});
