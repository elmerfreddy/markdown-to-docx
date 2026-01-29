from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import yaml


@dataclass
class ValidationReport:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_text(self) -> str:
        lines: list[str] = []
        if self.errors:
            lines.append("Errors:")
            lines.extend([f"- {e}" for e in self.errors])
        if self.warnings:
            lines.append("Warnings:")
            lines.extend([f"- {w}" for w in self.warnings])
        if not self.errors and not self.warnings:
            lines.append("OK")
        return "\n".join(lines)


_FIG_DIRECTIVE_RE = re.compile(r"^<!--\s*figure\s+(.*?)\s*-->\s*$", re.M)
_TAB_DIRECTIVE_RE = re.compile(r"^<!--\s*table\s+(.*?)\s*-->\s*$", re.M)
_MERMAID_FENCE_RE = re.compile(r"^```mermaid\s*$", re.M)


def _parse_kv(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    token_re = re.compile(r"(\w+)=(\"[^\"]*\"|\S+)")
    for m in token_re.finditer(s):
        k = m.group(1)
        v = m.group(2)
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        out[k] = v
    return out


def _load_sources_tags(sources_path: Path) -> set[str]:
    if not sources_path.exists():
        return set()
    data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    tags: set[str] = set()
    for src in data.get("sources", []) or []:
        tag = src.get("tag")
        if tag:
            tags.add(str(tag))
    return tags


def validate_project(input_md: Path, *, sources_path: Path, strict: bool) -> ValidationReport:
    txt = input_md.read_text(encoding="utf-8")
    errors: list[str] = []
    warnings: list[str] = []

    fig_ids: set[str] = set()
    tab_ids: set[str] = set()

    for m in _FIG_DIRECTIVE_RE.finditer(txt):
        kv = _parse_kv(m.group(1))
        missing = [k for k in ("id", "title", "source") if k not in kv]
        if missing:
            errors.append(f"figure directive missing keys: {missing}")
            continue
        fig_id = str(kv["id"]).strip()
        if fig_id in fig_ids:
            errors.append(f"duplicate figure id: {fig_id}")
        fig_ids.add(fig_id)

    for m in _TAB_DIRECTIVE_RE.finditer(txt):
        kv = _parse_kv(m.group(1))
        missing = [k for k in ("id", "title", "source") if k not in kv]
        if missing:
            errors.append(f"table directive missing keys: {missing}")
            continue
        tab_id = str(kv["id"]).strip()
        if tab_id in tab_ids:
            errors.append(f"duplicate table id: {tab_id}")
        tab_ids.add(tab_id)

    # Mermaid fences must be preceded by a figure directive
    lines = txt.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == "```mermaid":
            # Look backwards for the previous non-empty line
            j = idx - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j < 0 or not lines[j].strip().startswith("<!--figure"):
                errors.append(f"mermaid block at line {idx+1} must be preceded by a figure directive")

    # Cross refs
    for ref_id in re.findall(r"@fig:([A-Za-z0-9_-]+)", txt):
        if ref_id not in fig_ids:
            errors.append(f"unknown figure ref id: {ref_id}")
    for ref_id in re.findall(r"@tab:([A-Za-z0-9_-]+)", txt):
        if ref_id not in tab_ids:
            errors.append(f"unknown table ref id: {ref_id}")

    # Citations
    tags = _load_sources_tags(sources_path)
    if not tags:
        warnings.append(f"no sources loaded from {sources_path}")
    for tag in re.findall(r"\[@([A-Za-z0-9_-]+)\]", txt):
        if tag not in tags:
            errors.append(f"citation tag not found in sources: {tag}")

    # Warn if the author adds a bibliography heading that will likely duplicate the template.
    if re.search(r"^#{1,6}\s+Referencias\s*$", txt, flags=re.M | re.I):
        warnings.append(
            "Markdown contains a 'Referencias' heading. The template already includes 'Referencias' + BIBLIOGRAPHY."
        )

    if strict and warnings and not errors:
        errors.append("warnings present in strict mode")

    return ValidationReport(errors=errors, warnings=warnings)
