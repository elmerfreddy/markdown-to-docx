from pathlib import Path

from pygments import highlight
from pygments.formatters.img import ImageFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound


def render_code_to_png(code: str, *, language: str | None, output_png: Path) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)

    lexer = _pick_lexer(language)
    formatter = _build_formatter()
    data = highlight(code, lexer, formatter)
    output_png.write_bytes(data)


def _pick_lexer(language: str | None):
    if language:
        try:
            return get_lexer_by_name(language)
        except ClassNotFound:
            return TextLexer()
    return TextLexer()


def _build_formatter() -> ImageFormatter:
    kwargs: dict[str, object] = {
        "style": "xcode",
        "line_numbers": True,
        "font_size": 16,
        "background_color": "#ffffff",
        "line_number_bg": "#f7f7f7",
        "line_number_fg": "#666666",
        "line_number_pad": 6,
        "image_pad": 10,
        "line_pad": 2,
    }

    font_path = _find_mono_font()
    if font_path:
        kwargs["font_name"] = font_path

    return ImageFormatter(**kwargs)


def _find_mono_font() -> str | None:
    candidates = [
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
    ]

    for p in candidates:
        if p.exists():
            return str(p)
    return None
