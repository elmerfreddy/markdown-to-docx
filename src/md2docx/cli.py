from __future__ import annotations

import argparse
from pathlib import Path
import sys

from md2docx.build import build_docx
from md2docx.validate import validate_project


def _path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="md2docx")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_validate = sub.add_parser("validate", help="Validate markdown, refs and sources")
    p_validate.add_argument("input", type=_path, help="Input markdown file")
    p_validate.add_argument("--sources", type=_path, default=_path("references/sources.yaml"))
    p_validate.add_argument("--strict", action="store_true", help="Fail on warnings")

    p_build = sub.add_parser("build", help="Build docx from markdown")
    p_build.add_argument("input", type=_path, help="Input markdown file")
    p_build.add_argument(
        "--template",
        type=_path,
        default=_path("templates/Formato_GIRS.docx"),
        help="Formato_GIRS docx template",
    )
    p_build.add_argument("--meta", type=_path, default=_path("meta.yaml"))
    p_build.add_argument("--sources", type=_path, default=_path("references/sources.yaml"))
    p_build.add_argument("--output", type=_path, default=_path("build/report.docx"))
    p_build.add_argument(
        "--workdir",
        type=_path,
        default=_path("build/.md2docx"),
        help="Working directory for intermediate artifacts",
    )
    p_build.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Do not delete intermediate artifacts",
    )

    args = parser.parse_args(argv)

    try:
        if args.cmd == "validate":
            report = validate_project(args.input, sources_path=args.sources, strict=args.strict)
            sys.stdout.write(report.to_text() + "\n")
            return 0 if report.ok else 2

        if args.cmd == "build":
            report = validate_project(args.input, sources_path=args.sources, strict=True)
            if not report.ok:
                sys.stderr.write(report.to_text() + "\n")
                return 2

            args.output.parent.mkdir(parents=True, exist_ok=True)
            build_docx(
                input_md=args.input,
                template_docx=args.template,
                meta_path=args.meta,
                sources_path=args.sources,
                output_docx=args.output,
                workdir=args.workdir,
                keep_workdir=args.keep_workdir,
            )
            sys.stdout.write(f"OK: wrote {args.output}\n")
            return 0

        raise RuntimeError(f"Unknown command: {args.cmd}")
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
