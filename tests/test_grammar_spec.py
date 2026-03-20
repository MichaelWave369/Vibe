from vibe.grammar import GRAMMAR


def test_grammar_is_primary_definition_contains_new_blocks() -> None:
    assert "vibe_version" in GRAMMAR
    assert "import" in GRAMMAR
    assert "module" in GRAMMAR
    assert "type" in GRAMMAR
    assert "enum" in GRAMMAR
    assert "interface" in GRAMMAR
    assert "experimental.tesla.victory.layer" in GRAMMAR
    assert "agentora" in GRAMMAR
    assert "agentception" in GRAMMAR
    assert "sigil:" in GRAMMAR
    assert "sigil_temporal:" in GRAMMAR
