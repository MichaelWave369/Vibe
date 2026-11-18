"""Native VibeWeb Playground unit and loopback HTTP tests."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from vibe.playground import (
    EXAMPLES, MAX_SOURCE_CHARS, PlaygroundHandler, PlaygroundServer,
    compile_document,
)


def sample(name: str = "counter") -> str:
    filename = EXAMPLES[name][1]
    return (Path(__file__).parent.parent / "vibe" / "examples" / filename).read_text(encoding="utf-8")


def test_playground_uses_same_native_web_compiler_and_verifier():
    result = compile_document(sample("counter"))
    assert result["ok"] is True
    assert result["report"]["intent"] == "CounterPage"
    assert result["report"]["target"] == "web"
    assert result["report"]["bridge_passed"] is True
    assert result["report"]["bridge_score"] > 0
    assert "<!doctype html>" in result["html"]
    assert 'id="vibe-config"' in result["html"]
    assert result["report"]["size_bytes"] == len(result["html"].encode("utf-8"))
    assert result["diagnostics"][0]["level"] == "info"


def test_playground_compiles_typing_lesson_and_legacy_examples():
    for name in ("components", "forms", "typing", "curriculum", "packs"):
        result = compile_document(sample(name))
        assert result["ok"] is True, (name, result.get("diagnostics"))
        assert result["report"]["target"] == "web"
        assert "<!doctype html>" in result["html"]


def test_playground_fails_closed_on_invalid_or_excessive_source():
    error = compile_document("intent NoPage:\n  goal: \"hello\"\nemit web\n")
    assert error["ok"] is False
    assert error["diagnostics"][0]["level"] == "error"
    error = compile_document(sample().replace("page CounterPage:", "page WrongPage:"))
    assert error["ok"] is False
    assert "message" in error["diagnostics"][0]
    error = compile_document(sample().replace("count += 1", "eval(1)"))
    assert error["ok"] is False
    assert "message" in error["diagnostics"][0]
    assert compile_document("x" * (MAX_SOURCE_CHARS + 1))["ok"] is False
    assert compile_document(None)["ok"] is False


@pytest.fixture()
def local_server():
    server = PlaygroundServer(("127.0.0.1", 0), PlaygroundHandler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def http_request(base: str, path: str, *, method: str = "GET", data: object = None,
                 headers: dict[str, str] | None = None):
    content = None if data is None else json.dumps(data).encode("utf-8")
    request = Request(base + path, data=content, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def compile_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "X-Vibe-Playground": "compile"}


def test_playground_static_page_and_allowlisted_examples(local_server):
    code, headers, document = http_request(local_server, "/")
    assert code == 200
    assert b'VibeWeb Playground' in document
    assert b'sandbox="allow-scripts"' in document
    assert b'sandbox="allow-scripts allow-same-origin"' not in document
    assert b'sandbox="allow-same-origin' not in document
    assert headers["Cache-Control"] == "no-store"
    assert "Content-Security-Policy" in headers

    code, _, content = http_request(local_server, "/health")
    assert code == 200 and json.loads(content)["compiler"] == "native"
    code, _, content = http_request(local_server, "/api/examples")
    listing = json.loads(content)["examples"]
    assert code == 200 and len(listing) >= 5
    code, _, content = http_request(local_server, "/api/example?name=packs")
    assert code == 200 and "pack=" in json.loads(content)["source"]
    code, _, content = http_request(local_server, "/api/example?name=../../secret")
    assert code == 404
    code, _, content = http_request(local_server, "/not-found")
    assert code == 404


def test_playground_compile_endpoint_is_memory_only_and_returns_diagnostics(local_server):
    code, headers, content = http_request(local_server, "/api/compile", method="POST",
                                          data={"source": sample("counter")}, headers=compile_headers())
    result = json.loads(content)
    assert code == 200 and result["ok"] is True
    assert "<!doctype html>" in result["html"]
    assert headers["Content-Type"].startswith("application/json")
    code, _, content = http_request(local_server, "/api/compile", method="POST",
                                    data={"source": sample("counter").replace("count += 1", "eval(1)")},
                                    headers=compile_headers())
    result = json.loads(content)
    assert code == 200 and result["ok"] is False
    assert result["diagnostics"][0]["level"] == "error"


def test_playground_request_validation_and_csrf_guard(local_server):
    for headers, status in [
        ({"Content-Type": "application/json"}, 403),
        ({"X-Vibe-Playground": "compile", "Content-Type": "text/plain"}, 415),
        ({**compile_headers(), "Origin": "https://malicious.example"}, 403),
        ({**compile_headers(), "Host": "evil.example"}, 403),
    ]:
        code, _, _ = http_request(local_server, "/api/compile", method="POST",
                                  data={"source": sample("counter")}, headers=headers)
        assert code == status, (headers, code)

    for data, status in [
        ({"source": sample(), "filename": "../example"}, 400),
        ({"not_source": sample()}, 400),
        ({"source": ["not a string"]}, 200),
        ({"source": "x" * (MAX_SOURCE_CHARS + 1)}, 200),
    ]:
        code, _, body = http_request(local_server, "/api/compile", method="POST",
                                     data=data, headers=compile_headers())
        assert code == status
        if code == 200:
            assert json.loads(body)["ok"] is False

    code, _, _ = http_request(local_server, "/api/compile", method="OPTIONS")
    assert code == 405
    code, _, _ = http_request(local_server, "/api/no", method="POST",
                              data={"source": sample()}, headers=compile_headers())
    assert code == 404
