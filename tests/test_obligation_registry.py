import json
from pathlib import Path

from vibe.cli import main
from vibe.extensions.demo_obligations import DEMO_OBLIGATION_CATEGORY, register_demo_obligation_provider
from vibe.obligation_registry import (
    ExternalObligation,
    ExternalObligationContext,
    clear_external_obligation_providers,
    list_external_obligation_categories,
    register_external_obligation_provider,
    temporary_external_obligation_provider,
)


def _spec_with_demo_constraint() -> str:
    return """
intent ExtDemo:
  goal: "external obligation seam"
  inputs:
    x: number
  outputs:
    y: number
constraint:
  demo.require_audit_log = true
emit python
"""


def test_registry_registration_success_and_listing() -> None:
    clear_external_obligation_providers()

    def _provider(_: ExternalObligationContext) -> list[ExternalObligation]:
        return []

    register_external_obligation_provider("demo.registration", _provider)
    assert list_external_obligation_categories() == ["demo.registration"]
    clear_external_obligation_providers()


def test_registry_duplicate_registration_rejected() -> None:
    clear_external_obligation_providers()

    def _provider(_: ExternalObligationContext) -> list[ExternalObligation]:
        return []

    register_external_obligation_provider("demo.dup", _provider)
    try:
        register_external_obligation_provider("demo.dup", _provider)
        assert False, "expected duplicate registration to raise"
    except ValueError as exc:
        assert "already registered" in str(exc)
    finally:
        clear_external_obligation_providers()


def test_external_obligation_executes_in_verify_flow(tmp_path: Path, capsys) -> None:
    clear_external_obligation_providers()
    register_demo_obligation_provider()

    case = tmp_path / "ext.vibe"
    case.write_text(_spec_with_demo_constraint(), encoding="utf-8")
    assert main(["verify", str(case), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    row = next(o for o in payload["obligations"] if o["category"] == DEMO_OBLIGATION_CATEGORY)
    assert row["id"] == "external.demo.audit_log_present"
    assert row["status"] in {"satisfied", "violated"}
    clear_external_obligation_providers()


def test_external_obligation_appears_in_verify_json(tmp_path: Path, capsys) -> None:
    clear_external_obligation_providers()
    register_demo_obligation_provider()
    case = tmp_path / "ext.vibe"
    case.write_text(_spec_with_demo_constraint(), encoding="utf-8")

    assert main(["verify", str(case), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    row = next(o for o in payload["obligations"] if o["category"] == DEMO_OBLIGATION_CATEGORY)
    expected = json.loads(Path("tests/fixtures/obligation_registry/verify_external_obligation.json").read_text(encoding="utf-8"))
    assert {k: row[k] for k in ["id", "category", "status", "severity"]} == expected
    clear_external_obligation_providers()


def test_external_obligation_appears_in_proof_artifact(tmp_path: Path, capsys) -> None:
    clear_external_obligation_providers()
    register_demo_obligation_provider()
    case = tmp_path / "ext.vibe"
    case.write_text(_spec_with_demo_constraint(), encoding="utf-8")

    assert main(["verify", str(case), "--write-proof", "--report", "json"]) in {0, 1}
    capsys.readouterr()
    payload = json.loads(case.with_suffix(".vibe.proof.json").read_text(encoding="utf-8"))
    assert any(o["category"] == DEMO_OBLIGATION_CATEGORY for o in payload["obligations"])
    clear_external_obligation_providers()


def test_base_verify_unchanged_without_extensions(tmp_path: Path, capsys) -> None:
    clear_external_obligation_providers()
    case = tmp_path / "base.vibe"
    case.write_text(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["verify", str(case), "--report", "json"]) in {0, 1}
    baseline = json.loads(capsys.readouterr().out)
    assert main(["verify", str(case), "--report", "json"]) in {0, 1}
    again = json.loads(capsys.readouterr().out)
    assert baseline["obligations_total"] == again["obligations_total"]


def test_external_obligation_ordering_is_deterministic(tmp_path: Path, capsys) -> None:
    clear_external_obligation_providers()
    case = tmp_path / "base.vibe"
    case.write_text(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"), encoding="utf-8")

    def _z_provider(_: ExternalObligationContext) -> list[ExternalObligation]:
        return [
            ExternalObligation(
                obligation_id="external.z.1",
                category="demo.z",
                description="z",
                status="satisfied",
            )
        ]

    def _a_provider(_: ExternalObligationContext) -> list[ExternalObligation]:
        return [
            ExternalObligation(
                obligation_id="external.a.1",
                category="demo.a",
                description="a",
                status="satisfied",
            )
        ]

    with temporary_external_obligation_provider("demo.z", _z_provider):
        with temporary_external_obligation_provider("demo.a", _a_provider):
            assert main(["verify", str(case), "--report", "json"]) in {0, 1}
            payload = json.loads(capsys.readouterr().out)
            ext = [o for o in payload["obligations"] if str(o["category"]).startswith("demo.")]
            assert [o["category"] for o in ext] == ["demo.a", "demo.z"]

    clear_external_obligation_providers()
