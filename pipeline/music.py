import random
import subprocess
from pathlib import Path
import config

TRACKS = [
    (
        "assets/music/isolated.ogg",
        "Isolated by Kevin MacLeod (incompetech.com), licensed CC-BY 4.0",
    ),
    (
        "assets/music/nothing_broken.ogg",
        "Nothing Broken by Kevin MacLeod (incompetech.com), licensed CC-BY 4.0",
    ),
]

MUSIC_VOL = 0.20


def pick(seed: str = "") -> tuple[Path | None, str]:
    cands = [
        (config.ROOT / p, credit) for p, credit in TRACKS if (config.ROOT / p).exists()
    ]
    if not cands:
        return None, ""
    rnd = random.Random(seed or "rezain")
    return rnd.choice(cands)


def _run(cmd: list[str], timeout: int = 600) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"music mix failed:\n{proc.stderr[-600:]}")


def mix(
    voice: Path, out: Path, seed: str = "", delay_ms: int = 0
) -> tuple[Path, str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    track, credit = pick(seed)
    if track is None:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(voice),
            "-af",
            f"adelay={delay_ms}|{delay_ms}",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(out),
        ]
        _run(cmd)
        return out, ""
    fc = (
        f"[1:a]volume={MUSIC_VOL},apad[m];"
        f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a];"
        f"[a]adelay={delay_ms}|{delay_ms}[out]"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(voice),
        "-stream_loop",
        "-1",
        "-i",
        str(track),
        "-filter_complex",
        fc,
        "-map",
        "[out]",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        str(out),
    ]
    _run(cmd)
    return out, credit
