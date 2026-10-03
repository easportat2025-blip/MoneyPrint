import random
import config

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


GRADE = "eq=contrast=1.06:saturation=1.15,vignette=angle=PI/5,noise=alls=5:allf=t+u"


def variant(seed: str = "") -> str:
    rnd = random.Random(seed or "rezain")
    if rnd.random() < 0.5:
        return "hflip"
    return ""


def watermark_vf(tag: str = "") -> str:
    safe = (tag or config.WATERMARK).replace("'", "").replace(":", "")
    if not safe:
        return "null"
    return (
        f"drawtext=text='{safe}':fontfile={FONT}:fontsize=44:"
        f"fontcolor=white@0.55:x=w-text_w-44:y=64:borderw=2:bordercolor=black@0.45"
    )


def watermark_fallback(tag: str = "") -> str:
    safe = (tag or config.WATERMARK).replace("'", "").replace(":", "")
    if not safe:
        return "null"
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=44:"
        f"fontcolor=white@0.55:x=w-text_w-44:y=64:borderw=2"
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


def hook_vf(text: str, font: str) -> str:
    """Tieu de lon 3 giay dau - giu nguoi xem khong luot.

    Video nao cung bat dau bang mot cuc hinh anh trung tinh (tu marble bat
    huu, phong trang) - khong co gi khiến người ta dừng lại.

    Toa do dung bieu thuc ffmpeg ((h-text_h)/2) nen chay dung o ca
    1080x1920 va 1920x1080. enable='lt(t,3)' bat buoc - truoc day drawtext
    khong co enable nen tieu de cu nguyen tren man hinh ca video.
    """
    if not text:
        return "null"
    lines = _wrap(text, 15 if text.isascii() else 11, 3)
    if not lines:
        return "null"
    big = {1: 76, 2: 62, 3: 54}.get(len(lines), 54)
    step = int(big * 1.25)
    total = big * len(lines) + step * (len(lines) - 1)
    top = f"(h-{total})/2"
    parts = [
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.34:t=fill:enable='lt(t\\,3.0)'"
    ]
    for i, ln in enumerate(lines):
        safe = ln.replace("'", "").replace(":", "").replace("\\", "")[:30]
        yy = f"({top}+{i * step})" if i else top
        parts.append(
            f"drawtext=text='{safe}':fontfile={font}:fontsize={big}:"
            f"fontcolor=white:borderw=6:bordercolor=black@0.92:"
            f"x=(w-text_w)/2:y={yy}:enable='lt(t\\,3.0)'"
        )
    return ",".join(parts)


def hook_fallback(text: str) -> str:
    if not text:
        return "null"
    lines = _wrap(text, 15, 1)
    if not lines:
        return "null"
    safe = lines[0].replace("'", "").replace(":", "")[:30]
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=76:fontcolor=white:"
        f"borderw=6:bordercolor=black@0.92:x=(w-text_w)/2:y=(h-text_h)/2"
        f":enable='lt(t\\,3.0)'"
    )
