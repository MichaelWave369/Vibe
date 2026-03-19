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
    assert payload["external_obligation_providers"]
    diag = payload["external_obligation_providers"][0]
    assert diag["category"] == DEMO_OBLIGATION_CATEGORY
    assert diag["provider_name"] == "demo_audit_obligation_provider"
    assert diag["provider_version"] == "v1"
    assert diag["ran"] is True
    assert diag["emitted_obligations"] == 1
    assert diag["had_error"] is False
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
    expected_diag = json.loads(Path("tests/fixtures/obligation_registry/provider_execution_success.json").read_text(encoding="utf-8"))
    assert payload["external_obligation_providers"] == [expected_diag]
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
    assert payload["external_obligation_providers"][0]["category"] == DEMO_OBLIGATION_CATEGORY
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
    assert baseline["external_obligation_providers"] == []
    assert again["external_obligation_providers"] == []


def test_provider_exception_exposed_as_diagnostics(tmp_path: Path, capsys) -> None:
    clear_external_obligation_providers()
    case = tmp_path / "base.vibe"
    case.write_text(Path("vibe/examples/payment_router.vibe").read_text(encoding="utf-8"), encoding="utf-8")

    def _bad_provider(_: ExternalObligationContext) -> list[ExternalObligation]:
        raise RuntimeError("deterministic test failure")

    register_external_obligation_provider("demo.bad", _bad_provider, provider_name="bad_provider", provider_version="v0")
    assert main(["verify", str(case), "--report", "json"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)

    diag = payload["external_obligation_providers"][0]
    assert diag["category"] == "demo.bad"
    assert diag["provider_name"] == "bad_provider"
    assert diag["provider_version"] == "v0"
    assert diag["had_error"] is True
    assert diag["error_type"] == "RuntimeError"
    assert "deterministic test failure" in str(diag["error_message"])
    row = next(o for o in payload["obligations"] if o["id"] == "external.demo.bad.provider_error")
    assert row["status"] == "unknown"
    clear_external_obligation_providers()


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
            diags = payload["external_obligation_providers"]
            assert [d["category"] for d in diags] == ["demo.a", "demo.z"]
            assert [d["order_index"] for d in diags] == [1, 2]

    clear_external_obligation_providers()
