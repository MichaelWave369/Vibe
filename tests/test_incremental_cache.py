import json
from pathlib import Path

from vibe.cli import main
from vibe.cache import cache_record_path, sha256_text


def test_cache_hit_on_repeated_compile(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["compile", str(case)]) == 0
    first = capsys.readouterr().out
    assert "cache: miss" in first

    assert main(["compile", str(case)]) == 0
    second = capsys.readouterr().out
    assert "cache: hit" in second


def test_cache_miss_when_source_changes(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["compile", str(case)]) == 0
    capsys.readouterr()

    case.write_text(case.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    assert main(["compile", str(case)]) == 0
    out = capsys.readouterr().out
    assert "cache: miss" in out


def test_cache_miss_when_target_changes(capsys, tmp_path) -> None:
    py_src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "switch_target.vibe"
    case.write_text(py_src.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["compile", str(case)]) == 0
    capsys.readouterr()

    case.write_text(case.read_text(encoding="utf-8").replace("emit python", "emit typescript"), encoding="utf-8")
    assert main(["compile", str(case)]) == 0
    out = capsys.readouterr().out
    assert "cache: miss" in out
    assert case.with_suffix(".ts").exists()


def test_corrupted_cache_fallback(capsys, tmp_path) -> None:
    src = Path("vibe/examples/payment_router.vibe")
    case = tmp_path / "payment_router.vibe"
    case.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["compile", str(case)]) == 0
    capsys.readouterr()

    cache_file = cache_record_path(case)
    cache_file.write_text("{ bad json", encoding="utf-8")

    assert main(["compile", str(case)]) == 0
    out = capsys.readouterr().out
    assert "cache: corrupt record detected" in out


def test_failed_verification_not_treated_as_success_cache(capsys, tmp_path) -> None:
    bad = """
intent HardFail:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number
bridge:
  epsilon_floor = 0.7
  measurement_safe_ratio = 1.2
emit python
"""
    case = tmp_path / "hard_fail.vibe"
    case.write_text(bad, encoding="utf-8")

    assert main(["compile", str(case)]) == 1
    capsys.readouterr()
    assert main(["compile", str(case)]) == 1
    out = capsys.readouterr().out
    assert "cache: miss" in out or "cache: miss (metadata changed)" in out


def test_cache_key_material_is_deterministic() -> None:
    sample = "abc"
    assert sha256_text(sample) == sha256_text(sample)
