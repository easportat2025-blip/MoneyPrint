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


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def wrap_title(text: str, width: int = 14, lines: int = 3) -> str:
    words = text.upper().split()
    out, cur = [], ""
    for wd in words:
        trial = f"{cur} {wd}".strip()
        if len(trial) <= width or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = wd
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    return "\n".join(out[:lines])


def overlay_title(clip: Path, text: str, w: int, show_sec: float = 3.0) -> Path:
    txt = clip.parent / "title.txt"
    txt.write_text(wrap_title(text), encoding="utf-8")
    size = 100 if w <= 1080 else 116
    base = (
        f"drawtext=textfile='{txt.as_posix()}':"
        f"fontsize={size}:fontcolor=white:borderw=2:bordercolor=black@0.8:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-140:line_spacing=14:"
        f"enable='between(t,0,{show_sec})'"
    )
    tmp = clip.with_name("clip_00_titled.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip),
        "-vf",
        base,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-an",
        str(tmp),
    ]
    try:
        _run(cmd, timeout=300)
    except RuntimeError:
        cmd[cmd.index("-vf") + 1] = base.replace(f"fontfile={FONT}:", "")
        _run(cmd, timeout=300)
    tmp.replace(clip)
    return clip


def overlay_title_font(clip: Path, text: str, w: int, show_sec: float = 3.0) -> Path:
    txt = clip.parent / "title.txt"
    if w <= 1080:
        txt.write_text(wrap_title(text, width=16, lines=4), encoding="utf-8")
        size = 100
    else:
        txt.write_text(wrap_title(text, width=22, lines=3), encoding="utf-8")
        size = 116
    vf = (
        f"drawtext=textfile='{txt.as_posix()}':fontfile={FONT}:"
        f"fontsize={size}:fontcolor=white:borderw=2:bordercolor=black@0.8:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-140:line_spacing=14:"
        f"enable='between(t,0,{show_sec})'"
    )
    tmp = clip.with_name("clip_00_titled.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(clip),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-an",
        str(tmp),
    ]
    try:
        _run(cmd, timeout=300)
    except RuntimeError:
        return overlay_title(clip, text, w, show_sec)
    tmp.replace(clip)
    return clip


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


def _words_from_sentences(sentences: list, cap: float | None) -> list:
    words = []
    for s in sentences:
        if cap is not None and s["start"] >= cap:
            continue
        end = min(s["end"], cap) if cap is not None else s["end"]
        toks = [t for t in s["text"].split() if t]
        total = sum(len(t) for t in toks) or 1
        dur = max(end - s["start"], 0.2)
        t = s["start"]
        for tok in toks:
            wd = dur * len(tok) / total
            words.append({"w": tok, "start": t, "end": t + wd})
            t += wd
    return words


def _ass_ts(sec: float) -> str:
    ms = max(int(sec * 100), 0)
    h, ms = divmod(ms, 360000)
    m, ms = divmod(ms, 6000)
    s, cs = divmod(ms, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(w: str) -> str:
    return w.replace("{", "").replace("}", "").strip()


def build_karaoke(
    sentences: list, path: Path, kind: str, cap: float | None = None
) -> Path:
    if kind == "short":
        size, margin = 72, 600
    else:
        size, margin = 60, 140
    words = _words_from_sentences(sentences, cap)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
        "SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Karaoke,DejaVu Sans,{size},&H00FFFFFF,&H0000FFFF,"
        f"&H90000000,&H90000000,-1,0,0,0,100,100,0,0,1,3,0,2,40,40,{margin},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    lines = [header]
    for i in range(0, len(words), 4):
        chunk = words[i : i + 4]
        tags = "".join(
            "{\\k%d}%s " % (max(int((x["end"] - x["start"]) * 100), 1), _clean(x["w"]))
            for x in chunk
        ).strip()
        lines.append(
            f"Dialogue: 0,{_ass_ts(chunk[0]['start'])},{_ass_ts(chunk[-1]['end'])},"
            f"Karaoke,,0,0,0,,{tags}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
    return path


def build_burst_srt(
    sentences: list, path: Path, cap: float | None = None
) -> Path:
    def ts(sec: float) -> str:
        ms = max(int(sec * 1000), 0)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    words = _words_from_sentences(sentences, cap)
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    n = 1
    for i in range(0, len(words), 4):
        chunk = words[i : i + 4]
        text = " ".join(_clean(x["w"]) for x in chunk)
        blocks.append(f"{n}\n{ts(chunk[0]['start'])} --> {ts(chunk[-1]['end'])}\n{text}\n")
        n += 1
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def write_srt(scenes: list, durations: list[float], path: Path) -> Path:
    def ts(sec: float) -> str:
        ms = max(int(sec * 1000), 0)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def caption(s: dict) -> str:
        c = (s.get("caption") or "").strip()
        if c:
            return c
        return " ".join((s.get("narration") or "").split()[:14])

    path.parent.mkdir(parents=True, exist_ok=True)
    t = 0.0
    blocks = []
    for i, s in enumerate(scenes):
        d = durations[i] if i < len(durations) else 4.0
        blocks.append(f"{i + 1}\n{ts(t)} --> {ts(t + d)}\n{caption(s)}\n")
        t += d
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def mux_ass(
    video: Path,
    audio: Path,
    ass: Path,
    out: Path,
    max_sec: float | None = None,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ass_esc = str(ass).replace(":", "\\:").replace("'", "")
    vf = f"ass='{ass_esc}',format=yuv420p"
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
        margin = 600
        size = 64
    else:
        margin = 140
        size = 58
    style = (
        "FontName=DejaVu Sans,FontSize={sz},PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H90000000,BorderStyle=1,Outline=3,Shadow=0,"
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
    items: list[tuple[Path, bool, str]],
    audio: Path,
    sentences: list,
    scenes: list,
    voice_dur: float,
    title: str,
    workdir: Path,
    kind: str,
) -> tuple[Path, Path]:
    if kind == "short":
        w, h, fps, cap = (
            config.SHORT_W,
            config.SHORT_H,
            config.SHORT_FPS,
            55.0,
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
    total = min(voice_dur, cap) if cap else voice_dur
    durs = [total / n] * n
    clips = []
    for i, (path, is_video, _url) in enumerate(items):
        if config.kill_requested():
            raise RuntimeError("kill switch on")
        clip = workdir / f"clip_{i:02d}.mp4"
        if is_video:
            fit_clip(path, clip, durs[i], w, h, fps)
        else:
            ken_burns(path, clip, durs[i], w, h, fps)
        if i == 0:
            overlay_title_font(clip, title, w)
        clips.append(clip)
    silent = workdir / "silent.mp4"
    concat_clips(clips, silent)
    if sentences:
        subs = build_karaoke(sentences, workdir / "subs.ass", kind, cap)
        cc = build_burst_srt(sentences, workdir / "cc.srt", cap)
    else:
        subs = None
        cc = write_srt(scenes, durs, workdir / "cc.srt")
    final = workdir / "final.mp4"
    if subs is not None:
        mux_ass(silent, audio, subs, final, max_sec=cap)
    else:
        mux_subs(silent, audio, cc, final, kind, max_sec=cap)
    for c in clips:
        c.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    if kind == "short":
        verify_short(final)
    return final, cc
