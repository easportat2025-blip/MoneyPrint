import random
import config

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def variant(seed: str = "") -> str:
    rnd = random.Random(seed or "rezain")
    parts = []
    if rnd.random() < 0.5:
        parts.append("hflip")
    c = round(rnd.uniform(1.0, 1.15), 2)
    s = round(rnd.uniform(1.0, 1.25), 2)
    parts.append(f"eq=contrast={c}:saturation={s}")
    return ",".join(parts)


def watermark_vf(tag: str = "@ReZain") -> str:
    safe = tag.replace("'", "").replace(":", "")
    return (
        f"drawtext=text='{safe}':fontfile={FONT}:fontsize=40:"
        f"fontcolor=white@0.65:x=w-text_w-40:y=56:borderw=1:bordercolor=black@0.5"
    )


def watermark_fallback(tag: str = "@ReZain") -> str:
    safe = tag.replace("'", "").replace(":", "")
    return (
        f"drawtext=text='{safe}':font='DejaVu Sans':fontsize=40:"
        f"fontcolor=white@0.65:x=w-text_w-40:y=56:borderw=1"
    )
