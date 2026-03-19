from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


@dataclass(slots=True)
class TextDocument:
    uri: str
    text: str
    version: int

    @property
    def path(self) -> Path | None:
        parsed = urlparse(self.uri)
        if parsed.scheme != "file":
            return None
        return Path(unquote(parsed.path))


class DocumentStore:
    def __init__(self) -> None:
        self._docs: dict[str, TextDocument] = {}

    def open(self, uri: str, text: str, version: int) -> TextDocument:
        doc = TextDocument(uri=uri, text=text, version=version)
        self._docs[uri] = doc
        return doc

    def update(self, uri: str, text: str, version: int) -> TextDocument:
        doc = TextDocument(uri=uri, text=text, version=version)
        self._docs[uri] = doc
        return doc

    def get(self, uri: str) -> TextDocument | None:
        return self._docs.get(uri)

    def close(self, uri: str) -> None:
        self._docs.pop(uri, None)

    def all_uris(self) -> list[str]:
        return sorted(self._docs.keys())
