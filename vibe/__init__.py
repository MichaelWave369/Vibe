"""Vibe compiler package."""

from ._version import __version__
from .cli import main
from .obligation_registry import (
    list_external_obligation_categories,
    register_external_obligation_provider,
    unregister_external_obligation_provider,
)

__all__ = [
    "__version__",
    "main",
    "register_external_obligation_provider",
    "unregister_external_obligation_provider",
    "list_external_obligation_categories",
]
