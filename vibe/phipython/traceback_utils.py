from __future__ import annotations

import re
from dataclasses import dataclass, asdict


_FILE_LINE_RE = re.compile(r'  File "(?P<path>.+?)", line (?P<line>\d+), in (?P<func>.+)')
_EXCEPTION_RE = re.compile(r"(?P<exc>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):\s*(?P<msg>.*)")


@dataclass(frozen=True, slots=True)
class TracebackSummary:
    exception_type: str
    message: str
    file_path: str | None
    line_number: int | None
    code_context: str | None
    heuristic_note: str


def parse_traceback_text(traceback_text: str) -> TracebackSummary:
    """Parse common Python traceback text into a bounded structured summary."""

    lines = [line.rstrip("\n") for line in traceback_text.splitlines() if line.strip()]
    file_path: str | None = None
    line_number: int | None = None
    code_context: str | None = None

    for idx, line in enumerate(lines):
        match = _FILE_LINE_RE.match(line)
        if not match:
            continue
        file_path = match.group("path")
        line_number = int(match.group("line"))
        if idx + 1 < len(lines):
            possible_code = lines[idx + 1].strip()
            if possible_code and not possible_code.startswith("File "):
                code_context = possible_code

    exc_type = "UnknownError"
    msg = ""
    for line in reversed(lines):
        match = _EXCEPTION_RE.match(line.strip())
        if match:
            exc_type = match.group("exc")
            msg = match.group("msg")
            break

    return TracebackSummary(
        exception_type=exc_type,
        message=msg,
        file_path=file_path,
        line_number=line_number,
        code_context=code_context,
        heuristic_note=(
            "Bounded traceback parser: extracts common CPython traceback shapes only; verify against full traceback."
        ),
    )


def traceback_summary_dict(traceback_text: str) -> dict[str, object]:
    return asdict(parse_traceback_text(traceback_text))
