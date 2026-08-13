from PIL import Image, ImageDraw, ImageFont
import os


OUTPUT = "statics/icons"

os.makedirs(
    OUTPUT,
    exist_ok=True
)


def create_icon(
    filename,
    size
):

    image = Image.new(
        "RGBA",
        (size, size),
        "#e14b35"
    )

    draw = ImageDraw.Draw(
        image
    )


    # Background
    draw.rounded_rectangle(
        (
            size * 0.08,
            size * 0.08,
            size * 0.92,
            size * 0.92
        ),
        radius=int(size * 0.18),
        fill="#171716"
    )


    # Youcut symbol sederhana
    line_width = max(
        4,
        int(size * 0.035)
    )

    center = size / 2

    draw.line(
        (
            size * 0.25,
            size * 0.30,
            size * 0.75,
            size * 0.70
        ),
        fill="#f05b45",
        width=line_width
    )

    draw.line(
        (
            size * 0.75,
            size * 0.30,
            size * 0.25,
            size * 0.70
        ),
        fill="#f05b45",
        width=line_width
    )


    image.save(
        os.path.join(
            OUTPUT,
            filename
        ),
        "PNG"
    )


create_icon(
    "icon-192.png",
    192
)

create_icon(
    "icon-512.png",
    512
)

create_icon(
    "icon-512-maskable.png",
    512
)


print("PWA icons berhasil dibuat.")