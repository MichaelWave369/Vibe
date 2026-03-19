"""Phase 8.2 semantic versioning derived from intent diff."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re

from .diff import IntentDiffEntry, compute_intent_diff
from .ir import IR
from .manifest import load_manifest


_BUMP_ORDER = {"none": 0, "patch": 1, "minor": 2, "major": 3}


@dataclass(slots=True)
class SemverRationale:
    bump: str
    rule_id: str
    explanation: str
    category: str
    item: str
    change_type: str
    conservative: bool = False


@dataclass(slots=True)
class SemverDecision:
    bump: str
    confidence: str
    rationale: list[SemverRationale] = field(default_factory=list)
    ambiguity_notes: list[str] = field(default_factory=list)
    compared_paths: dict[str, str] = field(default_factory=dict)
    diff_summary: dict[str, int] = field(default_factory=dict)
    current_version: str | None = None
    recommended_next_version: str | None = None
    manifest_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "bump": self.bump,
            "confidence": self.confidence,
            "rationale": [asdict(r) for r in self.rationale],
            "ambiguity_notes": list(self.ambiguity_notes),
            "compared_paths": dict(self.compared_paths),
            "diff_summary": dict(self.diff_summary),
            "current_version": self.current_version,
            "recommended_next_version": self.recommended_next_version,
            "manifest_path": self.manifest_path,
        }


def _max_bump(a: str, b: str) -> str:
    return a if _BUMP_ORDER[a] >= _BUMP_ORDER[b] else b


def _parse_rule_expr(raw: object) -> tuple[str, float | str] | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    op, value = parts
    if op not in {"<", "<=", ">", ">=", "==", "!="}:
        return None
    try:
        return (op, float(value))
    except Exception:
        return (op, value)


def _preserve_modification_bump(entry: IntentDiffEntry) -> tuple[str, str, bool]:
    old_rule = _parse_rule_expr(entry.old_value)
    new_rule = _parse_rule_expr(entry.new_value)
    if old_rule is None or new_rule is None:
        if entry.semantic_effect == "broadened":
            return ("major", "preserve modification appears weakened (broadened)", True)
        if entry.semantic_effect == "narrowed":
            return ("minor", "preserve modification appears strengthened (narrowed)", True)
        return ("major", "preserve rule changed with ambiguous strength; using conservative major", True)

    old_op, old_v = old_rule
    new_op, new_v = new_rule
    if old_op == new_op and isinstance(old_v, float) and isinstance(new_v, float):
        if old_op in {">", ">="}:
            return (
                ("minor" if new_v > old_v else "major" if new_v < old_v else "patch"),
                "preserve threshold changed",
                False,
            )
        if old_op in {"<", "<="}:
            return (
                ("minor" if new_v < old_v else "major" if new_v > old_v else "patch"),
                "preserve threshold changed",
                False,
            )
        if old_op == "==":
            return ("minor" if old_v == new_v else "major", "preserve exact-match requirement changed", False)
    if entry.semantic_effect == "broadened":
        return ("major", "preserve modification is broader/weaker", True)
    if entry.semantic_effect == "narrowed":
        return ("minor", "preserve modification is narrower/stronger", True)
    return ("major", "preserve operator/value changed ambiguously; conservative major", True)


def _bridge_modified_bump(entry: IntentDiffEntry) -> tuple[str, str, bool]:
    if entry.semantic_effect == "broadened":
        return ("major", "bridge default weakened", False)
    if entry.semantic_effect == "narrowed":
        return ("minor", "bridge default strengthened", False)
    return ("patch", "bridge default changed without clear direction", True)


def classify_semver_change(entry: IntentDiffEntry) -> tuple[str, str, bool]:
    if entry.category == "output":
        if entry.change_type == "added":
            return ("minor", "added output field expands published contract", False)
        if entry.change_type == "removed":
            return ("major", "removed output field breaks published contract", False)
        return ("major", "output type/value changed", True)

    if entry.category == "preserve":
        if entry.change_type == "added":
            return ("minor", "added preserve rule strengthens guarantees", False)
        if entry.change_type == "removed":
            return ("major", "removed preserve rule weakens guarantees", False)
        if entry.change_type == "modified":
            return _preserve_modification_bump(entry)

    if entry.category == "constraint":
        if entry.change_type == "added":
            return ("minor", "added constraint narrows acceptable behavior", False)
        if entry.change_type == "removed":
            return ("major", "removed constraint broadens behavior", False)
        return ("major", "constraint changed in-place", True)

    if entry.category == "bridge":
        if entry.change_type == "modified":
            return _bridge_modified_bump(entry)
        if entry.change_type == "removed":
            return ("major", "bridge key removed", True)
        if entry.change_type == "added":
            return ("minor", "bridge key added", True)

    if entry.category == "emit" and entry.change_type == "target_changed":
        return ("major", "emit target changed; conservative compatibility break", True)

    if entry.category == "goal":
        return ("patch", "goal text changed (descriptive contract wording)", True)

    if entry.category in {"import", "module", "type", "enum", "interface", "vibe_version"}:
        return ("patch", "declaration-level metadata changed", True)

    if entry.category in {
        "hardware",
        "scientific_simulation",
        "legal_compliance",
        "genomics",
        "semantic_types",
        "effect_types",
        "resource_types",
        "inference_types",
        "agent_graph",
        "agent_boundary",
        "delegation",
        "runtime_monitor",
        "tesla_victory_layer",
        "agentora",
        "agentception",
    }:
        return ("patch", "derived/domain metadata changed; surfaced conservatively", True)

    return ("patch", "unclassified semantic change", True)


def derive_semver_from_diff(
    old_ir: IR,
    new_ir: IR,
    *,
    old_path: str | None = None,
    new_path: str | None = None,
    current_version: str | None = None,
    manifest_path: str | None = None,
) -> SemverDecision:
    diff = compute_intent_diff(old_ir, new_ir)
    bump = "none"
    ambiguity_notes: list[str] = []
    rationale: list[SemverRationale] = []

    for entry in diff.changes:
        entry_bump, explanation, conservative = classify_semver_change(entry)
        bump = _max_bump(bump, entry_bump)
        rationale.append(
            SemverRationale(
                bump=entry_bump,
                rule_id=f"semver.{entry.category}.{entry.change_type}",
                explanation=explanation,
                category=entry.category,
                item=entry.item,
                change_type=entry.change_type,
                conservative=conservative,
            )
        )
        if conservative:
            ambiguity_notes.append(
                f"{entry.category}:{entry.item} used conservative interpretation (`{entry.change_type}`)"
            )

    confidence = "high"
    if ambiguity_notes:
        confidence = "medium"
    if bump == "major" and ambiguity_notes:
        confidence = "low"

    next_version = bump_version(current_version, bump) if current_version else None
    return SemverDecision(
        bump=bump,
        confidence=confidence,
        rationale=sorted(rationale, key=lambda r: (r.bump, r.category, r.item)),
        ambiguity_notes=sorted(set(ambiguity_notes)),
        compared_paths={"old": old_path or "", "new": new_path or ""},
        diff_summary=dict(diff.summary),
        current_version=current_version,
        recommended_next_version=next_version,
        manifest_path=manifest_path,
    )


def parse_version(version: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"\s*(\d+)\.(\d+)\.(\d+)\s*", version)
    if not m:
        raise ValueError(f"invalid semantic version `{version}` (expected MAJOR.MINOR.PATCH)")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def bump_version(version: str | None, bump: str) -> str | None:
    if version is None:
        return None
    major, minor, patch = parse_version(version)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return f"{major}.{minor}.{patch}"


def current_version_from_manifest(path: Path) -> str:
    manifest = load_manifest(path)
    return manifest.package_version


def write_manifest_version(path: Path, new_version: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_package = False
    written = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_package = stripped == "[package]"
        if in_package and stripped.startswith("version"):
            out.append(f'version = "{new_version}"')
            written = True
            continue
        out.append(line)
    if not written:
        raise ValueError(f"manifest `{path}` has no package.version field")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def render_semver_human(decision: SemverDecision, *, show_rules: bool = False) -> str:
    lines = [
        "=== Vibe Semantic Version Recommendation (Phase 8.2) ===",
        f"old: {decision.compared_paths.get('old', '')}",
        f"new: {decision.compared_paths.get('new', '')}",
        f"recommended_bump: {decision.bump}",
        f"confidence: {decision.confidence}",
        f"diff_summary: {decision.diff_summary}",
    ]
    if decision.current_version:
        lines.append(f"current_version: {decision.current_version}")
    if decision.recommended_next_version:
        lines.append(f"recommended_next_version: {decision.recommended_next_version}")
    lines.append("rationale:")
    for row in decision.rationale:
        lines.append(f"- [{row.bump}] {row.category}:{row.item} :: {row.explanation}")
        if show_rules:
            lines.append(f"    rule_id: {row.rule_id}; conservative={row.conservative}")
    lines.append("ambiguity_notes:")
    if decision.ambiguity_notes:
        for note in decision.ambiguity_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- none")
    lines.append("truthfulness: deterministic rule-based semver with conservative handling for ambiguous semantic changes.")
    return "\n".join(lines)


def render_semver_json(decision: SemverDecision) -> str:
    return json.dumps(decision.to_dict(), indent=2, sort_keys=True)
