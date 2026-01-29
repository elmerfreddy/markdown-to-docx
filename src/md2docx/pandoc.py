from __future__ import annotations

from pathlib import Path
import os
import subprocess


def run_pandoc_to_docx(
    *,
    input_md: Path,
    output_docx: Path,
    reference_doc: Path,
    resource_paths: list[Path],
) -> None:
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    uniq: list[str] = []
    for p in resource_paths:
        if not p.exists():
            continue
        s = str(p)
        if s not in uniq:
            uniq.append(s)
    resource_path_arg = os.pathsep.join(uniq)

    cmd = [
        "pandoc",
        str(input_md),
        "--from",
        "markdown+fenced_divs+bracketed_spans+link_attributes+raw_attribute",
        "--to",
        "docx",
        "--reference-doc",
        str(reference_doc),
        "--resource-path",
        resource_path_arg,
        "-o",
        str(output_docx),
    ]

    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        stderr = p.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"pandoc failed (code {p.returncode}): {stderr}")
