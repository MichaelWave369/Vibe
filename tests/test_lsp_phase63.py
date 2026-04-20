import json
from pathlib import Path

from vibe.cli import main
from vibe.lsp.server import VibeLanguageServer


def _doc_uri(path: Path) -> str:
    return path.resolve().as_uri()


def test_lsp_document_lifecycle_and_diagnostics(tmp_path: Path) -> None:
    srv = VibeLanguageServer()
    file = tmp_path / "main.vibe"
    source = """intent X:
  goal: \"g\"
  inputs:
    a: number
  outputs:
    b: number

emit python
"""
    file.write_text(source, encoding="utf-8")

    out = srv.handle(
        "textDocument/didOpen",
        {"textDocument": {"uri": _doc_uri(file), "version": 1, "text": source}},
    )
    assert out["diagnostics"] == []

    changed = "intent Broken:\n  goal \"missing colon\"\n"
    out2 = srv.handle(
        "textDocument/didChange",
        {
            "textDocument": {"uri": _doc_uri(file), "version": 2},
            "contentChanges": [{"text": changed}],
        },
    )
    assert any(d["code"] == "parse.error" for d in out2["diagnostics"])


def test_lsp_hover_completion_definition_symbols_semantic_tokens(tmp_path: Path) -> None:
    srv = VibeLanguageServer()
    root = tmp_path / "pkg"
    main(["init", str(root)])
    (root / "src" / "helper.vibe").write_text(
        """intent Helper:
  goal: \"h\"
  inputs:
    x: number
  outputs:
    y: number

emit python
""",
        encoding="utf-8",
    )
    src = root / "src" / "main.vibe"
    src.write_text(
        """import helper

type PaymentRecord
interface PaymentService
enum PaymentStatus

intent PaymentRouter:
  goal: \"Route payment\"
  inputs:
    amount: number
  outputs:
    processor: string

preserve:
  latency < 200ms

bridge:
  measurement_safe_ratio = 0.85

emit python
""",
        encoding="utf-8",
    )
    uri = _doc_uri(src)
    text = src.read_text(encoding="utf-8")
    srv.handle("textDocument/didOpen", {"textDocument": {"uri": uri, "version": 1, "text": text}})

    # hover
    hover = srv.handle("textDocument/hover", {"textDocument": {"uri": uri}, "position": {"line": 6, "character": 10}})
    assert "PaymentRouter" in hover["contents"]["value"]
    assert "semantic qualifiers" in hover["contents"]["value"]

    # completion
    comp = srv.handle("textDocument/completion", {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 0}})
    labels = [x["label"] for x in comp["items"]]
    assert "import" in labels
    assert "helper" in labels

    # definition (helper import)
    dfn = srv.handle("textDocument/definition", {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 9}})
    assert dfn is not None

    # symbols
    syms = srv.handle("textDocument/documentSymbol", {"textDocument": {"uri": uri}})
    sym_names = [s["name"] for s in syms]
    assert "PaymentRouter" in sym_names
    assert "PaymentRecord" in sym_names

    # semantic tokens deterministic
    tok1 = srv.handle("textDocument/semanticTokens/full", {"textDocument": {"uri": uri}})
    tok2 = srv.handle("textDocument/semanticTokens/full", {"textDocument": {"uri": uri}})
    assert tok1 == tok2
    assert tok1["data"]

    # lenses
    lenses = srv.handle("textDocument/codeLens", {"textDocument": {"uri": uri}})
    assert lenses


def test_lsp_package_import_diagnostics_and_save_deep(tmp_path: Path) -> None:
    srv = VibeLanguageServer()
    root = tmp_path / "pkg"
    main(["init", str(root)])
    src = root / "src" / "main.vibe"
    bad = """import unknown.module

intent A:
  goal: \"a\"
  inputs:
    x: number
  outputs:
    y: number

bridge:
  measurement_safe_ratio = 2.0

emit python
"""
    src.write_text(bad, encoding="utf-8")
    uri = _doc_uri(src)

    srv.handle("textDocument/didOpen", {"textDocument": {"uri": uri, "version": 1, "text": bad}})
    save = srv.handle("textDocument/didSave", {"textDocument": {"uri": uri}})
    codes = [d.get("code") for d in save["diagnostics"]]
    assert "import.unresolved" in codes
    assert "bridge.range" in codes


def test_vibec_lsp_check_command(capsys) -> None:
    rc = main(["lsp", "--check"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "vibe-lsp: ready" in out


def test_lsp_initialize_capabilities_shape() -> None:
    srv = VibeLanguageServer()
    payload = srv.handle("initialize", {})
    assert payload["serverInfo"]["name"] == "vibe-lsp"
    caps = payload["capabilities"]
    assert caps["hoverProvider"] is True
    assert caps["definitionProvider"] is True
    assert caps["semanticTokensProvider"]["full"] is True
    # deterministic serialization surface
    assert json.dumps(payload, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_lsp_python_completion_and_hover_support(tmp_path: Path) -> None:
    srv = VibeLanguageServer()
    py_file = tmp_path / "app.py"
    text = "forloop\nif True:\n    requests.get('https://example.com')\n"
    py_file.write_text(text, encoding="utf-8")
    uri = _doc_uri(py_file)
    srv.handle("textDocument/didOpen", {"textDocument": {"uri": uri, "version": 1, "text": text}})

    completion = srv.handle(
        "textDocument/completion",
        {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 7}},
    )
    labels = [item["label"] for item in completion["items"]]
    assert "forloop" in labels

    hover_snippet = srv.handle(
        "textDocument/hover",
        {"textDocument": {"uri": uri}, "position": {"line": 0, "character": 3}},
    )
    assert "PhiPython snippet" in hover_snippet["contents"]["value"]

    hover_keyword = srv.handle(
        "textDocument/hover",
        {"textDocument": {"uri": uri}, "position": {"line": 1, "character": 1}},
    )
    assert "conditional branch" in hover_keyword["contents"]["value"]

    actions = srv.handle(
        "textDocument/codeAction",
        {
            "textDocument": {"uri": uri},
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 7}},
            "context": {"diagnostics": [{"code": "parse.error", "message": "demo"}]},
        },
    )
    titles = [item["title"] for item in actions]
    assert any("expand snippet" in title for title in titles)
    assert any("preview safe patch" in title for title in titles)
    assert any("list candidate patches" in title for title in titles)
    assert any("run scaffold doctor on project" in title for title in titles)
    assert any("explain this error" in title for title in titles)
