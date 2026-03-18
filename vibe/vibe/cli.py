"""CLI entrypoint for vibec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator_python import generate_python
from .ir import ast_to_ir
from .parser import parse_source
from .report import render_report
from .verifier import verify


def _load(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return path.read_text(encoding="utf-8")


def _compile(path: Path) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    py_code = generate_python(ir)
    result = verify(ir, py_code)
    print(render_report(result))
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
    print(json.dumps(ir.__dict__, indent=2, sort_keys=True))
    print("\nPreservation reasoning:")
    print(render_report(result))
    return 0


def _verify(path: Path) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    py_code = generate_python(ir)
    result = verify(ir, py_code)
    print(render_report(result))
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibec", description="Vibe compiler prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    cp = sub.add_parser("compile", help="Compile a .vibe source file")
    cp.add_argument("path", type=Path)

    ex = sub.add_parser("explain", help="Explain AST and IR")
    ex.add_argument("path", type=Path)

    vf = sub.add_parser("verify", help="Run verifier without emission")
    vf.add_argument("path", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        return _compile(args.path)
    if args.command == "explain":
        return _explain(args.path)
    if args.command == "verify":
        return _verify(args.path)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
