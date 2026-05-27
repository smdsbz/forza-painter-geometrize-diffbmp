from PIL import Image, ImageDraw
from pathlib import Path
import math

CANVAS = 256
PAD = 0  # no padding, fill canvas edge-to-edge

BASE = Path("primitives")


def square(size_w: int, size_h: int) -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x0 = (CANVAS - size_w) // 2
    y0 = (CANVAS - size_h) // 2
    draw.rectangle([x0, y0, x0 + size_w - 1, y0 + size_h - 1], fill=(0, 0, 0, 255))
    return img


def circle(size_w: int, size_h: int) -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x0 = (CANVAS - size_w) // 2
    y0 = (CANVAS - size_h) // 2
    draw.ellipse([x0, y0, x0 + size_w - 1, y0 + size_h - 1], fill=(0, 0, 0, 255))
    return img


def isosceles(size_w: int, size_h: int) -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = CANVAS // 2
    top_y = (CANVAS - size_h) // 2
    bot_y = top_y + size_h - 1
    left_x = cx - size_w // 2
    right_x = left_x + size_w - 1
    draw.polygon([(cx, top_y), (left_x, bot_y), (right_x, bot_y)], fill=(0, 0, 0, 255))
    return img


def right_triangle(size_w: int, size_h: int) -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = CANVAS // 2
    cy = CANVAS // 2
    half_w = size_w // 2
    half_h = size_h // 2
    left_x = cx - half_w
    bot_y = cy + half_h
    # right angle at bottom-left ┌
    a = (left_x,                bot_y)              # bottom-left  = right angle
    b = (left_x,                bot_y - size_h + 1)  # top-left     (vertical edge ↑)
    c = (left_x + size_w - 1,   bot_y)              # bottom-right (horizontal edge →)
    draw.polygon([a, b, c], fill=(0, 0, 0, 255))
    return img


def generate():
    ratios = {
        "square":  [(1, w) for w in [1, 4, 8]],                     # 1x1, 1x4, 1x8
        "circle":  [(1, w) for w in [1, 4, 8]],                     # 1x1, 1x4, 1x8
        "triangle-isosceles": [(w, 1) for w in [16, 8, 4]]            # 16x1, 8x1, 4x1
                             + [(1, 1)]
                             + [(1, w) for w in [4, 8, 16]],           # 1x4, 1x8, 1x16
        "triangle-right":    [(w, 1) for w in [16, 8, 4]]            # 16x1, 8x1, 4x1
                             + [(1, 1)]
                             + [(1, w) for w in [4, 8, 16]],           # 1x4, 1x8, 1x16
    }

    generators = {
        "square": square,
        "circle": circle,
        "triangle-isosceles": isosceles,
        "triangle-right": right_triangle,
    }

    total = 0
    for folder, rlist in ratios.items():
        gen = generators[folder]
        for w_r, h_r in rlist:
            # Max shape size within canvas, preserving aspect ratio
            max_w = CANVAS - 2 * PAD
            max_h = CANVAS - 2 * PAD
            # Determine which axis is the limiting axis
            scale = min(max_w / w_r, max_h / h_r)
            size_w = int(w_r * scale)
            size_h = int(h_r * scale)
            # Ensure at least 1 pixel
            size_w = max(1, size_w)
            size_h = max(1, size_h)
            # Snap to odd or even consistently
            fname = f"{w_r}x{h_r}.png"
            path = BASE / folder / fname
            path.parent.mkdir(parents=True, exist_ok=True)
            img = gen(size_w, size_h)
            img.save(path)
            total += 1

    print(f"Generated {total} PNGs under {BASE.resolve()}")


def main() -> None:
    generate()


if __name__ == "__main__":
    main()
