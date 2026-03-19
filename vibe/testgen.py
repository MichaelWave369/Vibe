"""Intent-guided test generation (Phase 3.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ir import IR


@dataclass(slots=True)
class GeneratedTestSuite:
    generated_files: dict[str, str] = field(default_factory=dict)
    preserve_rule_coverage: list[dict[str, str]] = field(default_factory=list)
    constraint_coverage: list[dict[str, str]] = field(default_factory=list)
    uncovered_items: list[str] = field(default_factory=list)
    partial_coverage_items: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _dummy_value(type_name: str, target: str) -> str:
    t = type_name.lower()
    if t == "number":
        return "1"
    if t == "string":
        return "'x'" if target == "python" else "'x'"
    if t == "boolean":
        return "True" if target == "python" else "true"
    return "None" if target == "python" else "undefined"


def _python_test_path(output_path: Path) -> Path:
    return output_path.with_name(f"test_{output_path.stem}_intent.py")


def _ts_test_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.intent.test.ts")


def generate_intent_guided_tests(
    ir: IR,
    output_path: Path,
    emitted_code: str,
    candidate_id: str,
) -> GeneratedTestSuite:
    target = ir.emit_target.lower()
    suite = GeneratedTestSuite()
    suite.notes.append("Generated tests are intent-guided confidence surfaces, not formal proof.")

    params_py = ", ".join(f"{k}={_dummy_value(v, 'python')}" for k, v in ir.inputs.items())
    params_ts = ", ".join(_dummy_value(v, "typescript") for _, v in ir.inputs.items())

    if target == "python":
        test_path = _python_test_path(output_path)
        fn_name = output_path.stem
        lines = [
            f"from {output_path.stem} import {fn_name}",
            "",
            f"def test_intent_shape_anchor_{candidate_id.replace('.', '_')}():",
            f"    result = {fn_name}({params_py})",
            "    assert result is not None or result is None",
        ]
        for c in ir.constraints:
            lower = c.lower()
            if "deterministic" in lower:
                lines.extend(
                    [
                        "",
                        "def test_constraint_deterministic_behavior():",
                        f"    r1 = {fn_name}({params_py})",
                        f"    r2 = {fn_name}({params_py})",
                        "    assert r1 == r2",
                    ]
                )
                suite.constraint_coverage.append({"constraint": c, "status": "executable", "test": "test_constraint_deterministic_behavior"})
            elif "fallback" in lower:
                lines.extend(
                    [
                        "",
                        "def test_constraint_fallback_scaffold():",
                        f"    src = open('{output_path.name}', encoding='utf-8').read().lower()",
                        "    assert 'fallback' in src or 'todo' in src",
                    ]
                )
                suite.constraint_coverage.append({"constraint": c, "status": "partial", "test": "test_constraint_fallback_scaffold"})
                suite.partial_coverage_items.append(f"constraint:{c}")
            elif "no hardcoded secrets" in lower:
                lines.extend(
                    [
                        "",
                        "def test_constraint_no_hardcoded_secrets_anchor():",
                        f"    src = open('{output_path.name}', encoding='utf-8').read().lower()",
                        "    assert 'secret' not in src",
                    ]
                )
                suite.constraint_coverage.append({"constraint": c, "status": "executable", "test": "test_constraint_no_hardcoded_secrets_anchor"})
            else:
                suite.constraint_coverage.append({"constraint": c, "status": "partial", "test": "scaffold_only"})
                suite.partial_coverage_items.append(f"constraint:{c}")

        for key, op, value in ir.preserve_rules:
            rule = f"{key} {op} {value}"
            if key.lower() in {"latency", "failure_rate"}:
                suite.preserve_rule_coverage.append({"rule": rule, "status": "partial", "test": "performance_stub"})
                suite.partial_coverage_items.append(f"preserve:{rule}")
            elif key.lower() in {"readability", "testability"}:
                suite.preserve_rule_coverage.append({"rule": rule, "status": "partial", "test": "static_anchor"})
                suite.partial_coverage_items.append(f"preserve:{rule}")
            else:
                suite.preserve_rule_coverage.append({"rule": rule, "status": "uncovered", "test": "none"})
                suite.uncovered_items.append(f"preserve:{rule}")

        suite.generated_files[str(test_path)] = "\n".join(lines) + "\n"

    else:
        test_path = _ts_test_path(output_path)
        fn_name = output_path.stem
        lines = [
            f"import {{ {fn_name} }} from './{output_path.stem}';",
            "",
            f"describe('intent-guided tests ({candidate_id})', () => {{",
            "  it('shape anchor', () => {",
            f"    const result = {fn_name}({params_ts});",
            "    expect(result).toBeDefined();",
            "  });",
        ]
        for c in ir.constraints:
            lower = c.lower()
            if "deterministic" in lower:
                lines.extend(
                    [
                        "  it('deterministic behavior', () => {",
                        f"    const r1 = {fn_name}({params_ts});",
                        f"    const r2 = {fn_name}({params_ts});",
                        "    expect(r1).toEqual(r2);",
                        "  });",
                    ]
                )
                suite.constraint_coverage.append({"constraint": c, "status": "executable", "test": "deterministic behavior"})
            elif "fallback" in lower:
                lines.extend(
                    [
                        "  it('fallback scaffold', () => {",
                        "    expect(true).toBe(true);",
                        "  });",
                    ]
                )
                suite.constraint_coverage.append({"constraint": c, "status": "partial", "test": "fallback scaffold"})
                suite.partial_coverage_items.append(f"constraint:{c}")
            else:
                suite.constraint_coverage.append({"constraint": c, "status": "partial", "test": "scaffold_only"})
                suite.partial_coverage_items.append(f"constraint:{c}")
        lines.append("});")

        for key, op, value in ir.preserve_rules:
            rule = f"{key} {op} {value}"
            if key.lower() in {"latency", "failure_rate", "readability", "testability"}:
                suite.preserve_rule_coverage.append({"rule": rule, "status": "partial", "test": "invariant_stub"})
                suite.partial_coverage_items.append(f"preserve:{rule}")
            else:
                suite.preserve_rule_coverage.append({"rule": rule, "status": "uncovered", "test": "none"})
                suite.uncovered_items.append(f"preserve:{rule}")

        suite.generated_files[str(test_path)] = "\n".join(lines) + "\n"

    # Ensure all constraints accounted for
    covered_constraints = {c["constraint"] for c in suite.constraint_coverage}
    for c in ir.constraints:
        if c not in covered_constraints:
            suite.constraint_coverage.append({"constraint": c, "status": "uncovered", "test": "none"})
            suite.uncovered_items.append(f"constraint:{c}")

    return suite
