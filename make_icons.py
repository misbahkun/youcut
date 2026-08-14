from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PIL import Image


SOURCE: Final = Path("favicon.png")
OUTPUT: Final = Path("statics/icons")
CHARCOAL: Final = (23, 23, 22, 255)
TRANSPARENT: Final = (0, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class IconSpec:
    filename: str
    size: int
    padding_ratio: float
    background: tuple[int, int, int, int] | None = None


def crop_artwork(source: Image.Image) -> Image.Image:
    image = source.convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        msg = f"{SOURCE} is fully transparent; favicon artwork is required."
        raise RuntimeError(msg)
    return image.crop(bbox)


def render_icon(artwork: Image.Image, spec: IconSpec) -> Image.Image:
    available = round(spec.size * (1 - spec.padding_ratio * 2))
    scale = min(available / artwork.width, available / artwork.height)
    rendered_size = (
        max(1, round(artwork.width * scale)),
        max(1, round(artwork.height * scale)),
    )
    rendered = artwork.resize(rendered_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (spec.size, spec.size), spec.background or TRANSPARENT)
    offset = (
        (spec.size - rendered.width) // 2,
        (spec.size - rendered.height) // 2,
    )
    canvas.alpha_composite(rendered, offset)
    return canvas


def main() -> None:
    artwork = crop_artwork(Image.open(SOURCE))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    specs: Final = (
        IconSpec("favicon-32.png", 32, 0.09),
        IconSpec("apple-touch-icon.png", 180, 0.15, CHARCOAL),
        IconSpec("icon-192.png", 192, 0.11),
        IconSpec("icon-512.png", 512, 0.11),
        IconSpec("icon-512-maskable.png", 512, 0.20, CHARCOAL),
    )

    for spec in specs:
        render_icon(artwork, spec).save(OUTPUT / spec.filename)

    render_icon(artwork, IconSpec("favicon.ico", 64, 0.09)).save(
        OUTPUT / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )

    print("YouCut icons generated from favicon.png.")


if __name__ == "__main__":
    main()
