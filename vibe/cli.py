"""CLI entrypoint for vibec."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .generator_python import generate_python
from .ir import ast_to_ir
from .parser import parse_source
from .report import render_report, render_report_json
from .verifier import verify


ReportMode = str


def _load(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return path.read_text(encoding="utf-8")


def _print_report(result, report: ReportMode) -> None:
    if report == "json":
        print(render_report_json(result))
    else:
        print(render_report(result))


def _compile(path: Path, report: ReportMode) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    py_code = generate_python(ir)
    result = verify(ir, py_code)
    _print_report(result, report)
    if not result.passed:
        print("compile failed: bridge preservation threshold not met")
        return 1

    out_path = path.with_suffix(".py")
    out_path.write_text(py_code, encoding="utf-8")
    print(f"emitted: {out_path}")
    return 0


def _explain(path: Path) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    py_code = generate_python(ir)
    result = verify(ir, py_code)
    print("AST:")
    print(ast)
    print("\nNormalized IR:")
    print(json.dumps(asdict(ir), indent=2, sort_keys=True))
    print("\nPreservation reasoning:")
    print(render_report(result))
    return 0


def _verify(path: Path, report: ReportMode) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    py_code = generate_python(ir)
    result = verify(ir, py_code)
    _print_report(result, report)
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibec", description="Vibe compiler prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    cp = sub.add_parser("compile", help="Compile a .vibe source file")
    cp.add_argument("path", type=Path)
    cp.add_argument("--report", choices=["human", "json"], default="human")

    ex = sub.add_parser("explain", help="Explain AST and IR")
    ex.add_argument("path", type=Path)

    vf = sub.add_parser("verify", help="Run verifier without emission")
    vf.add_argument("path", type=Path)
    vf.add_argument("--report", choices=["human", "json"], default="human")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        return _compile(args.path, args.report)
    if args.command == "explain":
        return _explain(args.path)
    if args.command == "verify":
        return _verify(args.path, args.report)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
