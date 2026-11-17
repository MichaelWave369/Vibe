// Exercise emitted VibeWeb string fields/selects in a minimal fake DOM.
// This is a runtime smoke test, not a full-browser accessibility certification.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const dataMatch = html.match(/<script type="application\/json" id="vibe-config">([\s\S]*?)<\/script>/);
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert(dataMatch && scriptMatch, "HTML contains data and runtime script");
const config = JSON.parse(dataMatch[1]);
assert.equal(config.string_fields.length, 6);
const texts = config.texts.map((_, i) => ({ dataset: { vibeText: String(i) }, textContent: "" }));
const buttons = config.buttons.map((_, i) => ({
  dataset: { vibeButton: String(i) },
  listeners: {},
  addEventListener(event, callback) { this.listeners[event] = callback; }
}));
const strings = config.string_fields.map((_, i) => ({
  dataset: { vibeString: String(i) },
  value: "",
  attrs: { "aria-invalid": "false" },
  listeners: {},
  addEventListener(event, callback) { this.listeners[event] = callback; },
  setAttribute(name, value) { this.attrs[name] = value; }
}));
const errors = Object.fromEntries(strings.map((_, i) =>
  ["vibe-string-error-" + i, { textContent: "" }]));
const document = {
  getElementById(id) {
    if (id === "vibe-config") return { textContent: dataMatch[1] };
    assert(errors[id], "expected error element " + id);
    return errors[id];
  },
  querySelectorAll(selector) {
    if (selector === "[data-vibe-text]") return texts;
    if (selector === "[data-vibe-button]") return buttons;
    if (selector === "[data-vibe-string]") return strings;
    throw new Error("Unexpected DOM selector " + selector);
  }
};
vm.runInNewContext(scriptMatch[1], { document });
assert.deepEqual(strings.map(s => s.value), [
  "Mikey", "Teal", "Visitor", "Calm", "Visitor", "Calm"
]);
assert.equal(texts[0].textContent, "Hello Mikey! Theme: Teal. Total: 0");
assert.equal(texts[1].textContent, "Alpha: Visitor / Calm · Welcome Mikey · Total 0");
assert.equal(texts[2].textContent, "Beta: Visitor / Calm · Welcome Mikey · Total 0");

function change(index, value) {
  strings[index].value = value;
  strings[index].listeners.change();
}
function click(scope, variable) {
  const index = config.buttons.findIndex(b => b.scope === scope && b.variable === variable);
  assert.notEqual(index, -1);
  buttons[index].listeners.click();
}
change(2, "A"); // invalid name
assert.equal(strings[2].attrs["aria-invalid"], "true");
assert.match(errors["vibe-string-error-2"].textContent, /2 to 24 characters/);
assert.equal(texts[1].textContent, "Alpha: Visitor / Calm · Welcome Mikey · Total 0");
assert.equal(texts[2].textContent, "Beta: Visitor / Calm · Welcome Mikey · Total 0");

change(2, "Alice");
assert.equal(strings[2].attrs["aria-invalid"], "false");
assert.equal(errors["vibe-string-error-2"].textContent, "");
assert.equal(texts[1].textContent, "Alpha: Alice / Calm · Welcome Mikey · Total 0");
assert.equal(texts[2].textContent, "Beta: Visitor / Calm · Welcome Mikey · Total 0");

change(5, "Playful");
assert.equal(texts[1].textContent, "Alpha: Alice / Calm · Welcome Mikey · Total 0");
assert.equal(texts[2].textContent, "Beta: Visitor / Playful · Welcome Mikey · Total 0");

change(3, "INVALID");
assert.equal(strings[3].attrs["aria-invalid"], "true");
assert.match(errors["vibe-string-error-3"].textContent, /available options/);
assert.equal(texts[1].textContent, "Alpha: Alice / Calm · Welcome Mikey · Total 0");
change(3, "Focused");
assert.equal(strings[3].attrs["aria-invalid"], "false");
assert.equal(texts[1].textContent, "Alpha: Alice / Focused · Welcome Mikey · Total 0");

change(0, "Bridge");
change(1, "Purple");
assert.equal(texts[0].textContent, "Hello Bridge! Theme: Purple. Total: 0");
assert.equal(texts[1].textContent, "Alpha: Alice / Focused · Welcome Bridge · Total 0");
assert.equal(texts[2].textContent, "Beta: Visitor / Playful · Welcome Bridge · Total 0");
click("instance_1", "total");
assert.equal(texts[0].textContent, "Hello Bridge! Theme: Purple. Total: 1");

change(0, "X".repeat(40));
assert.equal(strings[0].attrs["aria-invalid"], "true");
assert.equal(texts[0].textContent, "Hello Bridge! Theme: Purple. Total: 1");
change(0, "<img src=x onerror=x>");
assert.equal(strings[0].attrs["aria-invalid"], "false");
assert.equal(texts[0].textContent, "Hello <img src=x onerror=x>! Theme: Purple. Total: 1");
console.log("VibeWeb Phase 3D text/select/validation runtime PASS");
