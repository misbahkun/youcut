from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw


OUTPUT: Final = Path("statics/icons")
CANVAS_UNITS: Final = 64
CHARCOAL: Final = (23, 23, 22, 255)
CORAL: Final = (240, 91, 69, 255)
WARM: Final = (240, 240, 237, 255)
TRANSPARENT: Final = (0, 0, 0, 0)


def create_icon(size: int, *, maskable: bool = False) -> Image.Image:
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), CHARCOAL if maskable else TRANSPARENT)
    draw = ImageDraw.Draw(image)

    def unit(value: int) -> float:
        return value / CANVAS_UNITS * canvas

    margin = 0 if maskable else unit(4)
    corner_radius = unit(16 if maskable else 14)
    draw.rounded_rectangle(
        (margin, margin, canvas - margin, canvas - margin),
        radius=corner_radius,
        fill=CHARCOAL,
    )

    stroke_width = max(3 * scale, int(unit(11)))
    draw.line(
        [(unit(19), unit(17)), (unit(32), unit(31)), (unit(45), unit(17))],
        fill=CORAL,
        width=stroke_width,
        joint="curve",
    )
    draw.line(
        [(unit(32), unit(31)), (unit(32), unit(48))],
        fill=CORAL,
        width=stroke_width,
    )

    dot_radius = stroke_width / 2
    for x, y in ((19, 17), (45, 17), (32, 48)):
        draw.ellipse(
            (
                unit(x) - dot_radius,
                unit(y) - dot_radius,
                unit(x) + dot_radius,
                unit(y) + dot_radius,
            ),
            fill=CORAL,
        )

    draw.polygon(
        [
            (unit(45), unit(29)),
            (unit(53), unit(29)),
            (unit(53), unit(43)),
            (unit(45), unit(43)),
            (unit(45), unit(39)),
            (unit(49), unit(39)),
            (unit(49), unit(33)),
            (unit(45), unit(33)),
        ],
        fill=WARM,
    )

    return image.resize((size, size), Image.Resampling.LANCZOS)


OUTPUT.mkdir(parents=True, exist_ok=True)
create_icon(32).save(OUTPUT / "favicon-32.png")
create_icon(180).save(OUTPUT / "apple-touch-icon.png")
create_icon(192).save(OUTPUT / "icon-192.png")
create_icon(512).save(OUTPUT / "icon-512.png")
create_icon(512, maskable=True).save(OUTPUT / "icon-512-maskable.png")
create_icon(64).save(
    OUTPUT / "favicon.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
)

print("YouCut icons generated.")
