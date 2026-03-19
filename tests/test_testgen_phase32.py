import json
from pathlib import Path

from vibe.cli import main
from vibe.ir import ast_to_ir
from vibe.parser import parse_source
from vibe.proof import load_proof_artifact
from vibe.testgen import generate_intent_guided_tests


def _load_ir(example_path: str):
    source = Path(example_path).read_text(encoding="utf-8")
    return ast_to_ir(parse_source(source))


def test_generate_python_suite_deterministic_naming_and_content() -> None:
    ir = _load_ir("vibe/examples/payment_router.vibe")
    out_path = Path("payment_router.py")

    s1 = generate_intent_guided_tests(ir, out_path, emitted_code="", candidate_id="candidate.1")
    s2 = generate_intent_guided_tests(ir, out_path, emitted_code="", candidate_id="candidate.1")

    assert s1.generated_files == s2.generated_files
    assert "payment_router.py" not in s1.generated_files
    assert "test_payment_router_intent.py" in next(iter(s1.generated_files.keys()))
    content = next(iter(s1.generated_files.values()))
    assert "def test_intent_shape_anchor_candidate_1" in content
    assert any(item.startswith("preserve:") for item in s1.uncovered_items)
    assert any(item.startswith("constraint:") for item in s1.partial_coverage_items)


def test_generate_typescript_suite_deterministic_naming_and_content() -> None:
    ir = _load_ir("vibe/examples/edge_contract_ts.vibe")
    out_path = Path("edge_contract_ts.ts")

    suite = generate_intent_guided_tests(ir, out_path, emitted_code="", candidate_id="candidate.2")
    test_path = next(iter(suite.generated_files.keys()))
    content = suite.generated_files[test_path]

    assert test_path.endswith("edge_contract_ts.intent.test.ts")
    assert "describe('intent-guided tests (candidate.2)'" in content
    assert "shape anchor" in content


def test_compile_with_tests_emits_python_tests(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["compile", str(case), "--with-tests"])
    assert rc == 0

    emitted = case.with_suffix(".py")
    generated_test = case.with_name("test_payment_router_intent.py")
    assert emitted.exists()
    assert generated_test.exists()


def test_compile_with_tests_emits_typescript_tests(tmp_path) -> None:
    src = Path("vibe/examples/edge_contract_ts.vibe")
    case = tmp_path / "edge_contract_ts.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["compile", str(case), "--with-tests"])
    assert rc == 0

    emitted = case.with_suffix(".ts")
    generated_test = case.with_name("edge_contract_ts.intent.test.ts")
    assert emitted.exists()
    assert generated_test.exists()


def test_verify_report_json_includes_test_generation_metadata(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["verify", str(case), "--with-tests", "--report", "json"])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["test_generation_enabled"] is True
    assert payload["generated_test_files"]
    assert "preserve_rule_coverage" in payload
    assert "constraint_coverage" in payload
    assert "uncovered_items" in payload
    assert "partial_coverage_items" in payload
    assert "test_generation_notes" in payload


def test_compile_proof_includes_test_generation_metadata(tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rc = main(["compile", str(case), "--with-tests", "--write-proof"])
    assert rc == 0

    proof = load_proof_artifact(case.with_suffix(".vibe.proof.json"))
    assert "intent_guided_tests" in proof
    tests = proof["intent_guided_tests"]
    assert tests["test_generation_enabled"] is True
    assert tests["generated_test_files"]
    assert "preserve_rule_coverage" in tests
    assert "constraint_coverage" in tests
    assert "uncovered_items" in tests
    assert "partial_coverage_items" in tests
    assert "test_generation_notes" in tests
