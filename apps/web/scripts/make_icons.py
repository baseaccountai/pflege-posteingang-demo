"""App icons for the web app manifest (F11-AC1): a white envelope on petrol.

    cd apps/api && uv run python ../web/scripts/make_icons.py

"any" icons have rounded corners on a transparent background; "maskable" icons fill the
whole square and keep the envelope inside the central safe zone (Android crops them).
"""

from pathlib import Path

from PIL import Image, ImageDraw

PETROL = (17, 94, 89, 255)  # #115e59
WHITE = (255, 255, 255, 255)
OUT = Path(__file__).parents[1] / "public" / "icons"


def icon(size: int, maskable: bool) -> Image.Image:
    scale = 4  # draw large, shrink smoothly
    big = size * scale
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if maskable:
        draw.rectangle([0, 0, big, big], fill=PETROL)
        inner = 0.30  # envelope within the safe zone (radius 40 %)
    else:
        draw.rounded_rectangle([0, 0, big - 1, big - 1], radius=big // 5, fill=PETROL)
        inner = 0.22
    left, right = big * inner, big * (1 - inner)
    top, bottom = big * (inner + 0.08), big * (1 - inner - 0.08)
    line = max(2, big // 28)
    draw.rounded_rectangle([left, top, right, bottom], radius=big // 40, outline=WHITE, width=line)
    inset = line * 0.9  # the flap starts inside the frame, no corners stick out
    flap = [(left + inset, top + inset), (big / 2, (top + bottom) / 2), (right - inset, top + inset)]
    draw.line(flap, fill=WHITE, width=line, joint="curve")
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        icon(size, maskable=False).save(OUT / f"icon-{size}.png")
        icon(size, maskable=True).save(OUT / f"icon-{size}-maskable.png")
    icon(180, maskable=True).convert("RGB").save(OUT / "apple-touch-icon.png")  # iOS: no transparency
    print(f"Icons geschrieben nach {OUT}")


if __name__ == "__main__":
    main()
