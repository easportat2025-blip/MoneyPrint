"""Preview keyframe mode: strip of key vs calm frames (no ffmpeg needed)."""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import stickman

SCENES = [
    {"narration": "Ban co biet nao ban ngu 8 tieng van thay met?", "caption": "Ngu 8 tieng van met"},
    {"narration": "Vi giac ngu cua ban bi cat vun boi anh sang xanh.", "caption": "Anh sang xanh"},
    {"narration": "Dien thoai khien nao tuong dang ban ngay.", "caption": "Nao tuong ban ngay"},
    {"narration": "Melatonin, hormone gay buon ngu, bi chan dung.", "caption": "Melatonin bi chan"},
    {"narration": "Chi can tat man hinh 1 tieng truoc khi ngu.", "caption": "Tat man hinh 1h"},
]


def draw_frame(sc, key, t, w=300, h=533):
    lw = 6
    rnd = random.Random(3)
    img = Image.new("RGB", (w, h), stickman.BG)
    d = ImageDraw.Draw(img)
    d.line((w * 0.06, h * 0.9, w * 0.94, h * 0.9), fill=(205, 200, 190), width=3)
    fx, side = 0.5, 1
    if key:
        prop, pose_name = stickman._pick_prop(sc["caption"] + " " + sc["narration"])
        e = 0.5 - 0.5 * math.cos(math.pi * min(1.0, t / 1.2))
        pose = stickman._lerp_pose(stickman.POSES["idle"], stickman.POSES[pose_name], e)
        pose = stickman._transform(pose, fx, 0.52, 1.0 + 0.15 * e)
        stickman._draw_panel(d, w, h, lw, rnd, 1.15, side)
        stickman._draw_prop(d, prop, w, h, lw, rnd, side, cx=w * 0.78, cy=h * 0.36, pz=1.15)
    else:
        pose = dict(stickman.POSES["idle"])
        bob = math.sin(1.0 * 2.2) * 0.0012
        pose = {k: (v[0], v[1] + bob) for k, v in pose.items()}
        pose = stickman._transform(pose, fx, 0.52, 1.0)
    stickman._draw_figure(d, pose, w, h, lw, rnd)
    return img


def main():
    from runner import pick_keyframes

    keys = pick_keyframes(len(SCENES), 3)
    print("keyframes:", sorted(keys))
    cols, w, h = len(SCENES), 300, 533
    img = Image.new("RGB", (w * cols, h), stickman.BG)
    for si, sc in enumerate(SCENES):
        tile = draw_frame(sc, si in keys, 0.9)
        d = ImageDraw.Draw(tile)
        tag = "KEY" if si in keys else "calm"
        d.text((10, 8), tag, fill=(228, 87, 46) if si in keys else (150, 150, 150))
        img.paste(tile, (si * w, 0))
    out = Path("cache/stickman_keyframes.png")
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    print("ok ->", out)


if __name__ == "__main__":
    main()
