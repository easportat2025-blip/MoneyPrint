import random
import config

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


GRADE = "eq=contrast=1.06:saturation=1.15,vignette=angle=PI/5,noise=alls=5:allf=t+u"


def variant(seed: str = "") -> str:
    rnd = random.Random(seed or "rezain")
    if rnd.random() < 0.5:
        return "hflip"
    return ""


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
