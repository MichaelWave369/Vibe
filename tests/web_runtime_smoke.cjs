// Dependency-free Node smoke test of generated VibeWeb component runtime.
// Runs the emitted inline JavaScript against a minimal fake DOM, not a real browser.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const cfgMatch = html.match(/<script type="application\/json" id="vibe-config">([\s\S]*?)<\/script>/);
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert(cfgMatch && scriptMatch, "compiled page contains config and runtime");
const config = JSON.parse(cfgMatch[1]);
const texts = config.texts.map((_, i) => ({
  dataset: { vibeText: String(i) },
  textContent: ""
}));
const buttons = config.buttons.map((_, i) => ({
  dataset: { vibeButton: String(i) },
  listeners: {},
  addEventListener(event, callback) { this.listeners[event] = callback; }
}));
const document = {
  getElementById(id) {
    assert.equal(id, "vibe-config");
    return { textContent: cfgMatch[1] };
  },
  querySelectorAll(selector) {
    if (selector === "[data-vibe-text]") return texts;
    if (selector === "[data-vibe-button]") return buttons;
    throw new Error("Unexpected DOM selector: " + selector);
  }
};
vm.runInNewContext(scriptMatch[1], { document });
assert.equal(texts[0].textContent, "Shared total across cards: 0");
assert.equal(texts[1].textContent, "Alpha: 0 clicks. Shared total: 0");
assert.equal(texts[2].textContent, "Beta: 0 clicks. Shared total: 0");

function click(scope, variable) {
  const index = config.buttons.findIndex(action =>
    action.scope === scope && action.variable === variable);
  assert.notEqual(index, -1, "button exists for " + scope + ":" + variable);
  buttons[index].listeners.click();
}
click("instance_0", "count");
assert.equal(texts[1].textContent, "Alpha: 1 clicks. Shared total: 0");
assert.equal(texts[2].textContent, "Beta: 0 clicks. Shared total: 0");
click("instance_1", "count");
click("instance_1", "count");
assert.equal(texts[1].textContent, "Alpha: 1 clicks. Shared total: 0");
assert.equal(texts[2].textContent, "Beta: 2 clicks. Shared total: 0");
click("instance_1", "total");
assert.equal(texts[0].textContent, "Shared total across cards: 1");
assert.equal(texts[1].textContent, "Alpha: 1 clicks. Shared total: 1");
assert.equal(texts[2].textContent, "Beta: 2 clicks. Shared total: 1");
for (let i = 0; i < 20; i++) click("instance_0", "count");
assert.equal(texts[1].textContent, "Alpha: 9 clicks. Shared total: 1");
assert.equal(texts[2].textContent, "Beta: 2 clicks. Shared total: 1");
click(null, "total");
assert.equal(texts[0].textContent, "Shared total across cards: 0");
assert.equal(texts[1].textContent, "Alpha: 9 clicks. Shared total: 0");
assert.equal(texts[2].textContent, "Beta: 2 clicks. Shared total: 0");
console.log("VibeWeb Phase 3B runtime: isolated instance state, props, shared state and bounds PASS");
