from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import os
import shutil


def render_mermaid_to_png(mermaid_src: str, *, output_png: Path) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        in_path = td_path / "diagram.mmd"
        in_path.write_text(mermaid_src, encoding="utf-8")

        # Prefer explicit config/env, then local install, then npx.
        candidates: list[list[str]] = []

        env_mmdc = os.environ.get("MD2DOCX_MMDC")
        if env_mmdc:
            candidates.append([env_mmdc])

        candidates.append(["mmdc"])

        # repo-local install (npm): node_modules/.bin/mmdc(.cmd)
        local = Path.cwd() / "node_modules" / ".bin" / ("mmdc.cmd" if os.name == "nt" else "mmdc")
        if local.exists():
            candidates.append([str(local)])

        # last resort: npx (may download)
        candidates.append(["npx", "-y", "@mermaid-js/mermaid-cli"])

        cmds: list[list[str]] = []
        for base in candidates:
            cmds.append(
                [
                    *base,
                    "-i",
                    str(in_path),
                    "-o",
                    str(output_png),
                    "--backgroundColor",
                    "transparent",
                    "--width",
                    "1600",
                ]
            )

        last_err: Exception | None = None
        for cmd in cmds:
            try:
                _run(cmd)
                return
            except FileNotFoundError as e:
                last_err = e
            except subprocess.CalledProcessError as e:
                last_err = RuntimeError(e.stderr.decode("utf-8", errors="replace"))

        raise RuntimeError(f"Unable to render mermaid. Tried: {cmds}. Last error: {last_err}")


def _run(cmd: list[str]) -> None:
    # On Windows, tools installed via npm are often .cmd wrappers.
    if os.name == "nt":
        exe = shutil.which(cmd[0]) or cmd[0]
        if str(exe).lower().endswith((".cmd", ".bat")):
            # Use cmd.exe to run .cmd/.bat reliably.
            subprocess.run(["cmd", "/c", *cmd], check=True, capture_output=True)
            return

    subprocess.run(cmd, check=True, capture_output=True)
