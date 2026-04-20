from __future__ import annotations

import re
from pathlib import Path

from .traceback_utils import parse_traceback_text


def _preview(before: str, after: str, path: Path, patch_type: str, summary: str, can_apply: bool, notes: list[str]) -> dict[str, object]:
    return {
        "can_apply": can_apply,
        "patch_type": patch_type,
        "summary": summary,
        "target_file": str(path),
        "preview": {"before": before, "after": after},
        "confidence": "high" if can_apply else "low",
        "notes": notes,
    }


def _missing_import_patch(source: str, path: Path) -> dict[str, object] | None:
    if "requests.get(" in source and "import requests" not in source:
        after = "import requests\n" + source
        return _preview(source, after, path, "missing_import", "Insert missing `import requests`.", True, [])
    return None


def _missing_colon_patch(source: str, path: Path) -> dict[str, object] | None:
    lines = source.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"(if|for|while|def|try|class)\b", stripped) and not stripped.endswith(":"):
            lines[idx] = line + ":"
            after = "\n".join(lines) + ("\n" if source.endswith("\n") else "")
            return _preview(source, after, path, "missing_colon", f"Add missing colon to line {idx + 1}.", True, [])
    return None


def _file_mode_patch(source: str, path: Path) -> dict[str, object] | None:
    mapping = {"rw": "r+", "wr": "w+", "ra": "a+"}
    match = re.search(r"open\((?P<head>[^\)]*?),\s*['\"](?P<mode>rw|wr|ra)['\"]", source)
    if not match:
        return None
    mode = match.group("mode")
    after = source.replace(f'"{mode}"', f'"{mapping[mode]}"', 1).replace(f"'{mode}'", f"'{mapping[mode]}'", 1)
    return _preview(source, after, path, "file_open_mode", f"Replace mode `{mode}` with `{mapping[mode]}`.", True, [])


def _int_str_concat_patch(source: str, path: Path) -> dict[str, object] | None:
    pattern = re.compile(r"(?P<a>[A-Za-z_][A-Za-z0-9_]*)\s*\+\s*(?P<b>'[^']*'|\"[^\"]*\")")
    match = pattern.search(source)
    if match:
        repl = f"str({match.group('a')}) + {match.group('b')}"
        after = source[: match.start()] + repl + source[match.end() :]
        return _preview(source, after, path, "int_str_concat", "Wrap left operand in str(...) for concatenation.", True, [])
    pattern2 = re.compile(r"(?P<a>'[^']*'|\"[^\"]*\")\s*\+\s*(?P<b>[A-Za-z_][A-Za-z0-9_]*)")
    match2 = pattern2.search(source)
    if match2:
        repl = f"{match2.group('a')} + str({match2.group('b')})"
        after = source[: match2.start()] + repl + source[match2.end() :]
        return _preview(source, after, path, "int_str_concat", "Wrap right operand in str(...) for concatenation.", True, [])
    return None


def _main_guard_patch(source: str, path: Path) -> dict[str, object] | None:
    if "def main(" in source and "if __name__ == \"__main__\":" not in source:
        suffix = "\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n"
        after = source + suffix
        return _preview(source, after, path, "main_guard_missing", "Insert missing main guard block.", True, [])
    return None


def _requests_status_patch(source: str, path: Path) -> dict[str, object] | None:
    if "requests.get(" not in source or "raise_for_status()" in source:
        return None
    lines = source.splitlines()
    for idx, line in enumerate(lines):
        if "requests.get(" in line and "=" in line:
            lhs = line.split("=", 1)[0].strip()
            indent = re.match(r"\s*", line).group(0)
            lines.insert(idx + 1, f"{indent}{lhs}.raise_for_status()")
            after = "\n".join(lines) + ("\n" if source.endswith("\n") else "")
            return _preview(source, after, path, "requests_status_handling", "Add raise_for_status() after requests.get.", True, [])
    return None


def _patchers() -> list[tuple[str, callable]]:
    return [
        ("missing_import", _missing_import_patch),
        ("int_str_concat", _int_str_concat_patch),
        ("missing_colon", _missing_colon_patch),
        ("file_open_mode", _file_mode_patch),
        ("main_guard_missing", _main_guard_patch),
        ("requests_status_handling", _requests_status_patch),
    ]


def list_patch_candidates(path: Path, issue_type: str | None = None) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    candidates: list[dict[str, object]] = []
    for idx, (patch_name, patcher) in enumerate(_patchers(), start=1):
        if issue_type and issue_type != patch_name:
            continue
        candidate = patcher(source, path)
        if not candidate or not candidate["can_apply"]:
            continue
        candidates.append(
            {
                "patch_id": f"patch-{idx:03d}",
                "patch_type": patch_name,
                "summary": candidate["summary"],
                "confidence": candidate["confidence"],
                "files": [str(path)],
                "notes": ["Safe deterministic candidate."],
                "preview": candidate["preview"],
            }
        )

    return {
        "mode": "interactive_selection",
        "target": str(path),
        "candidates": candidates,
        "notes": ["Candidates are bounded and require explicit selection/apply."],
    }


def _candidate_by_id(path: Path, patch_id: str, issue_type: str | None = None) -> dict[str, object] | None:
    payload = list_patch_candidates(path, issue_type=issue_type)
    for candidate in payload["candidates"]:
        if candidate["patch_id"] == patch_id:
            return candidate
    return None


def preview_safe_patch(path: Path, issue_type: str | None = None, select: str | None = None) -> dict[str, object]:
    if select:
        candidate = _candidate_by_id(path, select, issue_type=issue_type)
        if candidate:
            return {
                "can_apply": True,
                "patch_type": candidate["patch_type"],
                "summary": candidate["summary"],
                "target_file": str(path),
                "preview": candidate["preview"],
                "confidence": candidate["confidence"],
                "notes": [f"Selected candidate {select}.", "Review preview before --apply."],
            }
        source = path.read_text(encoding="utf-8")
        return _preview(source, source, path, issue_type or "none", "Unknown patch selection id.", False, ["Use --interactive to list ids."])

    candidates = list_patch_candidates(path, issue_type=issue_type)["candidates"]
    if candidates:
        top = candidates[0]
        return {
            "can_apply": True,
            "patch_type": top["patch_type"],
            "summary": top["summary"],
            "target_file": str(path),
            "preview": top["preview"],
            "confidence": top["confidence"],
            "notes": ["Safe patch scope is narrow.", "Use --interactive for full candidate list."],
        }

    source = path.read_text(encoding="utf-8")
    return _preview(
        source,
        source,
        path,
        issue_type or "none",
        "No safe high-confidence patch candidate found.",
        False,
        ["Patch engine rejected ambiguous or unsupported rewrite."],
    )


def apply_safe_patch(path: Path, issue_type: str | None = None, apply: bool = False, select: str | None = None) -> dict[str, object]:
    payload = preview_safe_patch(path, issue_type=issue_type, select=select)
    payload["applied"] = False
    if apply and payload["can_apply"]:
        path.write_text(str(payload["preview"]["after"]), encoding="utf-8")
        payload["applied"] = True
        payload["notes"].append("Patch was applied because --apply was explicitly provided.")
    elif apply and not payload["can_apply"]:
        payload["notes"].append("--apply requested but patch was not eligible.")
    else:
        payload["notes"].append("Preview-only mode (default).")
    return payload


def patch_from_traceback(
    traceback_path: Path,
    apply: bool = False,
    issue_type: str | None = None,
    interactive: bool = False,
    select: str | None = None,
) -> dict[str, object]:
    summary = parse_traceback_text(traceback_path.read_text(encoding="utf-8"))
    target = Path(summary.file_path) if summary.file_path else None
    issue = issue_type
    if issue is None:
        if summary.exception_type in {"ImportError", "ModuleNotFoundError"}:
            issue = "missing_import"
        elif summary.exception_type == "TypeError":
            issue = "int_str_concat"
        elif summary.exception_type == "SyntaxError":
            issue = "missing_colon"

    if target is None or not target.exists():
        return {
            "mode": "interactive_selection" if interactive else "direct",
            "can_apply": False,
            "patch_type": issue or "unknown",
            "summary": "Traceback did not resolve to an accessible local target file.",
            "target_file": str(target) if target else "",
            "preview": {"before": "", "after": ""},
            "confidence": "low",
            "notes": ["Provide a traceback that includes a local file path."],
            "applied": False,
            "traceback_summary": {
                "exception_type": summary.exception_type,
                "message": summary.message,
                "line_number": summary.line_number,
            },
        }

    if interactive:
        payload = list_patch_candidates(target, issue_type=issue)
        payload["traceback_summary"] = {
            "exception_type": summary.exception_type,
            "message": summary.message,
            "line_number": summary.line_number,
        }
        return payload

    payload = apply_safe_patch(target, issue_type=issue, apply=apply, select=select)
    payload["traceback_summary"] = {
        "exception_type": summary.exception_type,
        "message": summary.message,
        "line_number": summary.line_number,
    }
    return payload
