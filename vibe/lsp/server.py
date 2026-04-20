from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

from .completion import completions
from .code_actions import python_code_actions
from .definitions import definition_location
from .diagnostics import collect_diagnostics
from .documents import DocumentStore
from .hover import hover_content, python_hover_content
from .lenses import intent_lenses
from .semantic_tokens import TOKEN_TYPES, semantic_tokens_full
from .symbols import document_symbols


@dataclass(slots=True)
class LSPResponse:
    id: int | str | None
    result: Any = None
    error: dict[str, object] | None = None


class VibeLanguageServer:
    def __init__(self) -> None:
        self.documents = DocumentStore()

    def initialize(self) -> dict[str, object]:
        return {
            "capabilities": {
                "textDocumentSync": 1,
                "hoverProvider": True,
                "completionProvider": {"resolveProvider": False},
                "codeActionProvider": True,
                "definitionProvider": True,
                "documentSymbolProvider": True,
                "codeLensProvider": {"resolveProvider": False},
                "semanticTokensProvider": {
                    "legend": {"tokenTypes": TOKEN_TYPES, "tokenModifiers": []},
                    "full": True,
                },
            },
            "serverInfo": {"name": "vibe-lsp", "version": "0.1"},
        }

    def _publish_diagnostics(self, uri: str, include_deep: bool = False) -> list[dict[str, object]]:
        doc = self.documents.get(uri)
        if doc is None:
            return []
        return collect_diagnostics(doc.text, path=doc.path, include_deep=include_deep)

    def on_did_open(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        text = str(td.get("text", ""))
        version = int(td.get("version", 0))
        self.documents.open(uri, text, version)
        return self._publish_diagnostics(uri, include_deep=False)

    def on_did_change(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        version = int(td.get("version", 0))
        changes = list(params.get("contentChanges", []))
        if not changes:
            return self._publish_diagnostics(uri, include_deep=False)
        text = str(changes[-1].get("text", ""))
        self.documents.update(uri, text, version)
        return self._publish_diagnostics(uri, include_deep=False)

    def on_did_save(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        return self._publish_diagnostics(uri, include_deep=True)

    def on_hover(self, params: dict[str, object]) -> dict[str, object] | None:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        pos = dict(params.get("position", {}))
        line = int(pos.get("line", 0))
        ch = int(pos.get("character", 0))
        doc = self.documents.get(uri)
        if doc is None:
            return None
        if doc.path is not None and doc.path.suffix == ".py":
            return python_hover_content(doc.text, line, ch)
        return hover_content(doc.text, line, ch)

    def on_completion(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        pos = dict(params.get("position", {}))
        line = int(pos.get("line", 0))
        character = int(pos.get("character", 0))
        doc = self.documents.get(uri)
        if doc is None:
            return []
        lines = doc.text.splitlines()
        prefix = ""
        if 0 <= line < len(lines):
            prefix = lines[line][:character].split()[-1] if lines[line][:character].strip() else ""
        return completions(prefix, path=doc.path)

    def on_definition(self, params: dict[str, object]) -> dict[str, object] | None:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        pos = dict(params.get("position", {}))
        doc = self.documents.get(uri)
        if doc is None:
            return None
        return definition_location(
            uri,
            doc.text,
            int(pos.get("line", 0)),
            int(pos.get("character", 0)),
            path=doc.path,
        )

    def on_document_symbol(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        doc = self.documents.get(uri)
        if doc is None:
            return []
        return document_symbols(doc.text)

    def on_semantic_tokens_full(self, params: dict[str, object]) -> dict[str, object]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        doc = self.documents.get(uri)
        if doc is None:
            return {"data": []}
        return semantic_tokens_full(doc.text)

    def on_code_lens(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        doc = self.documents.get(uri)
        if doc is None:
            return []
        return intent_lenses(doc.text)

    def on_code_action(self, params: dict[str, object]) -> list[dict[str, object]]:
        td = dict(params.get("textDocument", {}))
        uri = str(td.get("uri"))
        doc = self.documents.get(uri)
        if doc is None:
            return []
        range_params = dict(params.get("range", {}))
        start = dict(range_params.get("start", {}))
        end = dict(range_params.get("end", {}))
        start_line = int(start.get("line", 0))
        end_line = int(end.get("line", start_line))
        start_character = int(start.get("character", 0))
        end_character = int(end.get("character", 0))
        context = dict(params.get("context", {}))
        diagnostics = list(context.get("diagnostics", []))
        selected_text = None
        if 0 <= start_line < len(doc.text.splitlines()):
            selected_text = doc.text.splitlines()[start_line].strip()
        return python_code_actions(
            text=doc.text,
            path=doc.path,
            start_line=start_line,
            end_line=end_line,
            start_character=start_character,
            end_character=end_character,
            selected_text=selected_text,
            diagnostics=diagnostics,
        )

    def handle(self, method: str, params: dict[str, object] | None) -> Any:
        params = params or {}
        if method == "initialize":
            return self.initialize()
        if method == "textDocument/didOpen":
            return {"diagnostics": self.on_did_open(params)}
        if method == "textDocument/didChange":
            return {"diagnostics": self.on_did_change(params)}
        if method == "textDocument/didSave":
            return {"diagnostics": self.on_did_save(params)}
        if method == "textDocument/hover":
            return self.on_hover(params)
        if method == "textDocument/completion":
            return {"isIncomplete": False, "items": self.on_completion(params)}
        if method == "textDocument/definition":
            return self.on_definition(params)
        if method == "textDocument/documentSymbol":
            return self.on_document_symbol(params)
        if method == "textDocument/semanticTokens/full":
            return self.on_semantic_tokens_full(params)
        if method == "textDocument/codeLens":
            return self.on_code_lens(params)
        if method == "textDocument/codeAction":
            return self.on_code_action(params)
        if method in {"shutdown", "exit"}:
            return None
        raise KeyError(f"unsupported method: {method}")


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        text = line.decode("utf-8").strip()
        if not text:
            break
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    payload = sys.stdin.buffer.read(length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def _write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def run_stdio_server() -> int:
    server = VibeLanguageServer()
    while True:
        msg = _read_message()
        if msg is None:
            return 0
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}
        if not method:
            continue
        try:
            result = server.handle(str(method), dict(params))
            if req_id is not None:
                _write_message({"jsonrpc": "2.0", "id": req_id, "result": result})
            if method == "exit":
                return 0
        except Exception as exc:
            if req_id is not None:
                _write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": str(exc)},
                    }
                )


if __name__ == "__main__":
    raise SystemExit(run_stdio_server())
