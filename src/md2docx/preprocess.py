from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct

from md2docx.codeimg import render_code_to_png
from md2docx.mermaid import render_mermaid_to_png


CAPTION_FIG_RE = re.compile(r"^\[\[MD2DOCX_CAPTION_FIG:([A-Za-z0-9_-]+)\|(.*)\]\]$")
CAPTION_TAB_RE = re.compile(r"^\[\[MD2DOCX_CAPTION_TAB:([A-Za-z0-9_-]+)\|(.*)\]\]$")


@dataclass(frozen=True)
class PreprocessResult:
    markdown: str


_FIG_DIRECTIVE_RE = re.compile(r"^<!--\s*figure\s+(.*?)\s*-->\s*$")
_TAB_DIRECTIVE_RE = re.compile(r"^<!--\s*table\s+(.*?)\s*-->\s*$")
_CITATION_GROUP_RE = re.compile(r"\[(?P<content>[^\[\]]*?@[^\]]*?)\]")

# Target figure sizing in the generated DOCX.
# Keep Mermaid diagrams readable without overflowing page height.
MERMAID_MAX_WIDTH_IN = 6.0
MERMAID_MAX_HEIGHT_IN = 7.0


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    off = 8
    if len(data) < off + 24:
        return None
    length = struct.unpack(">I", data[off : off + 4])[0]
    if data[off + 4 : off + 8] != b"IHDR":
        return None
    ihdr = data[off + 8 : off + 8 + length]
    if len(ihdr) < 8:
        return None
    w, h = struct.unpack(">II", ihdr[:8])
    return int(w), int(h)


def _parse_kv(s: str) -> dict[str, str]:
    # Parses: key=value or key="value with spaces"
    out: dict[str, str] = {}
    token_re = re.compile(r"(\w+)=(\"[^\"]*\"|\S+)")
    for m in token_re.finditer(s):
        k = m.group(1)
        v = m.group(2)
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        out[k] = v
    return out


def _sanitize_id(s: str) -> str:
    s = s.strip()
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", s)
    s = s.strip("-")
    if not s:
        return "x"
    if not re.match(r"^[A-Za-z]", s):
        s = "x-" + s
    return s


def _replace_inline_tokens(text: str) -> str:
    # Cross refs
    text = re.sub(r"@fig:([A-Za-z0-9_-]+)", r"[[MD2DOCX_REF:fig:\1]]", text)
    text = re.sub(r"@tab:([A-Za-z0-9_-]+)", r"[[MD2DOCX_REF:tab:\1]]", text)
    # Citations (Pandoc-style bracket groups)
    text = _replace_citation_groups(text)
    return text


def _replace_citation_groups(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        content = m.group("content")

        def repl_tag(mt: re.Match[str]) -> str:
            tag = mt.group(1)
            return f"[[MD2DOCX_CITATION:{tag}]]"

        # Replace any @tag or -@tag with a placeholder.
        return re.sub(r"-?@([A-Za-z0-9_-]+)", repl_tag, content)

    return _CITATION_GROUP_RE.sub(repl, text)


def preprocess_markdown(*, input_md: Path, out_dir: Path, media_dir: Path) -> PreprocessResult:
    raw = input_md.read_text(encoding="utf-8")
    lines = raw.splitlines()

    out_lines: list[str] = []

    i = 0
    in_code_fence = False
    code_fence = ""
    pending_figure: dict[str, str] | None = None
    pending_table: dict[str, str] | None = None

    while i < len(lines):
        line = lines[i]

        # Handle a pending figure BEFORE generic fence handling.
        if pending_figure and not in_code_fence:
            # Skip blank lines between directive and content
            if not line.strip():
                i += 1
                continue

            # Mermaid code block
            if line.strip() == "```mermaid":
                mermaid_lines: list[str] = []
                i += 1
                while i < len(lines) and lines[i].strip() != "```":
                    mermaid_lines.append(lines[i])
                    i += 1
                if i >= len(lines):
                    raise ValueError("Unclosed mermaid fence")
                # consume closing fence
                i += 1

                fig_id = pending_figure["id"]
                title = pending_figure["title"]
                source = pending_figure["source"]

                out_lines.extend(
                    [
                        '::: {custom-style="Caption"}',
                        f"[[MD2DOCX_CAPTION_FIG:{fig_id}|{title}]]",
                        ":::",
                        "",
                    ]
                )

                png_path = media_dir / f"fig_{fig_id}.png"
                render_mermaid_to_png("\n".join(mermaid_lines), output_png=png_path)

                # Reference relative to processed.md
                rel = png_path.relative_to(out_dir)
                dims = _png_dimensions(png_path)
                width_in = MERMAID_MAX_WIDTH_IN
                if dims is not None:
                    w_px, h_px = dims
                    if h_px > 0:
                        width_in = min(MERMAID_MAX_WIDTH_IN, MERMAID_MAX_HEIGHT_IN * (w_px / h_px))
                out_lines.append(f"![]({rel.as_posix()}){{width={width_in:.2f}in}}")
                out_lines.append("")
                out_lines.append(f"Fuente: {source}")
                out_lines.append("")

                pending_figure = None
                continue

            # Code fence
            if line.strip().startswith("```"):
                fence = line.strip()
                lang = fence[3:].strip() or None
                code_lines: list[str] = []
                i += 1
                while i < len(lines) and lines[i].strip() != "```":
                    code_lines.append(lines[i])
                    i += 1
                if i >= len(lines):
                    raise ValueError("Unclosed code fence")
                # consume closing fence
                i += 1

                fig_id = pending_figure["id"]
                title = pending_figure["title"]
                source = pending_figure["source"]

                out_lines.extend(
                    [
                        '::: {custom-style="Caption"}',
                        f"[[MD2DOCX_CAPTION_FIG:{fig_id}|{title}]]",
                        ":::",
                        "",
                    ]
                )

                png_path = media_dir / f"code_{fig_id}.png"
                render_code_to_png("\n".join(code_lines), language=lang, output_png=png_path)

                rel = png_path.relative_to(out_dir)
                dims = _png_dimensions(png_path)
                width_in = MERMAID_MAX_WIDTH_IN
                if dims is not None:
                    w_px, h_px = dims
                    if h_px > 0:
                        width_in = min(MERMAID_MAX_WIDTH_IN, MERMAID_MAX_HEIGHT_IN * (w_px / h_px))
                out_lines.append(f"![]({rel.as_posix()}){{width={width_in:.2f}in}}")
                out_lines.append("")
                out_lines.append(f"Fuente: {source}")
                out_lines.append("")

                pending_figure = None
                continue

            # Image line
            if line.strip().startswith("!["):
                fig_id = pending_figure["id"]
                title = pending_figure["title"]
                source = pending_figure["source"]

                out_lines.extend(
                    [
                        '::: {custom-style="Caption"}',
                        f"[[MD2DOCX_CAPTION_FIG:{fig_id}|{title}]]",
                        ":::",
                        "",
                        _replace_inline_tokens(line),
                        "",
                        f"Fuente: {source}",
                        "",
                    ]
                )

                pending_figure = None
                i += 1
                continue

            raise ValueError(
                f"figure directive must be followed by mermaid, code fence, or image at line {i+1}"
            )

        # Track fenced code blocks
        if line.strip().startswith("```"):
            fence = line.strip()
            if not in_code_fence:
                in_code_fence = True
                code_fence = fence
            else:
                in_code_fence = False
                code_fence = ""
            out_lines.append(line)
            i += 1
            continue

        if not in_code_fence:
            m_fig = _FIG_DIRECTIVE_RE.match(line)
            if m_fig:
                pending_figure = _parse_kv(m_fig.group(1))
                if "id" not in pending_figure or "title" not in pending_figure or "source" not in pending_figure:
                    raise ValueError(f"figure directive missing required keys at line {i+1}")
                pending_figure = {k: v for k, v in pending_figure.items()}
                pending_figure["id"] = _sanitize_id(pending_figure["id"])
                i += 1
                continue

            m_tab = _TAB_DIRECTIVE_RE.match(line)
            if m_tab:
                pending_table = _parse_kv(m_tab.group(1))
                if "id" not in pending_table or "title" not in pending_table or "source" not in pending_table:
                    raise ValueError(f"table directive missing required keys at line {i+1}")
                pending_table = {k: v for k, v in pending_table.items()}
                pending_table["id"] = _sanitize_id(pending_table["id"])
                i += 1
                continue

        # Handle a pending table
        if pending_table and not in_code_fence:
            if not line.strip():
                i += 1
                continue

            # Assume a pipe table starts here and continues until blank line
            if "|" not in line:
                raise ValueError(f"table directive must be followed by a pipe table at line {i+1}")

            tab_id = pending_table["id"]
            title = pending_table["title"]
            source = pending_table["source"]

            out_lines.extend(
                [
                    '::: {custom-style="Caption"}',
                    f"[[MD2DOCX_CAPTION_TAB:{tab_id}|{title}]]",
                    ":::",
                    "",
                ]
            )

            # table block
            while i < len(lines):
                if not lines[i].strip():
                    break
                out_lines.append(_replace_inline_tokens(lines[i]))
                i += 1
            out_lines.append("")
            out_lines.append(f"Fuente: {source}")
            out_lines.append("")
            pending_table = None
            continue

        # Default path
        if in_code_fence:
            out_lines.append(line)
        else:
            out_lines.append(_replace_inline_tokens(line))
        i += 1

    return PreprocessResult(markdown="\n".join(out_lines) + "\n")
