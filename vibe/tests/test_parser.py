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
