import json
from pathlib import Path

from vibe.cli import main


STDLIB_PACKAGES = [
    "stdlib/vibe_http",
    "stdlib/vibe_payment",
    "stdlib/vibe_vector",
    "stdlib/vibe_agent",
]


def _module_path(pkg_dir: str) -> Path:
    return Path(pkg_dir) / "src" / "main.vibe"


def test_stdlib_manifests_and_build_verify_flows(capsys) -> None:
    for pkg in STDLIB_PACKAGES:
        root = Path(pkg)
        assert (root / "vibe.toml").exists()
        assert _module_path(pkg).exists()

        assert main(["manifest-check", str(root), "--report", "json"]) == 0
        manifest_payload = json.loads(capsys.readouterr().out)
        assert manifest_payload["manifest"]["name"].startswith("vibe_")

        assert main(["build", str(root), "--report", "json"]) == 0
        build_payload = json.loads(capsys.readouterr().out)
        assert build_payload["package"]["name"].startswith("vibe_")

        assert main(["verify", str(_module_path(pkg)), "--report", "json"]) == 0
        verify_payload = json.loads(capsys.readouterr().out)
        assert verify_payload["passed"] is True


def test_stdlib_registry_publish_search_inspect_and_proof_visibility(tmp_path: Path, capsys) -> None:
    registry_root = tmp_path / "registry"
    pkg = Path("stdlib/vibe_http")
    module = _module_path(str(pkg))

    assert main(["verify-proof", str(module), "--report", "json"]) == 0
    _ = capsys.readouterr().out

    assert main(["publish", str(pkg), "--registry-root", str(registry_root), "--report", "json"]) == 0
    publish_payload = json.loads(capsys.readouterr().out)
    assert publish_payload["proof_status"] in {"complete", "partial", "absent"}

    assert main(["search", "http", "--registry-root", str(registry_root), "--report", "json"]) == 0
    search_payload = json.loads(capsys.readouterr().out)
    assert search_payload["result_count"] >= 1

    entry = str(publish_payload["entry_id"])
    assert main(["registry-inspect", entry, "--registry-root", str(registry_root), "--report", "json"]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert "proof" in inspect_payload
    assert "module_proofs" in inspect_payload["proof"]


def test_stdlib_compat_and_stdlib_list_determinism(tmp_path: Path, capsys) -> None:
    registry_root = tmp_path / "registry"
    for pkg in ["stdlib/vibe_http", "stdlib/vibe_agent"]:
        module = _module_path(pkg)
        assert main(["verify-proof", str(module), "--report", "json"]) == 0
        _ = capsys.readouterr().out
        assert main(["publish", pkg, "--registry-root", str(registry_root), "--report", "json"]) == 0
        _ = capsys.readouterr().out

    assert main(
        [
            "compat",
            "vibe_http@0.1.0",
            "vibe_agent@0.1.0",
            "--registry-root",
            str(registry_root),
            "--report",
            "json",
        ]
    ) == 0
    compat_payload = json.loads(capsys.readouterr().out)
    assert "compatibility_status" in compat_payload

    assert main(["stdlib-list", "--report", "json"]) == 0
    p1 = json.loads(capsys.readouterr().out)
    assert main(["stdlib-list", "--report", "json"]) == 0
    p2 = json.loads(capsys.readouterr().out)
    assert p1 == p2
