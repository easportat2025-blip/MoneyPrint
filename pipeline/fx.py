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


def hook_vf(text: str, font: str, w: int = 1080) -> str:
    """Tieu de lon 3 giay dau - giu người xem không lướt.

    Khong co tieu de o 3 giay dau thi video mo dau bang mot tu anh
    marble bat huu khong, khong co gi khiến người ta dừng lại.
    """
    if not text:
        return "null"
    lines = [s for s in str(text).split("\n") if s.strip()][:3]
    if not lines:
        return "null"
    big = 84 if len(lines) == 1 else 72
    y0 = (h - big * (len(lines) + 1)) // 2
    parts = []
    for i, ln in enumerate(lines):
        safe = ln.replace("'", "").replace(":", "").replace("\\", "")[:46]
        yy = y0 + i * (big + 26)
        parts.append(
            f"drawtext=text='{safe}':fontfile={font}:fontsize={big}:"
            f"fontcolor=white:borderw=7:bordercolor=black@0.92:"
            f"x=(w-text_w)/2:y={yy}:line_spacing=10"
        )
    parts.append(
        f"drawbox=x=0:y=0:w={w}:h=ih:color=black@0.30:t=fill:enable='lt(t\\,3.0)'"
    )
    return ",".join(parts)


def hook_fallback(text: str) -> str:
    if not text:
        return "null"
    safe = str(text).split("\n")[0].replace("'", "").replace(":", "")[:46]
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=84:fontcolor=white:"
        f"borderw=7:bordercolor=black@0.92:x=(w-text_w)/2:y=(h-text_h)/2"
    )
