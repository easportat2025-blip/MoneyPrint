import subprocess
from pathlib import Path
import config


def synthesize(text: str, out_path: Path, voice: str = None) -> Path:
    voice = voice or config.VOICE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "edge-tts",
        "--voice",
        voice,
        "--text",
        text,
        "--write-media",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"edge-tts failed: {proc.stderr[-500:]}")
    return out_path


def duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    try:
        return float(proc.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}") from e
