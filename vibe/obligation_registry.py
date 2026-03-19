"""Controlled external obligation registration surface (Phase 4A)."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import re
from typing import Callable, Iterator

from .ir import IR

ObligationStatus = str


@dataclass(frozen=True, slots=True)
class ExternalObligation:
    obligation_id: str
    category: str
    description: str
    status: ObligationStatus
    source_location: str | None = None
    evidence: str | None = None
    critical: bool = False


@dataclass(frozen=True, slots=True)
class ExternalObligationContext:
    ir: IR
    generated_code: str
    observed_scalars: dict[str, float]
    observed_bools: dict[str, bool]
    observed_symbols: dict[str, str]


ExternalObligationProvider = Callable[[ExternalObligationContext], list[ExternalObligation]]


_CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_PROVIDERS: dict[str, ExternalObligationProvider] = {}


def register_external_obligation_provider(
    category: str,
    provider: ExternalObligationProvider,
    *,
    override: bool = False,
) -> None:
    cat = category.strip().lower()
    if not _CATEGORY_RE.fullmatch(cat):
        raise ValueError(
            f"invalid external obligation category `{category}`; use lowercase [a-z0-9_.-] and start with alnum"
        )
    if cat in _PROVIDERS and not override:
        raise ValueError(f"external obligation provider already registered for category `{cat}`")
    _PROVIDERS[cat] = provider


def unregister_external_obligation_provider(category: str) -> bool:
    return _PROVIDERS.pop(category.strip().lower(), None) is not None


def clear_external_obligation_providers() -> None:
    _PROVIDERS.clear()


def list_external_obligation_categories() -> list[str]:
    return sorted(_PROVIDERS.keys())


def evaluate_external_obligations(context: ExternalObligationContext) -> list[ExternalObligation]:
    rows: list[ExternalObligation] = []
    for category in list_external_obligation_categories():
        provider = _PROVIDERS[category]
        provided = provider(context)
        for row in provided:
            if row.category != category:
                raise ValueError(
                    f"external obligation category mismatch for `{category}`: provider emitted `{row.category}`"
                )
            rows.append(row)
    return rows


@contextmanager
def temporary_external_obligation_provider(
    category: str,
    provider: ExternalObligationProvider,
    *,
    override: bool = False,
) -> Iterator[None]:
    register_external_obligation_provider(category, provider, override=override)
    try:
        yield
    finally:
        unregister_external_obligation_provider(category)
