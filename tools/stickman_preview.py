"""Local preview: render stickman pose/prop grid as PNG (no ffmpeg needed)."""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import stickman

PROPS = [
    ("bulb", "think"), ("phone", "phone"), ("coins", "both_up"),
    ("bowl", "point_r"), ("brain", "think"), ("drop", "point_l"),
    ("monitor", "phone"), ("book", "point_r"), ("zzz", "sleep"),
    ("clock", "point_l"), ("heart", "both_up"), ("motion", "point_l"),
]


def grid(out: Path, cols: int = 4, w: int = 300, h: int = 533) -> Path:
    lw = 6
    rows = (len(PROPS) + cols - 1) // cols
    img = Image.new("RGB", (w * cols, h * rows), stickman.BG)
    for i, (prop, pose) in enumerate(PROPS):
        tile = Image.new("RGB", (w, h), stickman.BG)
        d = ImageDraw.Draw(tile)
        d.line((w * 0.08, h * 0.9, w * 0.92, h * 0.9), fill=(205, 200, 190), width=3)
        stickman._draw_prop(d, prop, w, h, lw, random.Random(i), 1)
        stickman._draw_figure(d, stickman.POSES[pose], w, h, lw, random.Random(i))
        stickman._draw_watermark(d, "@rescey", w, h, lw)
        img.paste(tile, ((i % cols) * w, (i // cols) * h))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


if __name__ == "__main__":
    for p in (grid(Path("cache/stickman_a.png")), grid(Path("cache/stickman_b.png"))):
        print("ok ->", p)
