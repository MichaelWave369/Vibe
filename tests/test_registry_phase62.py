import json
from pathlib import Path

from vibe.cli import main
from vibe.registry import create_registry_entry, search_local_registry


def _write_manifest(path: Path, *, name: str, version: str, description: str, tags: list[str], domain: str) -> None:
    path.write_text(
        f'''[package]
name = "{name}"
version = "{version}"
description = "{description}"

[bridge]
measurement_safe_ratio = 0.80
epsilon_floor = 0.02

[emit]
default_target = "python"

[metadata]
domain = "{domain}"
tags = {json.dumps(tags)}
''',
        encoding="utf-8",
    )


def _init_pkg(root: Path, *, name: str, version: str, description: str, tags: list[str], domain: str) -> Path:
    assert main(["init", str(root)]) == 0
    _write_manifest(root / "vibe.toml", name=name, version=version, description=description, tags=tags, domain=domain)
    return root


def test_registry_entry_creation_and_determinism(tmp_path: Path) -> None:
    pkg = _init_pkg(
        tmp_path / "pay_core",
        name="pay-core",
        version="1.2.0",
        description="payment routing core",
        tags=["payments", "routing"],
        domain="fintech",
    )

    e1 = create_registry_entry(pkg)
    e2 = create_registry_entry(pkg)
    assert json.dumps(e1, sort_keys=True) == json.dumps(e2, sort_keys=True)
    assert e1["package"]["name"] == "pay-core"
    assert e1["proof"]["proof_status"] == "absent"


def test_publish_search_inspect_compat_and_json_outputs(tmp_path: Path, capsys) -> None:
    registry_root = tmp_path / ".vibe_registry"

    pay = _init_pkg(
        tmp_path / "pay_router",
        name="pay-router",
        version="1.0.0",
        description="payment routing package",
        tags=["payments", "routing"],
        domain="fintech",
    )
    alt = _init_pkg(
        tmp_path / "pay_router_alt",
        name="pay-router",
        version="1.1.0",
        description="payment routing package updated",
        tags=["payments", "routing"],
        domain="fintech",
    )

    # Write a proof artifact for one package module to ensure proof metadata inclusion.
    assert main(["verify", str(pay / "src" / "main.vibe"), "--write-proof", "--report", "json"]) == 0
    capsys.readouterr()

    assert main(["publish", str(pay), "--registry-root", str(registry_root), "--report", "json"]) == 0
    p1 = json.loads(capsys.readouterr().out)
    assert p1["entry_id"] == "pay-router@1.0.0"

    assert main(["publish", str(alt), "--registry-root", str(registry_root), "--report", "json"]) == 0
    p2 = json.loads(capsys.readouterr().out)
    assert p2["entry_id"] == "pay-router@1.1.0"

    # Search: deterministic and queryable.
    assert main(["search", "payment routing", "--registry-root", str(registry_root), "--report", "json"]) == 0
    search_payload = json.loads(capsys.readouterr().out)
    assert search_payload["result_count"] == 2
    assert [r["entry_id"] for r in search_payload["results"]] == ["pay-router@1.0.0", "pay-router@1.1.0"]

    # Search with filter.
    filtered = search_local_registry(
        "payment",
        tag_filters=["routing"],
        domain_filter="fintech",
        registry_root=registry_root,
    )
    assert filtered["result_count"] == 2

    # Inspect latest by name.
    assert main(["registry-inspect", "pay-router", "--registry-root", str(registry_root), "--report", "json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["package"]["version"] == "1.1.0"
    assert inspect_payload["proof"]["proof_status"] == "absent"

    # Inspect explicit version with proof present.
    assert main(["registry-inspect", "pay-router@1.0.0", "--registry-root", str(registry_root), "--report", "json"]) == 0
    inspect_old = json.loads(capsys.readouterr().out)
    assert inspect_old["proof"]["proof_status"] in {"complete", "partial"}
    assert inspect_old["proof"]["proof_artifacts_present"] >= 1

    # Compatibility hints.
    assert main([
        "compat",
        "pay-router@1.0.0",
        "pay-router@1.1.0",
        "--registry-root",
        str(registry_root),
        "--report",
        "json",
    ]) == 0
    compat_payload = json.loads(capsys.readouterr().out)
    assert compat_payload["analysis_type"] == "phase-6.2 compatibility hints"
    assert compat_payload["semver"]["major_compatible"] is True
    assert compat_payload["compatibility_status"] in {"review-required", "insufficient-proof", "likely-compatible"}


def test_publish_fails_with_blocking_issues(tmp_path: Path, capsys) -> None:
    broken = _init_pkg(
        tmp_path / "broken",
        name="broken-pkg",
        version="0.1.0",
        description="broken package",
        tags=["broken"],
        domain="test",
    )
    # create unresolved import so build has blocking issue
    (broken / "src" / "main.vibe").write_text(
        """import missing.module

intent Broken:
  goal: "x"
  inputs:
    a: number
  outputs:
    b: number

emit python
""",
        encoding="utf-8",
    )

    rc = main(["publish", str(broken), "--registry-root", str(tmp_path / ".vibe_registry")])
    assert rc == 1
    assert "publish failed:" in capsys.readouterr().out
