// Execute Phase 3E generated JavaScript against a minimal fake DOM.
// This verifies local persistence and custom submission events, not full browser compatibility.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[2], "utf8");
const cfgMatch = html.match(/<script type="application\/json" id="vibe-config">([\s\S]*?)<\/script>/);
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
assert(cfgMatch && scriptMatch, "compiled config and runtime exist");
const config = JSON.parse(cfgMatch[1]);
assert.equal(config.persistence, "local");
assert(html.includes('<form id="vibe-form" novalidate>'));
const saved = new Map();

function start({ blocked = false } = {}) {
  const texts = config.texts.map((_, i) => ({ dataset: { vibeText: String(i) }, textContent: "" }));
  const buttons = config.buttons.map((_, i) => ({
    dataset: { vibeButton: String(i) }, handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; }
  }));
  const numeric = config.inputs.map((_, i) => ({
    dataset: { vibeInput: String(i) }, value: "", handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; }
  }));
  const strings = config.string_fields.map((_, i) => ({
    dataset: { vibeString: String(i) }, value: "", attrs: {},
    handlers: {},
    addEventListener(name, fn) { this.handlers[name] = fn; },
    setAttribute(name, value) { this.attrs[name] = value; }
  }));
  const errors = Object.fromEntries(strings.map((_, i) => ["vibe-string-error-" + i, { textContent: "" }]));
  const status = { textContent: "" };
  const form = { handlers: {}, addEventListener(name, fn) { this.handlers[name] = fn; } };
  const events = [];
  const localStorage = {
    getItem(key) {
      if (blocked) throw Error("blocked");
      return saved.get(key) ?? null;
    },
    setItem(key, value) {
      if (blocked) throw Error("blocked");
      saved.set(key, value);
    }
  };
  const window = { localStorage, dispatchEvent(event) { events.push(event); } };
  const document = {
    getElementById(id) {
      if (id === "vibe-config") return { textContent: cfgMatch[1] };
      if (id === "vibe-form") return form;
      if (id === "vibe-form-status") return status;
      if (Object.hasOwn(errors, id)) return errors[id];
      throw Error("Unexpected ID " + id);
    },
    querySelectorAll(selector) {
      if (selector === "[data-vibe-text]") return texts;
      if (selector === "[data-vibe-button]") return buttons;
      if (selector === "[data-vibe-input]") return numeric;
      if (selector === "[data-vibe-string]") return strings;
      throw Error("Unexpected selector " + selector);
    }
  };
  function CustomEvent(type, options) {
    this.type = type;
    this.detail = options.detail;
  }
  vm.runInNewContext(scriptMatch[1], { document, window, CustomEvent });
  return {
    texts, buttons, numeric, strings, errors, status, events,
    change(index, value) {
      strings[index].value = value;
      strings[index].handlers.change();
    },
    submit() {
      let prevented = false;
      form.handlers.submit({ preventDefault() { prevented = true; } });
      assert(prevented, "submit never navigates or sends network request");
    },
    click(scope, variable) {
      const i = config.buttons.findIndex(action => action.scope === scope && action.variable === variable);
      assert.notEqual(i, -1);
      buttons[i].handlers.click();
    }
  };
}

const a = start();
assert.equal(a.status.textContent, "");
assert.equal(a.strings[0].value, "Mikey");
a.change(0, "Bridge");
a.change(1, "Purple");
a.change(2, "Alice");
a.change(3, "Focused");
a.change(4, "Bob");
a.change(5, "Playful");
a.click("instance_0", "total");
assert.equal(a.texts[0].textContent, "Hello Bridge! Theme: Purple. Total: 1");
a.submit();
assert.equal(a.status.textContent, "Draft saved locally in this browser.");
assert.equal(a.events.length, 1);
assert.equal(a.events[0].type, "vibe:submit");
assert.equal(a.events[0].detail.saved, true);
assert.equal(a.events[0].detail.values.text_state.display_name, "Bridge");
assert.equal(a.events[0].detail.values.scope_text_states.instance_1.name, "Bob");
assert(saved.has(config.storage_key));

const b = start();
assert.equal(b.status.textContent, "Previous local draft restored.");
assert.equal(b.strings[0].value, "Bridge");
assert.equal(b.strings[2].value, "Alice");
assert.equal(b.strings[4].value, "Bob");
assert.equal(b.texts[0].textContent, "Hello Bridge! Theme: Purple. Total: 1");
b.strings[0].value = "X"; // not committed via change, submission must fail closed
b.submit();
assert.match(b.status.textContent, /correct or finish editing/);
assert.equal(b.events.length, 0);
assert.equal(JSON.parse(saved.get(config.storage_key)).text_state.display_name, "Bridge");
b.change(0, "Z"); // invalid length, still not committed
b.submit();
assert.equal(b.events.length, 0);
b.change(0, "Bridge Two");
b.submit();
assert.equal(b.events.length, 1);
assert.equal(b.events[0].detail.values.text_state.display_name, "Bridge Two");

const bad = JSON.parse(saved.get(config.storage_key));
bad.scope_text_states.instance_1.mood = "UNLISTED";
saved.set(config.storage_key, JSON.stringify(bad));
const c = start();
assert.match(c.status.textContent, /did not match/);
assert.equal(c.strings[0].value, "Mikey");
assert.equal(c.strings[4].value, "Visitor");

saved.set(config.storage_key, "not json");
const d = start();
assert.match(d.status.textContent, /unavailable/);
assert.equal(d.strings[0].value, "Mikey");

const e = start({ blocked: true });
assert.match(e.status.textContent, /unavailable/);
e.submit();
assert.match(e.status.textContent, /not saved/);
assert.equal(e.events.length, 1);
assert.equal(e.events[0].detail.saved, false);
console.log("VibeWeb Phase 3E: local drafts, validation, form submission events PASS");
