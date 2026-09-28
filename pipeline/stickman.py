import math
import os
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (247, 245, 239)
INK = (27, 27, 27)
ACCENT = (228, 87, 46)
BLUE = (38, 92, 168)
GREY = (120, 120, 120)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

# normalized figure joints (0-1 of canvas)
POSES = {
    "idle": {
        "head": (0.50, 0.30), "neck": (0.50, 0.38), "hip": (0.50, 0.58),
        "l_elbow": (0.43, 0.46), "l_hand": (0.38, 0.53),
        "r_elbow": (0.57, 0.46), "r_hand": (0.62, 0.53),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "point_l": {
        "head": (0.50, 0.30), "neck": (0.50, 0.38), "hip": (0.50, 0.58),
        "l_elbow": (0.38, 0.44), "l_hand": (0.26, 0.40),
        "r_elbow": (0.58, 0.47), "r_hand": (0.63, 0.55),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "point_r": {
        "head": (0.50, 0.30), "neck": (0.50, 0.38), "hip": (0.50, 0.58),
        "l_elbow": (0.42, 0.47), "l_hand": (0.37, 0.55),
        "r_elbow": (0.62, 0.44), "r_hand": (0.74, 0.40),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "think": {
        "head": (0.50, 0.29), "neck": (0.50, 0.38), "hip": (0.50, 0.58),
        "l_elbow": (0.42, 0.47), "l_hand": (0.41, 0.55),
        "r_elbow": (0.60, 0.42), "r_hand": (0.56, 0.33),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "both_up": {
        "head": (0.50, 0.28), "neck": (0.50, 0.37), "hip": (0.50, 0.58),
        "l_elbow": (0.38, 0.36), "l_hand": (0.32, 0.24),
        "r_elbow": (0.62, 0.36), "r_hand": (0.68, 0.24),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "shrug": {
        "head": (0.50, 0.30), "neck": (0.50, 0.38), "hip": (0.50, 0.58),
        "l_elbow": (0.40, 0.45), "l_hand": (0.34, 0.42),
        "r_elbow": (0.60, 0.45), "r_hand": (0.66, 0.42),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "phone": {
        "head": (0.50, 0.30), "neck": (0.50, 0.38), "hip": (0.50, 0.58),
        "l_elbow": (0.43, 0.47), "l_hand": (0.45, 0.55),
        "r_elbow": (0.57, 0.46), "r_hand": (0.55, 0.53),
        "l_knee": (0.46, 0.72), "l_foot": (0.44, 0.86),
        "r_knee": (0.54, 0.72), "r_foot": (0.56, 0.86),
    },
    "sleep": {
        "head": (0.50, 0.33), "neck": (0.50, 0.41), "hip": (0.50, 0.60),
        "l_elbow": (0.42, 0.50), "l_hand": (0.37, 0.58),
        "r_elbow": (0.58, 0.50), "r_hand": (0.63, 0.58),
        "l_knee": (0.45, 0.74), "l_foot": (0.41, 0.87),
        "r_knee": (0.55, 0.74), "r_foot": (0.60, 0.87),
    },
}


def _font(size: int):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _lerp_pose(a: dict, b: dict, t: float) -> dict:
    out = {}
    for k in a:
        x = a[k][0] + (b[k][0] - a[k][0]) * t
        y = a[k][1] + (b[k][1] - a[k][1]) * t
        out[k] = (x, y)
    return out


def _jitter(rnd: random.Random, amp: float) -> float:
    return rnd.uniform(-amp, amp)


def _stroke(d: ImageDraw.ImageDraw, pts, w: int, rnd, amp: float, color=INK):
    j = [(x + _jitter(rnd, amp), y + _jitter(rnd, amp)) for x, y in pts]
    d.line(j, fill=color, width=w, joint="curve")
    for x, y in (j[0], j[-1]):
        r = w / 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _draw_figure(d: ImageDraw.ImageDraw, pose: dict, w: int, h: int, lw: int, rnd):
    def P(k):
        x, y = pose[k]
        return (x * w, y * h)

    head = P("head")
    hr = w * 0.048
    d.ellipse((head[0] - hr, head[1] - hr, head[0] + hr, head[1] + hr), outline=INK, width=lw)
    _stroke(d, [P("neck"), P("hip")], lw, rnd, w * 0.0012)
    _stroke(d, [P("neck"), P("l_elbow"), P("l_hand")], lw, rnd, w * 0.0012)
    _stroke(d, [P("neck"), P("r_elbow"), P("r_hand")], lw, rnd, w * 0.0012)
    _stroke(d, [P("hip"), P("l_knee"), P("l_foot")], lw, rnd, w * 0.0012)
    _stroke(d, [P("hip"), P("r_knee"), P("r_foot")], lw, rnd, w * 0.0012)
    for k in ("l_hand", "r_hand"):
        x, y = P(k)
        r = lw * 0.75
        d.ellipse((x - r, y - r, x + r, y + r), fill=INK)


PROP_POSE = {
    "phone": ("phone", "phone"),
    "sleep": ("bed", "sleep"),
    "z": ("zzz", "sleep"),
    "money": ("coins", "both_up"),
    "coin": ("coins", "both_up"),
    "food": ("bowl", "point_r"),
    "eat": ("bowl", "point_r"),
    "brain": ("brain", "think"),
    "mind": ("brain", "think"),
    "water": ("drop", "point_l"),
    "screen": ("monitor", "phone"),
    "computer": ("monitor", "phone"),
    "work": ("monitor", "phone"),
    "book": ("book", "point_r"),
    "study": ("book", "point_r"),
    "run": ("motion", "point_l"),
    "cold": ("snow", "shrug"),
    "heat": ("sun", "shrug"),
    "eye": ("eye", "point_l"),
    "heart": ("heart", "both_up"),
    "teeth": ("tooth", "point_r"),
    "light": ("bulb", "think"),
    "idea": ("bulb", "both_up"),
    "time": ("clock", "point_l"),
    "clock": ("clock", "point_l"),
}


def _pick_prop(text: str) -> tuple[str, str]:
    low = (text or "").lower()
    best = ("bulb", "think")
    best_pos = 10**9
    for key, (prop, pose) in PROP_POSE.items():
        p = low.find(key)
        if p >= 0 and p < best_pos:
            best = (prop, pose)
            best_pos = p
    return best


def _transform(pose: dict, fx: float = 0.5, fy: float = 0.52, pz: float = 1.0) -> dict:
    return {
        k: (fx + (v[0] - 0.5) * pz, fy + (v[1] - 0.52) * pz) for k, v in pose.items()
    }


def _draw_prop(d, name, w, h, lw, rnd, side, cx=None, cy=None, pz=1.0):
    if cx is None:
        cx = w * (0.78 if side > 0 else 0.22)
    if cy is None:
        cy = h * 0.36
    S = pz
    if name == "phone":
        pw, ph = w * 0.11, h * 0.19
        d.rounded_rectangle(
            (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2),
            radius=w * 0.014, outline=INK, width=lw,
        )
        d.line((cx - pw * 0.28, cy + ph * 0.42, cx + pw * 0.28, cy + ph * 0.42), fill=INK, width=lw)
    elif name == "monitor":
        pw, ph = w * 0.26, h * 0.16
        d.rounded_rectangle((cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2), radius=w * 0.01, outline=INK, width=lw)
        d.line((cx, cy + ph / 2, cx, cy + ph / 2 + h * 0.05), fill=INK, width=lw)
        d.line((cx - w * 0.05, cy + ph / 2 + h * 0.05, cx + w * 0.05, cy + ph / 2 + h * 0.05), fill=INK, width=lw)
    elif name == "bed":
        bw, bh = w * 0.24, h * 0.07
        d.line((cx - bw / 2, cy, cx + bw / 2, cy), fill=INK, width=lw)
        d.line((cx - bw / 2, cy, cx - bw / 2, cy - bh), fill=INK, width=lw)
        d.ellipse((cx - bw / 2 + w * 0.02, cy - bh * 1.5, cx - bw / 2 + w * 0.10, cy - bh * 0.5), outline=INK, width=lw)
    elif name == "zzz":
        f = _font(int(w * 0.075))
        for i, ch in enumerate("ZZZ"):
            d.text((cx + i * w * 0.05, cy - i * h * 0.03), ch, font=f, fill=BLUE)
    elif name == "coins":
        for i in range(3):
            r = w * 0.05
            x = cx - w * 0.05 + i * w * 0.02
            y = cy - i * h * 0.018
            d.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), outline=INK, width=lw)
    elif name == "bowl":
        r = w * 0.11
        d.arc((cx - r, cy - r * 0.7, cx + r, cy + r * 0.9), 0, 180, fill=INK, width=lw)
        d.line((cx - r * 1.25, cy + r * 0.2, cx + r * 1.25, cy + r * 0.2), fill=INK, width=lw)
    elif name == "brain":
        r = w * 0.09
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK, width=lw)
        d.arc((cx - r * 0.5, cy - r * 0.7, cx + r * 0.6, cy + r * 0.5), 200, 160, fill=INK, width=lw)
    elif name == "drop":
        r = w * 0.06
        d.ellipse((cx - r, cy - r * 0.2, cx + r, cy + r * 1.1), outline=BLUE, width=lw)
        d.line((cx, cy - r * 1.4, cx, cy - r * 0.2), fill=BLUE, width=lw)
    elif name == "book":
        bw, bh = w * 0.14, h * 0.10
        d.line((cx, cy - bh / 2, cx, cy + bh / 2), fill=INK, width=lw)
        d.polygon(
            [(cx, cy - bh / 2), (cx - bw, cy - bh * 0.7), (cx - bw, cy + bh * 0.5), (cx, cy + bh / 2)],
            outline=INK, fill=None,
        )
        d.polygon(
            [(cx, cy - bh / 2), (cx + bw, cy - bh * 0.7), (cx + bw, cy + bh * 0.5), (cx, cy + bh / 2)],
            outline=INK,
        )
    elif name == "clock":
        r = w * 0.10
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK, width=lw)
        d.line((cx, cy, cx, cy - r * 0.6), fill=INK, width=lw)
        d.line((cx, cy, cx + r * 0.45, cy + r * 0.15), fill=ACCENT, width=lw)
    elif name == "bulb":
        r = w * 0.075
        d.ellipse((cx - r, cy - r, cx + r, cy + r * 0.5), outline=ACCENT, width=lw)
        d.line((cx - r * 0.4, cy + r * 0.6, cx + r * 0.4, cy + r * 0.6), fill=INK, width=lw)
        for a in range(0, 360, 45):
            rad = math.radians(a)
            d.line(
                (cx + math.cos(rad) * r * 1.35, cy - r * 0.25 + math.sin(rad) * r * 1.35,
                 cx + math.cos(rad) * r * 1.6, cy - r * 0.25 + math.sin(rad) * r * 1.6),
                fill=ACCENT, width=lw,
            )
    elif name == "sun":
        r = w * 0.085
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ACCENT, width=lw)
        for a in range(0, 360, 30):
            rad = math.radians(a)
            d.line(
                (cx + math.cos(rad) * r * 1.35, cy + math.sin(rad) * r * 1.35,
                 cx + math.cos(rad) * r * 1.7, cy + math.sin(rad) * r * 1.7),
                fill=ACCENT, width=lw,
            )
    elif name == "snow":
        for i in range(3):
            x = cx + (i - 1) * w * 0.07
            y = cy + (i % 2) * h * 0.05
            for a in range(0, 180, 60):
                rad = math.radians(a)
                d.line(
                    (x - math.cos(rad) * w * 0.03, y - math.sin(rad) * w * 0.03,
                     x + math.cos(rad) * w * 0.03, y + math.sin(rad) * w * 0.03),
                    fill=BLUE, width=lw,
                )
    elif name == "eye":
        r = w * 0.10
        d.ellipse((cx - r, cy - r * 0.62, cx + r, cy + r * 0.62), outline=INK, width=lw)
        d.ellipse((cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3), fill=INK)
    elif name == "heart":
        r = w * 0.085
        d.ellipse((cx - r, cy - r * 0.8, cx, cy + r * 0.3), outline=ACCENT, width=lw)
        d.ellipse((cx, cy - r * 0.8, cx + r, cy + r * 0.3), outline=ACCENT, width=lw)
        d.line((cx - r, cy - r * 0.15, cx, cy + r * 0.95), fill=ACCENT, width=lw)
        d.line((cx + r, cy - r * 0.15, cx, cy + r * 0.95), fill=ACCENT, width=lw)
    elif name == "tooth":
        tw, th = w * 0.09, h * 0.11
        d.arc((cx - tw, cy - th, cx + tw, cy + th * 0.4), 200, 340, fill=INK, width=lw)
        d.line((cx - tw, cy - th * 0.2, cx - tw, cy + th * 0.8), fill=INK, width=lw)
        d.line((cx + tw, cy - th * 0.2, cx + tw, cy + th * 0.8), fill=INK, width=lw)
        d.line((cx - tw * 0.35, cy + th * 0.8, cx, cy + th * 1.1), fill=INK, width=lw)
        d.line((cx + tw * 0.35, cy + th * 0.8, cx, cy + th * 1.1), fill=INK, width=lw)
    elif name == "motion":
        for i in range(3):
            y = cy - h * 0.04 + i * h * 0.045
            d.line((cx - w * 0.09, y, cx + w * 0.02, y), fill=BLUE, width=lw)
            d.polygon(
                [(cx + w * 0.07, y), (cx + w * 0.02, y - w * 0.025), (cx + w * 0.02, y + w * 0.025)],
                fill=BLUE,
            )
    elif name == "wifi":
        for i, rr in enumerate((0.04, 0.075, 0.11)):
            d.arc(
                (cx - w * rr, cy - w * rr, cx + w * rr, cy + w * rr),
                200, 340, fill=BLUE, width=lw,
            )
        d.ellipse(
            (cx - w * 0.012, cy - h * 0.004, cx + w * 0.012, cy + h * 0.02),
            fill=BLUE,
        )
    elif name == "battery":
        pw, ph = w * 0.15, h * 0.075
        d.rounded_rectangle(
            (cx - pw / 2, cy - ph / 2, cx + pw * 0.36, cy + ph / 2),
            radius=w * 0.008, outline=INK, width=lw,
        )
        d.line((cx + pw * 0.36, cy - ph * 0.2, cx + pw * 0.5, cy - ph * 0.2), fill=INK, width=lw)
        d.line((cx + pw * 0.36, cy + ph * 0.2, cx + pw * 0.5, cy + ph * 0.2), fill=INK, width=lw)
        d.rectangle(
            (cx - pw * 0.44, cy - ph * 0.26, cx - pw * 0.05, cy + ph * 0.26), fill=ACCENT
        )
    elif name == "car":
        cw, chh = w * 0.20, h * 0.06
        d.rounded_rectangle(
            (cx - cw / 2, cy - chh / 2, cx + cw / 2, cy + chh / 2),
            radius=h * 0.02, outline=INK, width=lw,
        )
        d.polygon(
            [(cx - cw * 0.22, cy - chh / 2), (cx - cw * 0.08, cy - chh * 1.3),
             (cx + cw * 0.16, cy - chh * 1.3), (cx + cw * 0.26, cy - chh / 2)],
            outline=INK,
        )
        for sx in (-1, 1):
            r2 = w * 0.028
            x = cx + sx * cw * 0.28
            d.ellipse((x - r2, cy + chh / 2 - r2, x + r2, cy + chh / 2 + r2), outline=INK, width=lw)
    elif name == "pill":
        pw, ph = w * 0.15, h * 0.07
        d.rounded_rectangle(
            (cx - pw / 2, cy - ph / 2, cx + pw / 2, cy + ph / 2),
            radius=ph / 2, outline=INK, width=lw,
        )
        d.line((cx, cy - ph / 2, cx, cy + ph / 2), fill=ACCENT, width=lw)
    elif name == "chart":
        bw = w * 0.035
        for i, hh in enumerate((0.05, 0.085, 0.065, 0.115)):
            x = cx - w * 0.09 + i * w * 0.055
            d.line((x, cy + h * 0.05, x, cy + h * 0.05 - h * hh), fill=BLUE, width=lw)
        d.line((cx - w * 0.12, cy + h * 0.05, cx + w * 0.12, cy + h * 0.05), fill=INK, width=lw)
    elif name == "city":
        for i, hh in enumerate((0.07, 0.11, 0.08, 0.13, 0.09)):
            x = cx - w * 0.11 + i * w * 0.055
            top = cy + h * 0.05 - h * hh
            d.rectangle((x, top, x + w * 0.042, cy + h * 0.05), outline=INK, width=lw)
            for r2 in range(2):
                for c2 in range(2):
                    d.rectangle(
                        (x + w * 0.008 + c2 * w * 0.016, top + h * 0.014 + r2 * h * 0.022,
                         x + w * 0.018 + c2 * w * 0.016, top + h * 0.026 + r2 * h * 0.022),
                        fill=(190, 185, 175),
                    )
    elif name == "cpu":
        cw = w * 0.11
        d.rectangle((cx - cw / 2, cy - cw / 2, cx + cw / 2, cy + cw / 2), outline=INK, width=lw)
        d.rectangle(
            (cx - cw * 0.22, cy - cw * 0.22, cx + cw * 0.22, cy + cw * 0.22),
            outline=ACCENT, width=lw,
        )
        for i in range(4):
            p = cw * (0.62 + i * 0.22)
            d.line((cx - p / 2, cy - cw / 2, cx - p / 2, cy - cw * 0.78), fill=INK, width=lw)
            d.line((cx + p / 2, cy - cw / 2, cx + p / 2, cy - cw * 0.78), fill=INK, width=lw)
            d.line((cx - p / 2, cy + cw / 2, cx - p / 2, cy + cw * 0.78), fill=INK, width=lw)
            d.line((cx + p / 2, cy + cw / 2, cx + p / 2, cy + cw * 0.78), fill=INK, width=lw)
    else:
        r = w * 0.085
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ACCENT, width=lw)
        d.text((cx - r * 0.6, cy - r * 0.9), "?", font=_font(int(w * 0.11)), fill=ACCENT)


def _draw_panel(d, w, h, lw, rnd, zoom: float, side: int) -> None:
    """Whiteboard panel that appears behind the figure on zoom beats."""
    if zoom <= 1.001:
        return
    pw = w * 0.30 * zoom
    ph = h * 0.14 * zoom
    px = w * (0.70 if side > 0 else 0.30)
    py = h * 0.66
    d.rounded_rectangle(
        (px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2),
        radius=w * 0.012,
        outline=(190, 185, 175),
        width=max(2, lw // 2),
    )


def _draw_watermark(d, tag, w, h, lw):
    if not tag:
        return
    f = _font(int(w * 0.030))
    d.text((w * 0.045, h * 0.028), tag, font=f, fill=GREY)


def render(
    scenes: list,
    out_path: Path,
    w: int = 1080,
    h: int = 1920,
    fps: int = 30,
    seconds_per_scene: float = 3.0,
    watermark: str = "",
    keyframes: set | None = None,
) -> Path:
    scenes = list(scenes) or [{"narration": "", "caption": ""}]
    if keyframes is None:
        keys = set(range(len(scenes)))
    else:
        keys = set(keyframes) | {0, len(scenes) - 1}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lw = max(3, int(w * 0.0068))
    rnd = random.Random(7)
    frame_count = max(int(len(scenes) * seconds_per_scene * fps), fps)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    rnd2 = random.Random(11)
    layouts = []
    last_fx, last_side = 0.5, 1
    for si in range(len(scenes)):
        if si in keys:
            reveal = (si % 3 == 2)
            last_fx = rnd2.choice([0.38, 0.42, 0.5, 0.58, 0.62])
            last_side = 1 if si % 2 == 0 else -1
            layouts.append(
                {
                    "fx": last_fx,
                    "side": last_side,
                    "pz": rnd2.uniform(1.12, 1.24) if reveal else 1.0,
                    "key": True,
                }
            )
        else:
            layouts.append({"fx": last_fx, "side": last_side, "pz": 1.0, "key": False})
    try:
        for i in range(frame_count):
            t = i / fps
            si = min(int(t / seconds_per_scene), len(scenes) - 1)
            sc = scenes[si]
            st = t - si * seconds_per_scene
            lay = layouts[si]
            side = lay["side"]
            if lay["key"]:
                prop, pose_name = _pick_prop(
                    (sc.get("caption") or "") + " " + (sc.get("narration") or "")
                )
                seq = [POSES["idle"], POSES[pose_name], POSES["idle"]]
                if st < seconds_per_scene * 0.4:
                    a, b, local = seq[0], seq[1], st / (seconds_per_scene * 0.4)
                elif st < seconds_per_scene * 0.8:
                    a, b, local = (
                        seq[1],
                        seq[2],
                        (st - seconds_per_scene * 0.4) / (seconds_per_scene * 0.4),
                    )
                else:
                    a, b, local = seq[2], seq[0], (st - seconds_per_scene * 0.8) / (seconds_per_scene * 0.2)
                e = 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, local)))
                pose = _lerp_pose(a, b, e)
                bob_amp = 0.0035
            else:
                prop, pose_name = None, "idle"
                e = 0.0
                pose = dict(POSES["idle"])
                bob_amp = 0.0012
            bob = math.sin(t * 2.2) * bob_amp
            pose = {k: (v[0], v[1] + bob) for k, v in pose.items()}
            zoom_in = 1.0 + (lay["pz"] - 1.0) * e
            pose = _transform(pose, lay["fx"], 0.52, zoom_in)
            pcx = lay["fx"] + (0.78 - 0.5) * zoom_in if side > 0 else lay["fx"] + (0.22 - 0.5) * zoom_in
            pcy = 0.36 + (0.52 - 0.52) * zoom_in
            img = Image.new("RGB", (w, h), BG)
            d = ImageDraw.Draw(img)
            d.line(
                (w * 0.06, h * 0.9, w * 0.94, h * 0.9),
                fill=(205, 200, 190),
                width=max(2, lw // 2),
            )
            if lay["key"]:
                _draw_panel(d, w, h, lw, rnd, zoom_in, side)
                _draw_prop(
                    d, prop, w, h, lw, rnd, side,
                    cx=w * pcx, cy=h * pcy, pz=zoom_in,
                )
            _draw_figure(d, pose, w, h, lw, rnd)
            _draw_watermark(d, watermark, w, h, lw)
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = (proc.stderr.read() or b"").decode("utf-8", errors="replace")
    proc.wait()
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"stickman render failed: {err[-500:]}")
    return out_path
