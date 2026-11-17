import assert from "node:assert/strict";
import { startServer } from "./serve.mjs";

const server = await startServer({ port: 0 });
try {
  const base = "http://127.0.0.1:" + server.address().port;
  for (const [path, marker] of [
    ["/dist-qa/index.html", "VibeWeb"],
    ["/dist-qa-instances/index.html", "Two counters. One language."],
    ["/dist-qa-typing/index.html", "Keyboard Dojo · First Lesson"],
    ["/qa/vibeweb/dist-react/index.html", "React Counter Baseline"],
    ["/qa/vibeweb/dist-svelte/index.html", "Svelte Counter Baseline"],
  ]) {
    const response = await fetch(base + path);
    assert.equal(response.status, 200, path + " must serve real HTML");
    const html = await response.text();
    assert.match(html, /<html\b/i, path);
    assert(html.includes(marker), path + " missing expected generated document marker");
  }
  const traversal = await fetch(base + "/../not-inside-root");
  assert.notEqual(traversal.status, 200, "server must not expose outside files");
  console.log("VibeWeb QA static HTTP server smoke PASS");
} finally {
  await new Promise(resolve => server.close(resolve));
}
