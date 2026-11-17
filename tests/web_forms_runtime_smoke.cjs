// Execute VibeWeb-generated HTML runtime with a minimal fake DOM (Node only).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const configMatch = html.match(/<script type="application\/json" id="vibe-config">([\s\S]*?)<\/script>/);
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert(configMatch && scriptMatch, "runtime and safe data payload present");
assert(html.includes('class="vibe-layout vibe-layout-grid"'), "responsive grid emitted");
const config = JSON.parse(configMatch[1]);
assert.equal(config.inputs.length, 3);

const texts = config.texts.map((_, index) => ({
  dataset: { vibeText: String(index) }, textContent: ""
}));
const buttons = config.buttons.map((_, index) => ({
  dataset: { vibeButton: String(index) },
  listeners: {},
  addEventListener(type, callback) { this.listeners[type] = callback; }
}));
const inputs = config.inputs.map((_, index) => ({
  dataset: { vibeInput: String(index) },
  value: "",
  listeners: {},
  addEventListener(type, callback) { this.listeners[type] = callback; }
}));
const document = {
  getElementById(id) {
    assert.equal(id, "vibe-config");
    return { textContent: configMatch[1] };
  },
  querySelectorAll(selector) {
    if (selector === "[data-vibe-text]") return texts;
    if (selector === "[data-vibe-button]") return buttons;
    if (selector === "[data-vibe-input]") return inputs;
    throw new Error("Unexpected selector: " + selector);
  }
};
vm.runInNewContext(scriptMatch[1], { document });
assert.deepEqual(inputs.map(i => i.value), ["3", "2", "2"]);
assert.equal(texts[0].textContent, "Shared value: 3");
assert.equal(texts[1].textContent, "Alpha: 2 · Shared: 3");
assert.equal(texts[2].textContent, "Beta: 2 · Shared: 3");

function change(index, raw) {
  inputs[index].value = raw;
  inputs[index].listeners.change();
}
function click(scope, variable) {
  const index = config.buttons.findIndex(b => b.scope === scope && b.variable === variable);
  assert.notEqual(index, -1);
  buttons[index].listeners.click();
}

change(1, "14");
assert.equal(texts[1].textContent, "Alpha: 14 · Shared: 3");
assert.equal(texts[2].textContent, "Beta: 2 · Shared: 3");

change(2, "88"); // upper bound 20
assert.equal(inputs[2].value, "20");
assert.equal(texts[1].textContent, "Alpha: 14 · Shared: 3");
assert.equal(texts[2].textContent, "Beta: 20 · Shared: 3");

change(0, "14");
assert.equal(texts[0].textContent, "Shared value: 14");
assert.equal(texts[1].textContent, "Alpha: 14 · Shared: 14");
assert.equal(texts[2].textContent, "Beta: 20 · Shared: 14");

change(0, "-40"); // lower bound zero
assert.equal(inputs[0].value, "0");
assert.equal(texts[1].textContent, "Alpha: 14 · Shared: 0");

change(1, "5.2"); // reject non-integer
assert.equal(inputs[1].value, "14");
change(1, "<script>alert(1)</script>"); // reject invalid input
assert.equal(inputs[1].value, "14");

click("instance_0", "meter");
assert.equal(inputs[1].value, "15");
assert.equal(inputs[2].value, "20");
click("instance_0", "shared");
assert.equal(inputs[0].value, "1");
assert.equal(texts[2].textContent, "Beta: 20 · Shared: 1");
console.log("VibeWeb Phase 3C grid + numeric form runtime PASS");
