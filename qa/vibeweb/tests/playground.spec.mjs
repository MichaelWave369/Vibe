import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const url = "http://127.0.0.1:4320/";

test("native compiler playground edits, compiles and previews real Vibe code in an isolated iframe", async ({ page }) => {
  await page.goto(url);
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  await expect(source).toHaveValue(/intent TypingPacks/);
  await expect(page.locator("#state")).toContainText("Compiled");
  const iframe = page.locator("#preview");
  await expect(iframe).toHaveAttribute("sandbox", "allow-scripts");
  await expect(page.frameLocator("#preview").getByRole("heading", { name: "Keyboard Dojo · Lesson Packs" })).toBeVisible();

  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(source).toHaveValue(/intent CounterPage/);
  await expect(page.locator("#state")).toContainText("Compiled");
  const preview = page.frameLocator("#preview");
  await expect(preview.getByRole("heading", { name: "The first VibeWeb page" })).toBeVisible();
  await preview.getByRole("button", { name: "Increase" }).click();
  await expect(preview.getByText("Count: 1")).toBeVisible();

  await page.getByRole("tab", { name: "HTML" }).click();
  await expect(page.locator("#html-output")).toContainText("<!doctype html>");
  await expect(page.locator("#html-output")).toContainText('id="vibe-config"');
  await page.getByRole("tab", { name: "Report" }).click();
  await expect(page.locator("#report-output")).toContainText('"intent": "CounterPage"');
  await expect(page.locator("#report-output")).toContainText('"bridge_passed": true');

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save HTML" }).click();
  expect((await download).suggestedFilename()).toBe("vibeweb-preview.html");
});

test("compiler errors display native diagnostic messages without executing invalid source", async ({ page }) => {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  const text = await source.inputValue();
  await source.fill(text.replace("lesson \"Double-Space Warmup\"", "script \"Double-Space Warmup\""));
  await source.press("Control+Enter");
  await expect(page.locator("#state")).toContainText("Compilation failed");
  await expect(page.locator("#diagnostics")).toContainText("ERROR");
  await expect(page.getByRole("button", { name: "Save HTML" })).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Report" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#html-output")).toContainText("No HTML was emitted");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("typing");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.locator("#state")).toContainText("Compiled");
  await expect(page.getByRole("button", { name: "Save HTML" })).toBeEnabled();
});

test("playground doesn't render source strings as HTML in the editing shell", async ({ page }) => {
  await page.goto(url);
  await expect(page.locator("#state")).toContainText("Compiled");
  await page.getByRole("combobox", { name: "Example to load" }).selectOption("counter");
  await page.getByRole("button", { name: "Load example" }).click();
  const source = page.getByRole("textbox", { name: "Vibe source code" });
  await expect(source).toHaveValue(/intent CounterPage/);
  await expect(page.frameLocator("#preview").getByRole("heading", { name: "The first VibeWeb page" })).toBeVisible();
  const text = await source.inputValue();
  await source.fill(text.replace('heading: "The first VibeWeb page"',
    'heading: "<img src=x onerror=alert(1)> safe example"'));
  await page.getByRole("button", { name: "Compile & preview" }).click();
  await expect.poll(async () => (await page.locator("#state").textContent()).trim())
    .toMatch(/^(Compiled|Compilation failed)/);
  const status = await page.locator("#state").textContent();
  const preview = page.frameLocator("#preview");
  if (status.trim().startsWith("Compiled")) {
    // If the compiler emits HTML, it must remain plain heading text.
    await expect(preview.locator("h1")).toContainText("<img src=x onerror=alert(1)> safe example");
    await expect(preview.locator("img")).toHaveCount(0);
    await page.getByRole("tab", { name: "HTML" }).click();
    await expect(page.locator("#html-output")).toContainText("&lt;img src=x onerror=alert(1)&gt;");
  } else {
    // Rejecting a suspicious example at the preservation gate is also safe.
    await expect(page.locator("#diagnostics")).toContainText("ERROR");
    await expect(page.getByRole("button", { name: "Save HTML" })).toBeDisabled();
  }
  await expect(page.locator("img")).toHaveCount(0);
});

test("mobile playground layout and basic axe WCAG A/AA scan", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(url);
  await expect(page.getByRole("textbox", { name: "Vibe source code" })).toBeVisible();
  await expect(page.locator("#state")).toContainText("Compiled");
  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth, document: document.documentElement.scrollWidth
  }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport + 1);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("#preview")
    .analyze();
  expect(result.violations.map(item => ({
    id: item.id, impact: item.impact,
    nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary }))
  }))).toEqual([]);
});
