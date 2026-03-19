"""Runtime monitor metadata + deterministic event evaluation (Phase 5.4)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import prod
from pathlib import Path
import json

from .ir import IR


EVENT_TYPES = {
    "agent_invocation_started",
    "agent_invocation_finished",
    "edge_transfer_observed",
    "fallback_triggered",
    "alert_triggered",
    "intent_drift_detected",
}


@dataclass(slots=True)
class RuntimeMonitorConfig:
    pipeline_name: str
    monitored_agents: list[str]
    monitored_edges: list[dict[str, object]]
    bridge_threshold: float
    critical_boundaries: list[str]
    fallback_policy: dict[str, object]
    alert_policy: dict[str, object]
    delegation_watch: dict[str, object]
    threshold_summary: dict[str, object]
    drift_rules: list[str]
    otel_mapping_notes: list[str]


def _parse_latency_threshold_ms(ir: IR) -> float | None:
    for key, op, value in ir.preserve_rules:
        k = key.lower()
        if "latency" in k and "ms" in value and op in {"<", "<=", "="}:
            try:
                return float(value.lower().replace("ms", "").strip())
            except Exception:
                return None
    return None


def build_runtime_monitor_config(ir: IR) -> RuntimeMonitorConfig:
    graph = ir.module.agent_graph_summary
    boundary = ir.module.agent_boundary_summary
    delegation = ir.module.delegation_summary

    agents = sorted(graph.get("agents", {}).keys())
    edges = list(boundary.get("edge_summaries", []))
    threshold = float(ir.bridge_config.get("measurement_safe_ratio", "0.85"))
    latency_ms = _parse_latency_threshold_ms(ir)

    return RuntimeMonitorConfig(
        pipeline_name=str(graph.get("graph_name") or ir.intent_name),
        monitored_agents=agents,
        monitored_edges=edges,
        bridge_threshold=threshold,
        critical_boundaries=list(boundary.get("critical_boundary_failures", [])),
        fallback_policy={"max_fallback_ratio": 0.30, "recommendation": "inspect upstream agent health + boundary contracts"},
        alert_policy={"bridge_threshold": threshold, "min_pipeline_runtime_score": threshold},
        delegation_watch={
            "edge_count": int(delegation.get("recursion_metadata", {}).get("edge_count", 0)),
            "missing_stop_edges": list(delegation.get("recursion_metadata", {}).get("missing_stop_edges", [])),
            "has_cycle": bool(delegation.get("recursion_metadata", {}).get("has_cycle", False)),
            "declared_edges": list(delegation.get("delegation_tree", [])),
        },
        threshold_summary={
            "measurement_safe_ratio": threshold,
            "latency_ms": latency_ms,
            "pipeline_bridge_score_compile_time": float(boundary.get("pipeline_bridge_score", 1.0)),
        },
        drift_rules=[
            "latency threshold exceeded repeatedly",
            "edge transfer observed type/category mismatch",
            "fallback frequency above tolerance",
            "deterministic agent output instability",
            "delegation depth exceeds static budget",
            "runtime edge bridge score below threshold",
        ],
        otel_mapping_notes=[
            "event_type -> span/event name",
            "pipeline/agent/edge -> span attributes",
            "metrics (latency_ms, edge_bridge_score) -> event attributes",
            "drift/alert/fallback signals -> log/event annotations",
        ],
    )


def monitor_config_payload(ir: IR) -> dict[str, object]:
    return asdict(build_runtime_monitor_config(ir))


def load_runtime_events(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "events" in payload:
        payload = payload["events"]
    if not isinstance(payload, list):
        raise ValueError("runtime events payload must be a list or {\"events\": [...]}")
    return [dict(e) for e in payload]


def evaluate_runtime_events(config: dict[str, object], events: list[dict[str, object]]) -> dict[str, object]:
    monitored_agents = set(config.get("monitored_agents", []))
    edge_expect = {str(e.get("edge")): str(e.get("downstream_receives", "")) for e in config.get("monitored_edges", [])}
    bridge_threshold = float(config.get("bridge_threshold", 0.85))
    latency_threshold = config.get("threshold_summary", {}).get("latency_ms")
    fallback_ratio_limit = float(config.get("fallback_policy", {}).get("max_fallback_ratio", 0.3))
    delegation_edges = config.get("delegation_watch", {}).get("declared_edges", [])
    max_depth_map = {str(e.get("edge")): e.get("max_depth") for e in delegation_edges}

    agent_scores = {a: 1.0 for a in monitored_agents}
    edge_scores = {e: 1.0 for e in edge_expect}
    outcome_signatures: dict[str, set[str]] = {}

    drift_signals: list[dict[str, object]] = []
    alerts: list[str] = []
    fallback_count = 0
    latency_exceed = 0
    valid_events = 0

    for idx, ev in enumerate(events, start=1):
        et = str(ev.get("event_type", ""))
        if et not in EVENT_TYPES:
            drift_signals.append({"event_index": idx, "type": "unknown_event_type", "severity": "medium", "evidence": et})
            continue
        valid_events += 1

        agent = str(ev.get("agent_name", ""))
        edge = str(ev.get("edge_name", ""))
        if et == "agent_invocation_finished":
            latency = ev.get("latency_ms")
            if latency_threshold is not None and isinstance(latency, (int, float)) and latency > float(latency_threshold):
                latency_exceed += 1
                if agent in agent_scores:
                    agent_scores[agent] = max(0.0, round(agent_scores[agent] - 0.1, 6))
            sig = str(ev.get("result_signature", ""))
            if sig:
                outcome_signatures.setdefault(agent, set()).add(sig)

        if et == "edge_transfer_observed":
            observed = str(ev.get("observed_type", ""))
            expected = edge_expect.get(edge, "")
            runtime_edge_score = ev.get("edge_bridge_score")
            if expected and observed and observed != expected:
                drift_signals.append(
                    {"event_index": idx, "type": "boundary_shape_mismatch", "severity": "high", "edge": edge, "evidence": f"observed={observed}, expected={expected}"}
                )
                if edge in edge_scores:
                    edge_scores[edge] = max(0.0, round(edge_scores[edge] - 0.4, 6))
            if isinstance(runtime_edge_score, (int, float)) and runtime_edge_score < bridge_threshold:
                drift_signals.append(
                    {"event_index": idx, "type": "runtime_edge_bridge_drop", "severity": "high", "edge": edge, "evidence": f"score={runtime_edge_score}, threshold={bridge_threshold}"}
                )
                if edge in edge_scores:
                    edge_scores[edge] = max(0.0, round(min(edge_scores[edge], float(runtime_edge_score)), 6))

        if et == "fallback_triggered":
            fallback_count += 1

        if et == "intent_drift_detected":
            drift_signals.append(
                {"event_index": idx, "type": "explicit_intent_drift", "severity": "high", "agent": agent or None, "evidence": str(ev.get("details", "runtime drift flag"))}
            )
            if agent in agent_scores:
                agent_scores[agent] = max(0.0, round(agent_scores[agent] - 0.25, 6))

        if et == "alert_triggered":
            alerts.append(str(ev.get("alert_code", "runtime_alert")))

        depth = ev.get("delegation_depth")
        if isinstance(depth, int) and edge in max_depth_map and isinstance(max_depth_map[edge], int) and depth > int(max_depth_map[edge]):
            drift_signals.append(
                {"event_index": idx, "type": "delegation_depth_exceeded", "severity": "high", "edge": edge, "evidence": f"depth={depth}, max_depth={max_depth_map[edge]}"}
            )

    for agent, sigs in sorted(outcome_signatures.items()):
        if len(sigs) > 1:
            drift_signals.append(
                {"type": "deterministic_instability", "severity": "high", "agent": agent, "evidence": f"distinct_signatures={sorted(sigs)}"}
            )
            if agent in agent_scores:
                agent_scores[agent] = max(0.0, round(agent_scores[agent] - 0.2, 6))

    fallback_ratio = (fallback_count / valid_events) if valid_events else 0.0
    if fallback_ratio > fallback_ratio_limit:
        drift_signals.append(
            {"type": "fallback_overuse", "severity": "high", "evidence": f"ratio={round(fallback_ratio, 6)}, limit={fallback_ratio_limit}"}
        )

    if latency_threshold is not None and latency_exceed >= 2:
        drift_signals.append(
            {"type": "latency_threshold_drop", "severity": "high", "evidence": f"exceed_count={latency_exceed}, threshold_ms={latency_threshold}"}
        )

    pipeline_runtime_score = round(prod(edge_scores.values()), 6) if edge_scores else round(sum(agent_scores.values()) / max(1, len(agent_scores)), 6)
    if pipeline_runtime_score < bridge_threshold:
        alerts.append("runtime_pipeline_bridge_below_threshold")

    return {
        "events_processed": valid_events,
        "agent_runtime_scores": dict(sorted(agent_scores.items())),
        "edge_runtime_scores": dict(sorted(edge_scores.items())),
        "pipeline_runtime_score": pipeline_runtime_score,
        "bridge_threshold": bridge_threshold,
        "drift_signals": drift_signals,
        "alert_recommendations": sorted(set(alerts)),
        "fallback_recommendation": (
            "fallback_overuse_detected" if fallback_ratio > fallback_ratio_limit else "fallback_within_policy"
        ),
        "fallback_ratio": round(fallback_ratio, 6),
        "notes": [
            "Runtime evaluation is observational and does not rewrite compile-time proof.",
            "Scoring is deterministic over supplied event payloads.",
        ],
    }
