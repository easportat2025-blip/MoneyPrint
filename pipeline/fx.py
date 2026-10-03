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


def hook_vf(text: str, font: str) -> str:
    """Tieu de lon 3 giay dau - giu nguoi xem khong luot.

    Video nao cung bat dau bang mot cuc hinh anh trung tinh (tu marble bat
    huu, phong trang) - khong co gi khiến người ta dừng lại. Tieu de to dat
    3 giay dau la thu giu nguoi xem lai.

    Toa do dung bieu thuc ffmpeg ((h-text_h)/2) nen chay dung o ca
    1080x1920 va 1920x1080.
    """
    if not text:
        return "null"
    lines = [s.strip() for s in str(text).split("\n") if s.strip()][:3]
    if not lines:
        return "null"
    big = 84 if len(lines) == 1 else 72
    step = big + 26
    total = big * len(lines) + step * (len(lines) - 1)
    top = f"(h-{total})/2"
    parts = [
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.32:t=fill:enable='lt(t\\,3.0)'"
    ]
    for i, ln in enumerate(lines):
        safe = ln.replace("'", "").replace(":", "").replace("\\", "")[:46]
        yy = f"({top}+{i * step})" if i else top
        parts.append(
            f"drawtext=text='{safe}':fontfile={font}:fontsize={big}:"
            f"fontcolor=white:borderw=7:bordercolor=black@0.92:"
            f"x=(w-text_w)/2:y={yy}"
        )
    return ",".join(parts)


def hook_fallback(text: str) -> str:
    if not text:
        return "null"
    safe = str(text).split("\n")[0].strip().replace("'", "").replace(":", "")[:46]
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=84:fontcolor=white:"
        f"borderw=7:bordercolor=black@0.92:x=(w-text_w)/2:y=(h-text_h)/2"
    )
