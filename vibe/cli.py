"""CLI entrypoint for vibec."""

from __future__ import annotations

import argparse
from pathlib import Path

from ._version import __version__
from .cache import (
    CacheRecord,
    clear_cache,
    load_cache_record,
    save_cache_record,
    sha256_text,
)
from .emitter import emit_code, output_path_for
from .ir import ast_to_ir, serialize_ir
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


def _compile(path: Path, report: ReportMode, no_cache: bool = False, clean_cache: bool = False) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    ir_ser = serialize_ir(ir)
    source_hash = sha256_text(source)
    ir_hash = sha256_text(ir_ser)

    emitted_code, backend = emit_code(ir)
    out_path = output_path_for(path, backend)

    if clean_cache:
        clear_cache(path)

    if not no_cache:
        decision = load_cache_record(path)
        if decision.status == "cache_corrupt":
            print("cache: corrupt record detected, revalidating")
        elif decision.record is not None:
            rec = decision.record
            if (
                rec.source_hash == source_hash
                and rec.ir_hash == ir_hash
                and rec.target == backend.target
                and rec.compiler_version == __version__
                and rec.verification_passed
                and Path(rec.output_path).exists()
            ):
                print(f"cache: hit ({backend.target})")
                print(f"emitted: {out_path}")
                return 0
            print("cache: miss (metadata changed)")
        else:
            print("cache: miss")

    result = verify(ir, emitted_code)
    _print_report(result, report)

    if not result.passed:
        print("compile failed: bridge preservation threshold not met")
        if not no_cache:
            save_cache_record(
                path,
                CacheRecord(
                    source_path=str(path.resolve()),
                    source_hash=source_hash,
                    ir_hash=ir_hash,
                    target=backend.target,
                    compiler_version=__version__,
                    output_path=str(out_path.resolve()),
                    verification_passed=False,
                    bridge_score=float(result.bridge_score),
                ),
            )
        return 1

    out_path.write_text(emitted_code, encoding="utf-8")
    print(f"emitted: {out_path}")

    if not no_cache:
        save_cache_record(
            path,
            CacheRecord(
                source_path=str(path.resolve()),
                source_hash=source_hash,
                ir_hash=ir_hash,
                target=backend.target,
                compiler_version=__version__,
                output_path=str(out_path.resolve()),
                verification_passed=True,
                bridge_score=float(result.bridge_score),
            ),
        )

    return 0


def _explain(path: Path) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    emitted_code, _ = emit_code(ir)
    result = verify(ir, emitted_code)
    print("AST:")
    print(ast)
    print("\nNormalized IR:")
    print(serialize_ir(ir))
    print("\nPreservation reasoning:")
    print(render_report(result))
    return 0


def _verify(path: Path, report: ReportMode) -> int:
    source = _load(path)
    ast = parse_source(source)
    ir = ast_to_ir(ast)
    emitted_code, _ = emit_code(ir)
    result = verify(ir, emitted_code)
    _print_report(result, report)
    return 0 if result.passed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibec", description="Vibe compiler prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    cp = sub.add_parser("compile", help="Compile a .vibe source file")
    cp.add_argument("path", type=Path)
    cp.add_argument("--report", choices=["human", "json"], default="human")
    cp.add_argument("--no-cache", action="store_true", help="Disable incremental cache for this compile")
    cp.add_argument("--clean-cache", action="store_true", help="Remove cache record before compiling")

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
        return _compile(args.path, args.report, no_cache=args.no_cache, clean_cache=args.clean_cache)
    if args.command == "explain":
        return _explain(args.path)
    if args.command == "verify":
        return _verify(args.path, args.report)

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
