import random
import config

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


GRADE = (
    "eq=contrast=1.05:saturation=1.12:gamma=1.02,"
    "unsharp=3:3:0.4,"
    "vignette=angle=PI/5,"
    "noise=alls=4:allf=t+u"
)


def variant(seed: str = "") -> str:
    rnd = random.Random(seed or "rezain")
    if rnd.random() < 0.35:
        return "hflip"
    return ""


def _font_file(*names: str) -> str:
    for n in names:
        if (config.ROOT / "assets" / "fonts" / n).exists():
            return "assets/fonts/" + n
    return ""


def watermark_vf(tag: str = "") -> str:
    safe = (tag or config.WATERMARK).replace("'", "").replace(":", "")
    if not safe:
        return "null"
    f = _font_file("Poppins-SemiBold.ttf") or FONT
    return (
        f"drawtext=text='{safe}':fontfile={f}:fontsize=38:"
        "box=1:boxcolor=black@0.38:boxborderw=14:"
        "fontcolor=white@0.88:x=w-text_w-40:y=52"
    )


def watermark_fallback(tag: str = "") -> str:
    safe = (tag or config.WATERMARK).replace("'", "").replace(":", "")
    if not safe:
        return "null"
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=38:"
        "box=1:boxcolor=black@0.38:boxborderw=14:"
        "fontcolor=white@0.85:x=w-text_w-40:y=52"
    )


def _wrap(text: str, per_line: int = 15, max_lines: int = 3) -> list:
    words = str(text).split()
    lines, cur = [], ""
    for wd in words:
        cand = (cur + " " + wd).strip()
        if len(cand) > per_line and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def hook_vf(text: str, font: str = "") -> str:
    """Tieu de lon 3 giay dau - giu nguoi xem khong luot.

    Toa do dung bieu thuc ffmpeg ((h-text_h)/2) nen chay dung o ca
    1080x1920 va 1920x1080; enable='lt(t,3)' bat buoc.
    """
    if not text:
        return "null"
    lines = _wrap(text, 16 if text.isascii() else 13, 3)
    if not lines:
        return "null"
    f = _font_file("Anton-Regular.ttf") or font or FONT
    big = {1: 94, 2: 84, 3: 72}.get(len(lines), 72)
    step = int(big * 1.2)
    total = big * len(lines) + step * (len(lines) - 1)
    top = f"(h-{total})/2"
    accent = (config.ACCENT or "0xFFD700").replace("#", "")
    parts = [
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.32:t=fill:enable='lt(t\\,3.0)'",
        (
            f"drawbox=x='(iw-iw*0.16)/2':y={top}+{total}+26:w='iw*0.16':h=10:"
            f"color={accent}@0.95:t=fill:enable='lt(t\\,3.0)'"
        ),
    ]
    for i, ln in enumerate(lines):
        safe = ln.replace("'", "").replace(":", "").replace("\\", "")[:34]
        yy = f"{top}+{i * step}" if i else top
        parts.append(
            f"drawtext=text='{safe}':fontfile={f}:fontsize={big}:"
            "fontcolor=white:alpha='min(1\\,t/0.4)':"
            "borderw=7:bordercolor=black@0.92:"
            "shadowcolor=black@0.7:shadowx=0:shadowy=7:"
            f"x=(w-text_w)/2:y={yy}:enable='lt(t\\,3.0)'"
        )
    return ",".join(parts)


def hook_fallback(text: str) -> str:
    if not text:
        return "null"
    lines = _wrap(text, 16, 1)
    if not lines:
        return "null"
    safe = lines[0].replace("'", "").replace(":", "")[:30]
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=80:fontcolor=white:"
        f"borderw=6:bordercolor=black@0.92:x=(w-text_w)/2:y=(h-text_h)/2"
        f":enable='lt(t\\,3.0)'"
    )
