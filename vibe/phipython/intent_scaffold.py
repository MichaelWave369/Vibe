from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class IntentScaffoldMatch:
    template: str
    confidence: str
    matched_terms: tuple[str, ...]
    reason: str
    features: tuple[str, ...]


_TEMPLATE_HINTS: dict[str, tuple[str, ...]] = {
    "cli": ("cli", "command", "argument", "argparse", "greet"),
    "automation": ("automation", "batch", "rename", "folder", "filesystem"),
    "api_tool": ("api", "requests", "http", "endpoint", "json"),
    "scraper": ("scrape", "html", "beautifulsoup", "website", "crawl"),
    "flask_app": ("flask", "web app", "route", "server"),
    "dashboard": ("dashboard", "streamlit", "visual", "csv", "chart"),
}

_FEATURE_HINTS: dict[str, str] = {
    "requests": "requests",
    "json": "json_output",
    "csv": "csv_io",
    "env": "env_config",
}


def classify_intent_to_template(intent_text: str) -> IntentScaffoldMatch:
    """Classify bounded textual intent into a starter template."""

    norm = " ".join(intent_text.lower().split())
    scores: list[tuple[int, str, tuple[str, ...]]] = []
    for template, terms in _TEMPLATE_HINTS.items():
        matched = tuple(term for term in terms if term in norm)
        scores.append((len(matched), template, matched))
    scores.sort(key=lambda row: (-row[0], row[1]))

    top_score, top_template, matched_terms = scores[0]
    confidence = "high" if top_score >= 2 else "medium" if top_score == 1 else "low"
    features = tuple(sorted({feature for key, feature in _FEATURE_HINTS.items() if key in norm}))

    reason = (
        f"Selected `{top_template}` from keyword overlap: {', '.join(matched_terms) if matched_terms else 'no direct hits'}; "
        "low overlap defaults remain bounded starter guesses."
    )
    return IntentScaffoldMatch(
        template=top_template,
        confidence=confidence,
        matched_terms=matched_terms,
        reason=reason,
        features=features,
    )


def classify_intent_to_template_dict(intent_text: str) -> dict[str, object]:
    return asdict(classify_intent_to_template(intent_text))
