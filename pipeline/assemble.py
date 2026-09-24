import subprocess
from pathlib import Path
import config


def _run(cmd: list[str], timeout: int = 1200) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {cmd[:5]}\n{proc.stderr[-800:]}")


def probe(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    out = {"width": 0, "height": 0, "duration": 0.0}
    for line in proc.stdout.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "width":
            out["width"] = int(float(v))
        elif k == "height":
            out["height"] = int(float(v))
        elif k == "duration" and out["duration"] == 0.0:
            try:
                out["duration"] = float(v)
            except ValueError:
                pass
    return out


def ken_burns(image: Path, out: Path, seconds: float, w: int, h: int, fps: int) -> Path:
    frames = max(int(seconds * fps), fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={w * 2}:-2,"
        f"zoompan=z='min(1.0+0.0012*on,1.18)'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        "format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image),
        "-vf",
        vf,
        "-t",
        f"{seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-r",
        str(fps),
        "-an",
        str(out),
    ]
    _run(cmd, timeout=600)
    return out


def fit_clip(src: Path, out: Path, seconds: float, w: int, h: int, fps: int) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    pre: list[str] = []
    if info["duration"] and info["duration"] < seconds:
        pre = ["-stream_loop", "3"]
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        *pre,
        "-i",
        str(src),
        "-vf",
        vf,
        "-t",
        f"{seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-r",
        str(fps),
        "-an",
        str(out),
    ]
    _run(cmd, timeout=600)
    return out


def concat_clips(clips: list[Path], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    list_file = out.with_suffix(".txt")
    list_file.write_text(
        "".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(out),
    ]
    _run(cmd)
    list_file.unlink(missing_ok=True)
    return out


def write_srt(scenes: list, durations: list[float], path: Path) -> Path:
    def ts(sec: float) -> str:
        ms = int(sec * 1000)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def caption(s: dict) -> str:
        c = (s.get("caption") or "").strip()
        if c:
            return c
        words = (s.get("narration") or "").split()
        return " ".join(words[:14])

    path.parent.mkdir(parents=True, exist_ok=True)
    t = 0.0
    blocks = []
    for i, s in enumerate(scenes):
        d = durations[i] if i < len(durations) else 4.0
        blocks.append(f"{i + 1}\n{ts(t)} --> {ts(t + d)}\n{caption(s)}\n")
        t += d
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def mux_subs(
    video: Path,
    audio: Path,
    srt: Path,
    out: Path,
    kind: str,
    max_sec: float | None = None,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if kind == "short":
        margin = 320
        size = 58
    else:
        margin = 120
        size = 56
    style = (
        "FontName=DejaVu Sans,FontSize={sz},PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H90000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV={mg}".format(sz=size, mg=margin)
    )
    srt_esc = str(srt).replace(":", "\\:").replace("'", "")
    vf = f"subtitles='{srt_esc}':force_style='{style}',format=yuv420p"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
    ]
    if max_sec:
        cmd += ["-t", f"{max_sec:.3f}"]
    cmd.append(str(out))
    _run(cmd, timeout=1800)
    return out


def verify_short(path: Path) -> dict:
    info = probe(path)
    w, h, d = info["width"], info["height"], info["duration"]
    problems = []
    if h <= w:
        problems.append(f"not vertical ({w}x{h})")
    if d > 61:
        problems.append(f"too long ({d:.1f}s > 60s, not a Short)")
    if problems:
        raise RuntimeError("short verify failed: " + "; ".join(problems))
    return info


def assemble(
    items: list[tuple[Path, bool]],
    audio: Path,
    scenes: list,
    audio_dur: float,
    workdir: Path,
    kind: str,
) -> Path:
    if kind == "short":
        w, h, fps, cap = (
            config.SHORT_W,
            config.SHORT_H,
            config.SHORT_FPS,
            58.0,
        )
    else:
        w, h, fps, cap = (
            config.LONG_W,
            config.LONG_H,
            config.LONG_FPS,
            None,
        )
    workdir.mkdir(parents=True, exist_ok=True)
    n = len(items)
    total = min(audio_dur, cap) if cap else audio_dur
    durs = [total / n] * n
    clips = []
    for i, (path, is_video) in enumerate(items):
        if config.kill_requested():
            raise RuntimeError("kill switch on")
        clip = workdir / f"clip_{i:02d}.mp4"
        if is_video:
            fit_clip(path, clip, durs[i], w, h, fps)
        else:
            ken_burns(path, clip, durs[i], w, h, fps)
        clips.append(clip)
    silent = workdir / "silent.mp4"
    concat_clips(clips, silent)
    srt = write_srt(scenes, durs, workdir / "subs.srt")
    final = workdir / "final.mp4"
    mux_subs(silent, audio, srt, final, kind, max_sec=cap)
    for c in clips:
        c.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    if kind == "short":
        verify_short(final)
    return final
