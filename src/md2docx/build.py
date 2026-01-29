from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from md2docx.preprocess import preprocess_markdown
from md2docx.pandoc import run_pandoc_to_docx
from md2docx.docxops import assemble_final_docx


@dataclass(frozen=True)
class BuildArtifacts:
    processed_md: Path
    body_docx: Path
    media_dir: Path


def build_docx(
    *,
    input_md: Path,
    template_docx: Path,
    meta_path: Path,
    sources_path: Path,
    output_docx: Path,
    workdir: Path,
    keep_workdir: bool,
) -> None:
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    media_dir = workdir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    processed_md = workdir / "processed.md"
    body_docx = workdir / "body.docx"

    processed = preprocess_markdown(
        input_md=input_md,
        out_dir=workdir,
        media_dir=media_dir,
    )
    processed_md.write_text(processed.markdown, encoding="utf-8")

    run_pandoc_to_docx(
        input_md=processed_md,
        output_docx=body_docx,
        reference_doc=template_docx,
        resource_paths=[input_md.parent, input_md.parent.parent],
    )

    assemble_final_docx(
        template_docx=template_docx,
        body_docx=body_docx,
        output_docx=output_docx,
        meta_path=meta_path,
        sources_path=sources_path,
    )

    if not keep_workdir:
        shutil.rmtree(workdir)
