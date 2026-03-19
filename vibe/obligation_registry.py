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


@dataclass(frozen=True, slots=True)
class ExternalObligationProviderRegistration:
    category: str
    provider: ExternalObligationProvider
    provider_name: str
    provider_version: str | None


@dataclass(frozen=True, slots=True)
class ExternalObligationProviderExecution:
    category: str
    provider_name: str
    provider_version: str | None
    order_index: int
    ran: bool
    emitted_obligations: int
    status_counts: dict[str, int]
    had_error: bool
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class ExternalObligationEvaluationResult:
    obligations: list[ExternalObligation]
    executions: list[ExternalObligationProviderExecution]


_PROVIDERS: dict[str, ExternalObligationProviderRegistration] = {}


def register_external_obligation_provider(
    category: str,
    provider: ExternalObligationProvider,
    *,
    override: bool = False,
    provider_name: str | None = None,
    provider_version: str | None = None,
) -> None:
    cat = category.strip().lower()
    if not _CATEGORY_RE.fullmatch(cat):
        raise ValueError(
            f"invalid external obligation category `{category}`; use lowercase [a-z0-9_.-] and start with alnum"
        )
    if cat in _PROVIDERS and not override:
        raise ValueError(f"external obligation provider already registered for category `{cat}`")
    _PROVIDERS[cat] = ExternalObligationProviderRegistration(
        category=cat,
        provider=provider,
        provider_name=provider_name or getattr(provider, "__name__", "external_provider"),
        provider_version=provider_version,
    )


def unregister_external_obligation_provider(category: str) -> bool:
    return _PROVIDERS.pop(category.strip().lower(), None) is not None


def clear_external_obligation_providers() -> None:
    _PROVIDERS.clear()


def list_external_obligation_categories() -> list[str]:
    return sorted(_PROVIDERS.keys())


def evaluate_external_obligations(context: ExternalObligationContext) -> ExternalObligationEvaluationResult:
    rows: list[ExternalObligation] = []
    executions: list[ExternalObligationProviderExecution] = []
    for order_index, category in enumerate(list_external_obligation_categories(), start=1):
        registration = _PROVIDERS[category]
        try:
            provided = registration.provider(context)
            status_counts: dict[str, int] = {}
            valid_rows: list[ExternalObligation] = []
            for row in provided:
                if row.category != category:
                    raise ValueError(
                        f"external obligation category mismatch for `{category}`: provider emitted `{row.category}`"
                    )
                status_counts[row.status] = status_counts.get(row.status, 0) + 1
                valid_rows.append(row)
            rows.extend(valid_rows)
            executions.append(
                ExternalObligationProviderExecution(
                    category=category,
                    provider_name=registration.provider_name,
                    provider_version=registration.provider_version,
                    order_index=order_index,
                    ran=True,
                    emitted_obligations=len(valid_rows),
                    status_counts=status_counts,
                    had_error=False,
                    error_type=None,
                    error_message=None,
                )
            )
        except Exception as exc:
            executions.append(
                ExternalObligationProviderExecution(
                    category=category,
                    provider_name=registration.provider_name,
                    provider_version=registration.provider_version,
                    order_index=order_index,
                    ran=True,
                    emitted_obligations=0,
                    status_counts={},
                    had_error=True,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                )
            )
            rows.append(
                ExternalObligation(
                    obligation_id=f"external.{category}.provider_error",
                    category=category,
                    description="External obligation provider execution failed",
                    status="unknown",
                    source_location=None,
                    evidence=f"{exc.__class__.__name__}: {exc}",
                    critical=False,
                )
            )
    return ExternalObligationEvaluationResult(obligations=rows, executions=executions)


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
