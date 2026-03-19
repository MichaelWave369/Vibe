"""Intent/emission structural correspondence (Phase 2.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from .ir import IR

CorrespondenceStatus = str


@dataclass(slots=True)
class CorrespondenceEntry:
    category: str
    source_item: str
    output_item: str | None
    status: CorrespondenceStatus
    drift_severity: str
    evidence: str
    target: str


@dataclass(slots=True)
class EquivalenceSummary:
    intent_items_total: int
    intent_items_matched: int
    intent_items_partial: int
    intent_items_missing: int
    intent_items_extra: int
    intent_items_unknown: int
    intent_equivalence_score: float
    drift_score: float
    mapping_notes: list[str] = field(default_factory=list)
    correspondences: list[CorrespondenceEntry] = field(default_factory=list)


@dataclass(slots=True)
class EmittedArtifact:
    target: str
    function_names: list[str] = field(default_factory=list)
    function_params: dict[str, list[str]] = field(default_factory=dict)
    exports: list[str] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)


def _snake_name(name: str) -> str:
    collapsed = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", collapsed).lower() or "generated_intent"


def _camel_name(name: str) -> str:
    safe = re.sub(r"[^0-9a-zA-Z]+", " ", name).strip()
    if not safe:
        return "generatedIntent"
    parts = safe.split()
    return parts[0].lower() + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def introspect_emitted_artifact(target: str, code: str) -> EmittedArtifact:
    target = target.lower()
    if target == "python":
        fn_matches = list(re.finditer(r"^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)", code, re.M))
        function_names = [m.group(1) for m in fn_matches]
        params = {
            m.group(1): [p.split(":", 1)[0].strip() for p in m.group(2).split(",") if p.strip()]
            for m in fn_matches
        }
        constants = re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", code, re.M)
        return EmittedArtifact(target=target, function_names=function_names, function_params=params, exports=list(function_names), constants=constants)

    if target == "typescript":
        fn_matches = list(re.finditer(r"export\s+function\s+([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)", code))
        function_names = [m.group(1) for m in fn_matches]
        params = {
            m.group(1): [p.split(":", 1)[0].strip() for p in m.group(2).split(",") if p.strip()]
            for m in fn_matches
        }
        exports = re.findall(r"export\s+(?:function|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)", code)
        constants = re.findall(r"export\s+const\s+([A-Z_][A-Z0-9_]*)", code)
        return EmittedArtifact(target=target, function_names=function_names, function_params=params, exports=exports, constants=constants)

    return EmittedArtifact(target=target)


def analyze_intent_equivalence(ir: IR, code: str) -> EquivalenceSummary:
    target = ir.emit_target.lower()
    artifact = introspect_emitted_artifact(target, code)
    rows: list[CorrespondenceEntry] = []
    notes = [
        "Structural correspondence only (not full behavioral equivalence)",
        f"Target-aware analysis: {target}",
    ]

    expected_fn = _snake_name(ir.intent_name) if target == "python" else _camel_name(ir.intent_name)
    if expected_fn in artifact.function_names:
        rows.append(CorrespondenceEntry("intent", f"intent.name:{ir.intent_name}", expected_fn, "matched", "low", "function name mapped", target))
    else:
        rows.append(CorrespondenceEntry("intent", f"intent.name:{ir.intent_name}", None, "missing_in_output", "high", "expected intent function missing", target))

    params = artifact.function_params.get(expected_fn, [])
    for name in ir.inputs:
        if name in params:
            rows.append(CorrespondenceEntry("intent", f"input:{name}", name, "matched", "low", "input parameter present", target))
        else:
            rows.append(CorrespondenceEntry("intent", f"input:{name}", None, "missing_in_output", "high", "declared input missing from signature", target))

    for out in ir.outputs:
        if out in code:
            rows.append(CorrespondenceEntry("intent", f"output:{out}", out, "matched", "low", "output anchor appears in emitted structure", target))
        elif ("processor" in out and "chosen_processor" in code.lower()) or ("fee" in out and "chosen_fee" in code.lower()):
            rows.append(CorrespondenceEntry("intent", f"output:{out}", None, "partially_matched", "medium", "mapped through heuristic alias", target))
        else:
            rows.append(CorrespondenceEntry("intent", f"output:{out}", None, "missing_in_output", "high", "declared output missing from emitted return structure", target))

    if ir.goal and ir.goal in code:
        rows.append(CorrespondenceEntry("intent", "goal", ir.goal, "matched", "low", "goal string preserved in doc/comment", target))
    elif ir.goal:
        rows.append(CorrespondenceEntry("intent", "goal", None, "partially_matched", "medium", "goal semantics present but string not exact", target))

    for key, op, value in ir.preserve_rules:
        if key in code and value in code:
            status = "partially_matched"
            evidence = "preserve appears as comment/metadata anchor"
        elif key in code or value in code:
            status = "partially_matched"
            evidence = "partial preserve anchor found"
        else:
            status = "unknown"
            evidence = "no deterministic preserve anchor for target"
        rows.append(CorrespondenceEntry("preserve", f"{key} {op} {value}", None, status, "medium", evidence, target))

    for c in ir.constraints:
        if c in code:
            rows.append(CorrespondenceEntry("constraint", c, c, "matched", "low", "constraint text present", target))
        else:
            rows.append(CorrespondenceEntry("constraint", c, None, "unknown", "medium", "constraint not directly represented structurally", target))

    for k, v in ir.bridge_config.items():
        if target == "typescript" and "BRIDGE_CONFIG" in code and k in code and str(v) in code:
            status = "matched"
            evidence = "bridge config emitted as exported const"
        elif target == "python" and (k in code or str(v) in code):
            status = "partially_matched"
            evidence = "bridge anchor appears indirectly"
        else:
            status = "missing_in_output" if target == "python" else "unknown"
            evidence = "bridge config not structurally represented"
        rows.append(CorrespondenceEntry("bridge", f"{k}={v}", None, status, "medium", evidence, target))

    if ir.tesla_victory_layer:
        status = "matched" if "TESLA_VICTORY_LAYER" in code else "missing_in_output"
        rows.append(CorrespondenceEntry("experimental", "tesla_victory_layer", "TESLA_VICTORY_LAYER", status, "high" if status != "matched" else "low", "tesla block mapping", target))
    if ir.agentora_config.get("enabled"):
        status = "matched" if "AGENTORA_CONFIG" in code else "missing_in_output"
        rows.append(CorrespondenceEntry("experimental", "agentora", "AGENTORA_CONFIG", status, "high" if status != "matched" else "low", "agentora config mapping", target))
    if ir.agentception_config:
        status = "matched" if "AGENTCEPTION_CONFIG" in code else "missing_in_output"
        rows.append(CorrespondenceEntry("experimental", "agentception", "AGENTCEPTION_CONFIG", status, "high" if status != "matched" else "low", "agentception config mapping", target))

    expected_consts = {"TESLA_VICTORY_LAYER", "AGENTORA_CONFIG", "AGENT_DEFINITIONS", "AGENTCEPTION_CONFIG", "BRIDGE_CONFIG"}
    for const_name in artifact.constants:
        if const_name not in expected_consts:
            rows.append(CorrespondenceEntry("extra", "<none>", const_name, "extra_in_output", "low", "extra helper/config constant emitted", target))

    totals = {
        "matched": sum(1 for r in rows if r.status == "matched"),
        "partially_matched": sum(1 for r in rows if r.status == "partially_matched"),
        "missing_in_output": sum(1 for r in rows if r.status == "missing_in_output"),
        "extra_in_output": sum(1 for r in rows if r.status == "extra_in_output"),
        "unknown": sum(1 for r in rows if r.status == "unknown"),
    }
    total = max(1, len(rows))
    equivalence = (totals["matched"] + 0.5 * totals["partially_matched"]) / total
    drift = (totals["missing_in_output"] + totals["extra_in_output"] + 0.5 * totals["partially_matched"] + 0.5 * totals["unknown"]) / total

    return EquivalenceSummary(
        intent_items_total=total,
        intent_items_matched=totals["matched"],
        intent_items_partial=totals["partially_matched"],
        intent_items_missing=totals["missing_in_output"],
        intent_items_extra=totals["extra_in_output"],
        intent_items_unknown=totals["unknown"],
        intent_equivalence_score=round(equivalence, 6),
        drift_score=round(drift, 6),
        mapping_notes=notes,
        correspondences=rows,
    )
