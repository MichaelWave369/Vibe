import json
from pathlib import Path

from vibe.cli import main
from vibe.manifest import VibeManifest, manifest_to_json, load_manifest
from vibe.package_manager import build_project, package_summary_json, resolve_package_graph


def _write_module(path: Path, *, imports: list[str] | None = None, bridge: str | None = None, emit: str | None = None, intent_name: str = "M") -> None:
    prelude = ""
    if imports:
        prelude = "\n".join(f"import {x}" for x in imports) + "\n\n"
    bridge_block = ""
    if bridge is not None:
        bridge_block = f"\nbridge:\n  measurement_safe_ratio = {bridge}\n"
    emit_line = f"\nemit {emit}\n" if emit else "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        prelude
        + f"intent {intent_name}:\n"
        + '  goal: "g"\n'
        + "  inputs:\n"
        + "    x: number\n"
        + "  outputs:\n"
        + "    y: number\n"
        + bridge_block
        + emit_line,
        encoding="utf-8",
    )


def test_manifest_serialization_deterministic() -> None:
    manifest = VibeManifest(
        package_name="pkg",
        package_version="0.1.0",
        bridge_defaults={"b": 2, "a": 1},
        emit_defaults={"default_target": "python"},
    )
    j1 = manifest_to_json(manifest)
    j2 = manifest_to_json(manifest)
    assert j1 == j2


def test_init_manifest_check_and_build_roundtrip(tmp_path: Path, capsys) -> None:
    root = tmp_path / "demo"
    assert main(["init", str(root)]) == 0
    assert (root / "vibe.toml").exists()
    assert (root / "src" / "main.vibe").exists()

    capsys.readouterr()
    assert main(["manifest-check", str(root), "--report", "json"]) == 0
    check_payload = json.loads(capsys.readouterr().out)
    assert check_payload["manifest"]["name"] == "my-intent-package"

    assert main(["build", str(root), "--report", "json"]) == 0
    build_payload = json.loads(capsys.readouterr().out)
    assert build_payload["package"]["name"] == "my-intent-package"
    assert build_payload["build_graph"]["reachable_modules"] >= 1


def test_build_with_local_import_and_dependency_resolution(tmp_path: Path, capsys) -> None:
    dep = tmp_path / "dep_pkg"
    main(["init", str(dep)])
    dep_manifest = dep / "vibe.toml"
    dep_manifest.write_text(
        dep_manifest.read_text(encoding="utf-8").replace('name = "my-intent-package"', 'name = "dep_pkg"'),
        encoding="utf-8",
    )
    _write_module(dep / "src" / "shared.vibe", intent_name="DepShared")

    root = tmp_path / "root_pkg"
    main(["init", str(root)])
    (root / "vibe.toml").write_text(
        """[package]
name = "root_pkg"
version = "0.1.0"

[bridge]
measurement_safe_ratio = 0.70
epsilon_floor = 0.03

[emit]
default_target = "typescript"

[dependencies]
dep_pkg = "path:../dep_pkg"
""",
        encoding="utf-8",
    )
    _write_module(root / "src" / "util.vibe", intent_name="Util")
    _write_module(root / "src" / "main.vibe", imports=["util", "dep_pkg.shared"], intent_name="Main")

    capsys.readouterr()
    assert main(["build", str(root), "--report", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    modules = {Path(m["module"]).name: m for m in payload["build_modules"]}
    assert "main.vibe" in modules
    assert "util.vibe" in modules
    assert any(Path(m["module"]).name == "shared.vibe" for m in payload["build_modules"])
    assert "dep_pkg" in payload["dependency_summary"]["resolved_local_dependencies"]


def test_dependency_cycle_detection(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    main(["init", str(a)])
    main(["init", str(b)])
    (a / "vibe.toml").write_text(
        """[package]
name = "a"
version = "0.1.0"

[dependencies]
b = "path:../b"
""",
        encoding="utf-8",
    )
    (b / "vibe.toml").write_text(
        """[package]
name = "b"
version = "0.1.0"

[dependencies]
a = "path:../a"
""",
        encoding="utf-8",
    )
    graph = resolve_package_graph(a / "vibe.toml")
    assert any(i["issue_id"] == "package_graph.cycle" for i in graph.issues)


def test_precedence_module_over_package_over_global(tmp_path: Path) -> None:
    root = tmp_path / "pkg"
    main(["init", str(root)])
    (root / "vibe.toml").write_text(
        """[package]
name = "pkg"
version = "0.1.0"

[bridge]
measurement_safe_ratio = 0.61

[emit]
default_target = "typescript"
""",
        encoding="utf-8",
    )
    _write_module(root / "src" / "main.vibe", imports=["secondary"], bridge="0.95", emit="python", intent_name="Main")
    _write_module(root / "src" / "secondary.vibe", intent_name="Secondary")

    payload = build_project(root / "vibe.toml")
    by_name = {Path(m["module"]).name: m for m in payload["build_modules"]}
    assert by_name["main.vibe"]["bridge_config_effective"]["measurement_safe_ratio"] == "0.95"
    assert by_name["main.vibe"]["emit_target"] == "python"
    assert by_name["secondary.vibe"]["bridge_config_effective"]["measurement_safe_ratio"] == "0.61"
    assert by_name["secondary.vibe"]["emit_target"] == "typescript"


def test_proof_and_build_json_deterministic_and_visible_package_metadata(tmp_path: Path, capsys) -> None:
    root = tmp_path / "proof_pkg"
    main(["init", str(root)])
    (root / "vibe.toml").write_text(
        """[package]
name = "proof_pkg"
version = "1.2.3"

[bridge]
measurement_safe_ratio = 0.72
""",
        encoding="utf-8",
    )

    capsys.readouterr()
    assert main(["verify", str(root / "src" / "main.vibe"), "--report", "json", "--write-proof"]) == 0
    out = capsys.readouterr().out
    verify_payload = json.loads(out.split("proof:")[0])
    assert verify_payload["package_context"]["package_name"] == "proof_pkg"

    proof = json.loads((root / "src" / "main.vibe.proof.json").read_text(encoding="utf-8"))
    assert proof["package_context"]["package_name"] == "proof_pkg"

    b1 = build_project(root / "vibe.toml")
    b2 = build_project(root / "vibe.toml")
    assert package_summary_json(b1) == package_summary_json(b2)


def test_manifest_check_reports_unresolved_dependency(tmp_path: Path) -> None:
    root = tmp_path / "broken"
    main(["init", str(root)])
    (root / "vibe.toml").write_text(
        """[package]
name = "broken"
version = "0.1.0"

[dependencies]
missing = "path:../missing_pkg"
""",
        encoding="utf-8",
    )
    manifest = load_manifest(root / "vibe.toml")
    assert manifest.package_name == "broken"
    payload = build_project(root / "vibe.toml")
    assert any(i["issue_id"].startswith("dependency.unresolved") for i in payload["dependency_graph"]["issues"])
