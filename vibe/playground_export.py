"""In-memory, predictable GitHub Pages ZIP export for one compiled VibeWeb page.

The exporter never accesses the user's filesystem.  Only the generated site/
folder is published by the included GitHub Actions workflow.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

MAX_ARCHIVE_BYTES = 2_000_000
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]*\.vibe\Z")
_WORKFLOW = Path(__file__).with_name("pages_workflow.yml").read_text(encoding="utf-8")


def safe_source_filename(name: object) -> bool:
    return (
        isinstance(name, str)
        and 6 <= len(name) <= 80
        and _FILENAME.fullmatch(name) is not None
        and ".." not in name
    )


def archive_filename(name: str) -> str:
    if not safe_source_filename(name):
        raise ValueError("export filename must be a safe .vibe basename")
    label = name[:-5].strip().lower().replace(" ", "-")
    return f"vibeweb-{label}-pages.zip"


def build_pages_archive(source: str, filename: str, html: str) -> bytes:
    """Create a complete, immutable site/source/workflow bundle in memory."""
    if not safe_source_filename(filename):
        raise ValueError("export filename must be a safe .vibe basename")
    if not isinstance(source, str) or not isinstance(html, str):
        raise ValueError("export requires valid source and compiled HTML")
    if len(source) > 20_000:
        raise ValueError("source exceeds maximum size")
    if not html.lstrip().lower().startswith("<!doctype html>"):
        raise ValueError("export must contain compiled HTML")
    guide = f"""# VibeWeb GitHub Pages project

This bundle was generated from the native Vibe compiler.

## Contents

- \`site/index.html\`: A compiled preview, regenerated from source during each deployment.
- \`source/{filename}\`: The original editable Vibe source.
- \`.github/workflows/deploy-pages.yml\`: Pinned compiler build and GitHub Pages publishing workflow.

## Publish to GitHub Pages

1. Extract this archive to an **empty** GitHub repository working directory.
2. Commit all extracted files and push to the \`main\` branch.
3. In the repository, go to **Settings → Pages** and set the build/deployment
   source to **GitHub Actions**.
4. Open **Actions → Deploy VibeWeb to GitHub Pages** to check the job.
   The deployment URL appears in the completed job's environment.

The ZIP does **not** create a repository, commit files, or deploy anything
on your behalf. GitHub Pages publishes the \`site/\` folder only; other files
remain in the repository. Public repositories expose their Vibe source too.

## Making edits

Edit \`source/{filename}\` in the VibeWeb Playground or your editor,
commit it, and push to \`main\`. GitHub Actions checks out the native Vibe
compiler pinned to commit 5ed4ef6108b86e3b91c0cb24c55b25576af0cffd,
installs it, recompiles your source, and runs the Vibe heuristic
preservation gate before publishing \`site/\`. You do not need to edit
\`site/index.html\` manually. This happens on every push to \`main\`
or manually dispatched workflow run. If compilation fails, deployment
does not occur and your old live site remains unchanged.

To upgrade the language version, explicitly change the pinned \`ref:\`
in \`.github/workflows/deploy-pages.yml\` to a reviewed compiler commit.
The compiler checkout is excluded from the published site artifact.

Browser-local storage in this published site uses its actual GitHub Pages
origin. If that origin is shared with other apps, they may access its data.
Never put credentials or secrets in a published site or public source.
Only include source and generated code you intend to share.

## Boundaries

The included site is a single static HTML app. No backend, authentication,
persistent server data, account features or automatic custom domain is
configured. The Vibe preservation score is heuristic, not a security audit.
"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=9) as out:
        for path, content in (
            ("site/index.html", html),
            ("site/.nojekyll", ""),
            (f"source/{filename}", source),
            ("README.md", guide),
            (".github/workflows/deploy-pages.yml", _WORKFLOW),
        ):
            info = ZipInfo(path, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, content)
    result = buffer.getvalue()
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValueError("compiled export exceeds 2 MB")
    return result
