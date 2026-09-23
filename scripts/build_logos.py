"""Genera logos del ERP LEIVA renderizando los SVG con resvg-py (Rust engine).

SVGs fuente:
  - assets/logo.svg            -> icono cuadrado
  - assets/logo-wordmark.svg   -> logo horizontal (icono + texto)

Salidas:
  - assets/icon-{32,64,128,256,512}.png
  - assets/logo-wordmark.png
  - assets/favicon.ico  (multi-resolucion)
  - frontend/static/img/{favicon.ico, logo.png, icon.png}
"""
from pathlib import Path
import resvg_py

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FRONTEND = ROOT / "frontend" / "static" / "img"
FRONTEND.mkdir(parents=True, exist_ok=True)


def render_svg(svg_path: Path, output_path: Path, width: int, height: int):
    """Renderiza SVG a PNG con el tamano deseado."""
    svg_text = svg_path.read_text(encoding="utf-8")
    png_bytes = resvg_py.svg_to_bytes(
        svg_string=svg_text,
        width=width,
        height=height,
    )
    output_path.write_bytes(bytes(png_bytes))


def make_favicon(png_256: Path, out: Path):
    """Genera ICO multi-resolucion a partir de un PNG 256x256."""
    from PIL import Image
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    Image.open(png_256).save(out, format="ICO", sizes=sizes)


def main():
    print("Generando logos desde SVG (resvg-py)...")
    ASSETS.mkdir(exist_ok=True)

    icon_svg = ASSETS / "logo.svg"
    wm_svg = ASSETS / "logo-wordmark.svg"

    tmp_256 = ASSETS / "_tmp_icon_256.png"

    # Iconos cuadrados
    for sz in [32, 64, 128, 256, 512]:
        out = ASSETS / f"icon-{sz}.png"
        if sz == 256:
            render_svg(icon_svg, tmp_256, sz, sz)
        render_svg(icon_svg, out, sz, sz)
        print(f"  + assets/icon-{sz}.png")

    # Wordmark alta resolucion (1200x360)
    render_svg(wm_svg, ASSETS / "logo-wordmark.png", 1200, 360)
    print(f"  + assets/logo-wordmark.png (1200x360)")

    # Favicon multi-resolucion
    ico = ASSETS / "favicon.ico"
    make_favicon(tmp_256, ico)
    if tmp_256.exists():
        tmp_256.unlink()
    print(f"  + assets/favicon.ico ({ico.stat().st_size} bytes)")

    # Copiar a frontend
    (FRONTEND / "favicon.ico").write_bytes(ico.read_bytes())
    print("  + frontend/static/img/favicon.ico")

    render_svg(wm_svg, FRONTEND / "logo.png", 600, 180)
    print("  + frontend/static/img/logo.png (600x180)")

    render_svg(icon_svg, FRONTEND / "icon.png", 128, 128)
    print("  + frontend/static/img/icon.png (128x128)")

    print()
    print("OK")


if __name__ == "__main__":
    main()