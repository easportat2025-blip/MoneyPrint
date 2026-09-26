import subprocess
from pathlib import Path
import config


CHARS_PER_SEC = {"en": 14.5, "vi": 16.0}
FALLBACKS = {
    "vi": ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural", "en-US-GuyNeural"],
    "en": ["en-US-GuyNeural", "en-US-AvaMultilingualNeural", "en-US-ChristopherNeural"],
}


def fit_to_cap(text: str, max_sec: float, lang: str = "en") -> tuple[str, int]:
    cps = CHARS_PER_SEC.get(lang, 14.5)
    budget = int(cps * max_sec)
    if len(text) <= budget:
        return text, 0
    parts = [p.strip() for p in text.replace("! ", "!|").replace("? ", "?|").replace(". ", ".|").split("|")]
    kept, total = [], 0
    for p in parts:
        if total + len(p) + 1 > budget:
            break
        kept.append(p)
        total += len(p) + 1
    if not kept:
        cut = text[:budget].rsplit(" ", 1)[0]
        return cut, len(text) - len(cut)
    out = " ".join(kept)
    return out, len(text) - len(out)


def synthesize(
    text: str, out_path: Path, voice: str = None, srt_path: Path | None = None
) -> tuple[Path, str]:
    import config

    voice = voice or config.VOICE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lang = config.LANG
    order = [voice] + [v for v in FALLBACKS.get(lang, []) if v != voice]
    last = ""
    for cand in order:
        cmd = [
            "edge-tts",
            "--voice",
            cand,
            "--text",
            text,
            "--write-media",
            str(out_path),
        ]
        if srt_path is not None:
            cmd += ["--write-subtitles", str(srt_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 2000:
            return out_path, cand
        last = (proc.stderr or "").strip().splitlines()[-1][:160] if proc.stderr else ""
    raise RuntimeError(f"edge-tts failed all voices. last error: {last}")


def trim_leading_silence(path: Path) -> float:
    import subprocess

    tmp = path.with_name(path.stem + "_trim" + path.suffix)
    try:
        before = duration(path)
    except RuntimeError:
        return 0.0
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-af",
        "silenceremove=start_periods=1:start_duration=0.02:start_threshold=-50dB",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "3",
        str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not tmp.exists():
        return 0.0
    try:
        after = duration(tmp)
    except RuntimeError:
        tmp.unlink(missing_ok=True)
        return 0.0
    shift = max(before - after, 0.0)
    if shift < 0.03:
        tmp.unlink(missing_ok=True)
        return 0.0
    tmp.replace(path)
    return shift


def shift_sentences(sentences: list, shift: float) -> list:
    if shift <= 0:
        return sentences
    out = []
    for s in sentences:
        start = round(max(s["start"] - shift, 0.0), 3)
        end = round(max(s["end"] - shift, 0.01), 3)
        if end - start >= 0.05:
            out.append({"start": start, "end": end, "text": s["text"]})
    return out


def _srt_ts(ts: str) -> float:
    ts = ts.replace(",", ":").replace(".", ":")
    parts = [float(p) for p in ts.split(":")]
    while len(parts) < 4:
        parts.insert(0, 0.0)
    h, m, s, ms = parts[-4], parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s + ms / 1000.0


def parse_sentences(srt_path: Path) -> list:
    import re

    if srt_path is None or not srt_path.exists():
        return []
    raw = srt_path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", raw.strip())
    out = []
    for b in blocks:
        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"(.+?)\s*-->\s*(.+)", lines[1])
        if not m:
            continue
        try:
            start, end = _srt_ts(m.group(1)), _srt_ts(m.group(2))
        except ValueError:
            continue
        text = " ".join(lines[2:])
        if text and end > start:
            out.append({"start": start, "end": end, "text": text})
    return out


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
