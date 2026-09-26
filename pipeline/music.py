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
VOICE_CHAIN = (
    "highpass=f=120,"
    "equalizer=f=3000:t=q:w=1:g=1.5,"
    "dynaudnorm=f=150:g=7"
)


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


def _voice_dur(voice: Path) -> float:
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(voice),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return float(proc.stdout.strip())
    except (ValueError, subprocess.SubprocessError):
        return 60.0


def mix(
    voice: Path, out: Path, seed: str = "", delay_ms: int = 0
) -> tuple[Path, str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    track, credit = pick(seed)
    dur = _voice_dur(voice)
    fade_st = max(dur + 1.0 - 0.8, 0.5)
    tail = (
        f"afade=t=in:st=0:d=0.05,apad=pad_dur=1.0,"
        f"afade=t=out:st={fade_st:.2f}:d=0.8,alimiter=limit=0.891[aout]"
    )
    if track is None:
        fc = f"[0:a]{VOICE_CHAIN},{tail}"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(voice),
            "-filter_complex",
            fc,
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            str(out),
        ]
        if delay_ms:
            cmd[cmd.index("-filter_complex") + 1] = (
                f"[0:a]{VOICE_CHAIN},adelay={delay_ms}|{delay_ms},{tail}"
            )
        _run(cmd)
        return out, ""
    fc = (
        f"[0:a]{VOICE_CHAIN},asplit[v1][v2];"
        f"[1:a]volume={MUSIC_VOL},highpass=f=80[m];"
        f"[m][v2]sidechaincompress=threshold=0.02:ratio=8:attack=200:release=500[d];"
        f"[v1][d]amix=inputs=2:duration=first:dropout_transition=0[mx];"
        f"[mx]{tail}"
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
        "[aout]",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        str(out),
    ]
    _run(cmd)
    return out, credit
