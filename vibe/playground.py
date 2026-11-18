"""Loopback-only VibeWeb playground powered by the real native compiler.

No shell commands, arbitrary file writes, imported user modules or remote APIs.
The preview is sandboxed in the browser; never serve compiler output as the
playground document itself.
"""
from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .emitter import emit_code
from .ir import ast_to_ir
from .parser import ParseError, parse_source
from .verifier import verify
from .web import WebSpecError

MAX_SOURCE_CHARS = 20_000
MAX_REQUEST_BYTES = 40_000
EXAMPLES = {
    "counter": ("Bounded counter", "web_counter.vibe"),
    "components": ("Independent components", "web_instances.vibe"),
    "forms": ("Form studio", "web_text_forms.vibe"),
    "typing": ("Keyboard dojo", "web_typing_dojo.vibe"),
    "curriculum": ("Typing curriculum", "web_typing_course.vibe"),
    "packs": ("Lesson packs", "web_typing_packs.vibe"),
}
_HTML = Path(__file__).with_name("playground.html")
_EXAMPLES_DIR = Path(__file__).with_name("examples")


def compile_document(source: str) -> dict[str, object]:
    """Compile from in-memory text; preserve the existing Vibe bridge gate."""
    if not isinstance(source, str):
        return {"ok": False, "diagnostics": [{"level": "error", "message": "source must be a string"}]}
    if len(source) > MAX_SOURCE_CHARS:
        return {"ok": False, "diagnostics": [{"level": "error", "message": "source exceeds 20,000 characters"}]}
    try:
        program = parse_source(source)
        if program.web_page is None or program.emit_target != "web":
            raise WebSpecError("The playground accepts VibeWeb page specs ending with emit web.")
        ir = ast_to_ir(program)
        html, backend = emit_code(ir)
        if backend.target != "web":
            raise WebSpecError("Unexpected backend: only native web emission is supported.")
        result = verify(ir, html, use_calibration=False)
        if not result.passed:
            return {
                "ok": False,
                "diagnostics": [{
                    "level": "error",
                    "message": f"Heuristic preservation gate rejected output (score={result.bridge_score:.4f}).",
                }],
            }
        return {
            "ok": True,
            "html": html,
            "report": {
                "intent": program.intent.name,
                "target": "web",
                "size_bytes": len(html.encode("utf-8")),
                "bridge_score": round(float(result.bridge_score), 6),
                "bridge_passed": True,
                "checks": ["bounded VibeWeb grammar", "typed SSA IR", "native web emitter",
                           "heuristic preservation gate"],
                "disclaimer": "Bridge scores are heuristic, not proof of browser safety or correctness.",
            },
            "diagnostics": [{"level": "info", "message": "Compilation succeeded. Browser preview is sandboxed."}],
        }
    except (ParseError, WebSpecError, ValueError, TypeError) as exc:
        diagnostic: dict[str, object] = {"level": "error", "message": str(exc)[:1500]}
        line = getattr(exc, "line", None)
        column = getattr(exc, "column", None)
        if isinstance(line, int):
            diagnostic["line"] = line
        else:
            match = re.search(r"\bline\s+(\d+)\b", str(exc))
            if match:
                diagnostic["line"] = int(match.group(1))
        if isinstance(column, int):
            diagnostic["column"] = column
        return {"ok": False, "diagnostics": [diagnostic]}


class PlaygroundServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class PlaygroundHandler(BaseHTTPRequestHandler):
    server_version = "VibeWebPlayground/0.1"
    protocol_version = "HTTP/1.1"

    def _allowed_host(self) -> bool:
        host = self.headers.get("Host", "")
        return bool(re.fullmatch(r"(?:127\.0\.0\.1|localhost)(?::\d{1,5})?", host))

    def _headers(self, status: int, content_type: str, content: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; frame-src 'self' about:; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, data: dict[str, object]) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", content)

    def _reject_host(self) -> bool:
        if not self._allowed_host():
            self._json(403, {"error": "Only localhost/127.0.0.1 Host is accepted."})
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        if self._reject_host():
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._headers(200, "text/html; charset=utf-8", _HTML.read_bytes())
        elif parsed.path == "/health":
            self._json(200, {"status": "ok", "compiler": "native"})
        elif parsed.path == "/api/examples":
            self._json(200, {"examples": [{"key": key, "title": title}
                                          for key, (title, _) in EXAMPLES.items()]})
        elif parsed.path == "/api/example":
            name = parse_qs(parsed.query).get("name", [""])[0]
            if name not in EXAMPLES:
                self._json(404, {"error": "Unknown example."})
                return
            title, filename = EXAMPLES[name]
            self._json(200, {"title": title, "source": (_EXAMPLES_DIR / filename).read_text(encoding="utf-8")})
        else:
            self._json(404, {"error": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        if self._reject_host():
            return
        if urlsplit(self.path).path != "/api/compile":
            self._json(404, {"error": "Not found."})
            return
        # Cross-origin websites cannot set this non-simple header without a
        # preflight; this server neither accepts OPTIONS nor returns CORS headers.
        if self.headers.get("X-Vibe-Playground") != "compile":
            self._json(403, {"error": "Missing playground request header."})
            return
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and origin not in {"http://" + host, "https://" + host}:
            self._json(403, {"error": "Cross-origin compile requests are forbidden."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._json(415, {"error": "Expected application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._json(413, {"error": "Request must be a bounded JSON payload."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeError):
            self._json(400, {"error": "Malformed JSON request."})
            return
        if not isinstance(payload, dict) or set(payload) != {"source"}:
            self._json(400, {"error": "Expected only the source property."})
            return
        self._json(200, compile_document(payload["source"]))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._json(405, {"error": "CORS preflight not supported."})

    def log_message(self, format: str, *args: object) -> None:
        # Do not log user-written source, submitted JSON, or URL query values.
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the VibeWeb loopback playground")
    parser.add_argument("--port", type=int, default=4320, help="localhost TCP port, default 4320")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    server = PlaygroundServer(("127.0.0.1", args.port), PlaygroundHandler)
    print(f"VibeWeb Playground: http://127.0.0.1:{args.port}/", flush=True)
    print("Loopback-only, no file writes or network submission. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
