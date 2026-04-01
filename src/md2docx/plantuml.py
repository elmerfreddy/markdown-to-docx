from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def render_plantuml_to_png(plantuml_src: str, *, output_png: Path) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)

    java_bin = _resolve_java_bin()
    if not java_bin:
        raise RuntimeError(
            "Java runtime not found. Install Java via mise (java = \"liberica-jre-21\") and run `mise install` "
            "or ensure `java` is available in PATH."
        )

    jar_path = _plantuml_jar_path()
    if not jar_path.exists():
        raise RuntimeError(
            f"PlantUML jar not found at {jar_path}. Ensure tools/plantuml/plantuml.jar exists in this repository."
        )

    cmd = [
        java_bin,
        "-Djava.awt.headless=true",
        "-jar",
        str(jar_path),
        "-charset",
        "UTF-8",
        "-tpng",
        "-pipe",
    ]

    try:
        result = subprocess.run(
            cmd,
            input=plantuml_src.encode("utf-8"),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Unable to render PlantUML: {stderr or e}") from e

    if not result.stdout:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"PlantUML returned no PNG output. {stderr}")

    output_png.write_bytes(result.stdout)


def _plantuml_jar_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "tools" / "plantuml" / "plantuml.jar"


def _resolve_java_bin() -> str | None:
    java_bin = shutil.which("java")
    if java_bin:
        return java_bin

    mise_bin = shutil.which("mise")
    if not mise_bin:
        return None

    repo_root = Path(__file__).resolve().parents[2]
    try:
        res = subprocess.run(
            [mise_bin, "-C", str(repo_root), "which", "java"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    java_path = res.stdout.strip()
    if java_path and Path(java_path).exists():
        return java_path
    return None
