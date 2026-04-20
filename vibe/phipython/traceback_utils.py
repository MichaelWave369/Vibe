from __future__ import annotations

import re
from dataclasses import asdict, dataclass


_FILE_LINE_RE = re.compile(r'  File "(?P<path>.+?)", line (?P<line>\d+), in (?P<func>.+)')
_EXCEPTION_RE = re.compile(r"(?P<exc>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):\s*(?P<msg>.*)")
_DURING_RE = "During handling of the above exception, another exception occurred:"
_CAUSE_RE = "The above exception was the direct cause of the following exception:"


@dataclass(frozen=True, slots=True)
class TracebackStage:
    exception_type: str
    message: str
    file_path: str | None
    line_number: int | None
    code_context: str | None
    relation_to_previous: str | None = None


@dataclass(frozen=True, slots=True)
class TracebackSummary:
    exception_type: str
    message: str
    file_path: str | None
    line_number: int | None
    code_context: str | None
    chain: tuple[TracebackStage, ...]
    chain_summary: str
    heuristic_note: str


def parse_traceback_text(traceback_text: str) -> TracebackSummary:
    """Parse common Python traceback text, including chained exception forms."""

    lines = [line.rstrip("\n") for line in traceback_text.splitlines() if line.strip()]
    frames: list[tuple[str | None, int | None, str | None]] = []
    stages: list[TracebackStage] = []
    pending_relation: str | None = None

    for idx, line in enumerate(lines):
        frame_match = _FILE_LINE_RE.match(line)
        if frame_match:
            file_path = frame_match.group("path")
            line_number = int(frame_match.group("line"))
            code_context = None
            if idx + 1 < len(lines):
                possible = lines[idx + 1].strip()
                if possible and not possible.startswith("File "):
                    code_context = possible
            frames.append((file_path, line_number, code_context))
            continue

        stripped = line.strip()
        if stripped == _DURING_RE:
            pending_relation = "during_handling"
            continue
        if stripped == _CAUSE_RE:
            pending_relation = "direct_cause"
            continue

        exc_match = _EXCEPTION_RE.match(stripped)
        if exc_match:
            file_path, line_number, code_context = frames[-1] if frames else (None, None, None)
            stages.append(
                TracebackStage(
                    exception_type=exc_match.group("exc"),
                    message=exc_match.group("msg"),
                    file_path=file_path,
                    line_number=line_number,
                    code_context=code_context,
                    relation_to_previous=pending_relation,
                )
            )
            pending_relation = None

    if not stages:
        stages.append(
            TracebackStage(
                exception_type="UnknownError",
                message="",
                file_path=frames[-1][0] if frames else None,
                line_number=frames[-1][1] if frames else None,
                code_context=frames[-1][2] if frames else None,
                relation_to_previous=None,
            )
        )

    final = stages[-1]
    chain_summary = " -> ".join(stage.exception_type for stage in stages)

    return TracebackSummary(
        exception_type=final.exception_type,
        message=final.message,
        file_path=final.file_path,
        line_number=final.line_number,
        code_context=final.code_context,
        chain=tuple(stages),
        chain_summary=chain_summary,
        heuristic_note=(
            "Bounded traceback parser: supports common CPython traceback/chained-exception shapes; "
            "verify against full traceback text."
        ),
    )


def summarize_traceback_chain(traceback_text: str) -> dict[str, object]:
    summary = parse_traceback_text(traceback_text)
    return {
        "final_exception": summary.exception_type,
        "chain_summary": summary.chain_summary,
        "stages": [asdict(stage) for stage in summary.chain],
        "heuristic_note": summary.heuristic_note,
    }


def traceback_summary_dict(traceback_text: str) -> dict[str, object]:
    return asdict(parse_traceback_text(traceback_text))
