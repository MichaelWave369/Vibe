from pathlib import Path

import pytest

from vibe.parser import ParseError, parse_source


EXAMPLE = Path("vibe/examples/payment_router.vibe")


def test_parse_valid_payment_router() -> None:
    ast = parse_source(EXAMPLE.read_text(encoding="utf-8"))
    assert ast.intent.name == "PaymentRouter"
    assert ast.intent.goal.startswith("Route payments")
    assert len(ast.intent.inputs) == 3
    assert len(ast.intent.outputs) == 2
    assert ast.emit_target == "python"


def test_parse_rejects_missing_intent() -> None:
    bad = "preserve:\n  readability = high\n"
    with pytest.raises(ParseError):
        parse_source(bad)


def test_parse_rejects_malformed_rule() -> None:
    bad = """
intent Demo:
  goal: \"x\"
preserve:
  unreadable rule
emit python
"""
    with pytest.raises(ParseError):
        parse_source(bad)


def test_parse_reports_line_and_column() -> None:
    bad = """
intent Demo:
  goal: \"x\"
  inputs:
   x: number
emit python
"""
    with pytest.raises(ParseError) as exc:
        parse_source(bad)
    msg = str(exc.value)
    assert "Line" in msg and "Col" in msg


def test_new_top_level_blocks_parse() -> None:
    src = """
vibe_version 1.1
import std.core
module resonance.bridge
type SignalState
enum BridgeMode
interface PreservationContract

intent Demo:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
emit python
"""
    ast = parse_source(src)
    assert ast.vibe_version == "1.1"
    assert ast.imports == ["std.core"]
    assert ast.modules == ["resonance.bridge"]
    assert ast.types == ["SignalState"]
    assert ast.enums == ["BridgeMode"]
    assert ast.interfaces == ["PreservationContract"]
