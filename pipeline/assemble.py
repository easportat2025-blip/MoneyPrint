import random
import subprocess
from pathlib import Path
import config
from pipeline import fx as fx_mod

FADE = 0.4
FADE_LONG = 0.55

KB_PATTERNS = (
    "punch", "in", "out", "pan_right", "in_right",
    "pan_left", "in_up", "out", "pan_down", "in",
)


def _kb_filter(pattern: str, frames: int, w: int, h: int, fps: int) -> str:
    p = max(frames, 2)
    if pattern == "punch":
        z = f"min(1.0+{(0.30 / p):.6f}*on,1.30)"
    elif pattern == "in":
        z = f"min(1.0+{(0.20 / p):.6f}*on,1.20)"
    elif pattern == "out":
        z = f"max(1.24-{(0.22 / p):.6f}*on,1.02)"
    else:
        z = "1.14"
    geo = {
        "pan_right": (f"(iw-iw/zoom)*(on/{p})", "(ih-ih/zoom)*0.5"),
        "pan_left": (f"(iw-iw/zoom)*(1-on/{p})", "(ih-ih/zoom)*0.5"),
        "pan_up": ("(iw-iw/zoom)*0.5", f"(ih-ih/zoom)*(1-on/{p})"),
        "pan_down": ("(iw-iw/zoom)*0.5", f"(ih-ih/zoom)*(on/{p})"),
        "in_right": ("(iw-iw/zoom)*0.85", "(ih-ih/zoom)*0.5"),
        "in_left": ("(iw-iw/zoom)*0.15", "(ih-ih/zoom)*0.5"),
        "in_up": ("(iw-iw/zoom)*0.5", "(ih-ih/zoom)*0.15"),
        "in_down": ("(iw-iw/zoom)*0.5", "(ih-ih/zoom)*0.85"),
    }.get(pattern, ("(iw-iw/zoom)*0.5", "(ih-ih/zoom)*0.5"))
    return (
        f"zoompan=z='{z}':x='{geo[0]}':y='{geo[1]}'"
        f":d={frames}:s={w}x{h}:fps={fps}"
    )


def _enc() -> list:
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", config.FF_CRF]


FASTSTART = ["-movflags", "+faststart"]


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


def ken_burns(
    image: Path,
    out: Path,
    seconds: float,
    w: int,
    h: int,
    fps: int,
    extra: str = "",
    pattern: str = "in",
) -> Path:
    frames = max(int(seconds * fps), fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    tail = f",{extra}" if extra else ""
    vf = (
        f"scale={w * 2}:-2,"
        f"{_kb_filter(pattern, frames, w, h, fps)}"
        f"{tail},{fx_mod.GRADE},format=yuv420p"
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
        *_enc(),
        "-r",
        str(fps),
        "-an",
        str(out),
    ]
    _run(cmd, timeout=900)
    return out


def fit_clip(
    src: Path, out: Path, seconds: float, w: int, h: int, fps: int, extra: str = ""
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    pre: list[str] = []
    if info["duration"] and info["duration"] < seconds:
        pre = ["-stream_loop", "3"]
    tail = f",{extra}" if extra else ""
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},fps={fps}{tail},{fx_mod.GRADE},format=yuv420p"
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
        *_enc(),
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


def _chunk_words(words: list, max_words: int = 7, max_sec: float = 2.6) -> list:
    """Chia caption theo cum chu khong cat giua giua mang nghia.

    Ban cu chia cung 4 tu nen ra manh nhu "về chúng ta. Hàng" / "độc đang bán phá"
    - doc khong hieu, va text be nho khong ai doc. Bay gio moi nhan dung 7 tu
    hoac 2.6s, va khong bao gio cat giua mot cum.
    """
    out, cur = [], []
    for w in words:
        cur.append(w)
        span = cur[-1]["end"] - cur[0]["start"]
        full = len(" ".join(x["w"] for x in cur))
        if len(cur) >= max_words or span >= max_sec:
            # khong cat ngay sau dau cham - do la het mot y
            joined = " ".join(x["w"] for x in cur).rstrip(".,;:!?")
            if len(cur) >= 3 and not joined.endswith((".", "!", "?", "…")):
                out.append(cur)
                cur = []
    if cur:
        out.append(cur)
    return out


def build_karaoke(
    sentences: list, path: Path, kind: str, cap: float | None = None
) -> Path:
    if kind == "short":
        size, margin, res_x, res_y = 104, 430, 1080, 1920
    else:
        size, margin, res_x, res_y = 78, 150, 1920, 1080
    fname = (
        config.SUB_FONT_ASS
        if (config.MEDIA_POLISH and (config.FONTS_DIR / "Poppins-Bold.ttf").exists())
        else "DejaVu Sans"
    )
    words = _words_from_sentences(sentences, cap)
    groups = _chunk_words(words)
    path.parent.mkdir(parents=True, exist_ok=True)
    style = (
        f"Style: Karaoke,{fname},{size},&H0000D7FF,&H00FFFFFF,"
        f"&H00000000,&H88000000,-1,-1,0,0,100,100,0.5,0,1,5,1,2,"
        f"40,40,{margin},1\n\n"
    )
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {res_x}\nPlayResY: {res_y}\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
        "SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + style
        + "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )
    lines = [header]
    for chunk in groups:
        pop = (
            "{\\blur1.3\\fad(110,70)"
            "\\t(0,140,\\fscx106\\fscy106)\\t(140,260,\\fscx100\\fscy100)}"
        )
        tags = "".join(
            "{\\kf%s}%s " % (max(int((x["end"] - x["start"]) * 100), 1), _clean(x["w"]))
            for x in chunk
        ).strip()
        lines.append(
            f"Dialogue: 0,{_ass_ts(chunk[0]['start'])},{_ass_ts(chunk[-1]['end'])},"
            f"Karaoke,,0,0,0,,{pop}{tags}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
    return path


def _two_lines(chunk: list) -> str:
    """Chu thuong cho 1 den 2 dong, khong vuot khung 1080px."""
    txt = " ".join(_clean(x["w"]) for x in chunk)
    if len(txt) <= 20:
        return txt
    half = len(txt) // 2
    for i, ch in enumerate(txt):
        if i >= half - 8 and ch == " ":
            return txt[:i] + r"\N" + txt[i + 1 :]
    return txt


def _ass_header(res_x: int, res_y: int, styles: str) -> str:
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {res_x}\nPlayResY: {res_y}\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
        "SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + styles
        + "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
    )


def _ass_font() -> str:
    if config.MEDIA_POLISH and (config.FONTS_DIR / "Poppins-Bold.ttf").exists():
        return config.SUB_FONT_ASS
    return "DejaVu Sans"


def build_chapter_ass(
    scenes: list, sentences: list, beats: list, path: Path
) -> Path:
    """Chapter strip nhỏ góc trái: nhảy mỗi khi sang mốc chương (video dai)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = _ass_header(
        1920,
        1080,
        (
            f"Style: Chap,{_ass_font()},34,&H00FFFFFF,&H00FFFFFF,"
            "&H00000000,&H50000000,0,0,0,0,100,100,0.2,0,4,14,0,1,48,48,52,1\n\n"
        ),
    )
    names = [str(b).strip()[:44] for b in (beats or []) if str(b).strip()]
    per = max(1, len(sentences) / max(1, len(scenes))) if sentences else 1
    lines = [header]
    last_t = -10.0
    last_label = ""
    for i, s in enumerate(scenes):
        si = min(int(i * per), len(sentences) - 1) if sentences else 0
        t = float(sentences[si].get("start", 0)) if sentences else i * 6.0
        if i == 0 or t < 3.4:
            continue
        label = ""
        if names:
            label = names[min(i * len(names) // max(1, len(scenes)), len(names) - 1)]
        if not label:
            label = " ".join(str(s.get("caption") or "").split()[:6]) or f"Part {i + 1}"
        label = " ".join(label.upper().split())[:44]
        if label.lower() == last_label.lower() or t - last_t < 4.0:
            continue
        last_t, last_label = t, label
        lines.append(
            f"Dialogue: 0,{_ass_ts(t + 0.25)},{_ass_ts(t + 3.6)},Chap,,0,0,0,,"
            f"{{\\fad(220,230)}}PART {i + 1} - {label}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
    return path


def build_end_ass(path: Path, sentences: list, channel: str) -> Path:
    """End card cuoi video dai: 'Cam on da xem' + ten kenh, 4s cuoi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    total_end = max(float(sentences[-1]["end"]), 5.0) if sentences else 30.0
    st = max(total_end - 4.2, 0.0)
    ch = " ".join(str(channel or "Channel").upper().split())[:24]
    header = _ass_header(
        1920,
        1080,
        (
            f"Style: End,Anton,110,&H0000D7FF,&H0000D7FF,"
            "&H00000000,&H88000000,0,0,0,0,100,100,0,0,1,7,2,5,0,0,0,1"
        )
        + "\n\n",
    )
    lines = [
        header,
        f"Dialogue: 0,{_ass_ts(st)},{_ass_ts(total_end + 2.0)},End,,0,0,0,,"
        "{\\an5\\pos(960,470)\\fad(400,500)}THANKS FOR WATCHING\n",
        f"Dialogue: 0,{_ass_ts(st)},{_ass_ts(total_end + 2.0)},End,,0,0,0,,"
        "{\\an5\\pos(960,580)\\fad(500,500)}"
        f"{{\\fs52}}{{\\1c&H00FFFFFF&}}MORE ON {ch}\n",
    ]
    path.write_text("".join(lines), encoding="utf-8")
    return path


def build_burst_srt(sentences: list, path: Path, cap: float | None = None) -> Path:
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
    for chunk in _chunk_words(words):
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
    hook_text: str = "",
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ass_esc = ass.as_posix().replace(":", "\\:").replace("'", "")
    base = f"ass='{ass_esc}',format=yuv420p"
    vfs = [
        f"{fx_mod.hook_vf(hook_text, fx_mod.FONT)},{fx_mod.watermark_vf()},{base}",
        f"{fx_mod.hook_vf(hook_text, fx_mod.FONT)},{fx_mod.watermark_fallback()},{base}",
        f"{fx_mod.watermark_vf()},{base}",
        f"{fx_mod.watermark_fallback()},{base}",
        base,
    ]
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
        vfs[0],
        *_enc(),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-shortest",
        *FASTSTART,
    ]
    if max_sec:
        cmd += ["-t", f"{max_sec:.3f}"]
    cmd.append(str(out))
    err = None
    for vf in vfs:
        cmd[cmd.index("-vf") + 1] = vf
        try:
            _run(cmd, timeout=1800)
            return out
        except RuntimeError as e:
            err = e
            continue
    raise err


def mux_subs(
    video: Path,
    audio: Path,
    srt: Path,
    out: Path,
    kind: str,
    max_sec: float | None = None,
    hook_text: str = "",
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    if kind == "short":
        margin = 430
        size = 96
    else:
        margin = 150
        size = 70
    style = (
        "FontName=DejaVu Sans,FontSize={sz},PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H90000000,BorderStyle=1,Outline=4,Shadow=0,"
        "Alignment=2,MarginV={mg}".format(sz=size, mg=margin)
    )
    srt_esc = srt.as_posix().replace(":", "\\:").replace("'", "")
    base = f"subtitles='{srt_esc}':force_style='{style}',format=yuv420p"
    hook = fx_mod.hook_vf(hook_text, fx_mod.FONT)
    hook_fb = fx_mod.hook_fallback(hook_text)
    vfs = [
        f"{hook},{fx_mod.watermark_vf()},{base}",
        f"{hook},{fx_mod.watermark_fallback()},{base}",
        f"{hook_fb},{base}",
        f"{fx_mod.watermark_vf()},{base}",
        f"{fx_mod.watermark_fallback()},{base}",
        base,
    ]
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
        vfs[0],
        *_enc(),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-shortest",
        *FASTSTART,
    ]
    if max_sec:
        cmd += ["-t", f"{max_sec:.3f}"]
    cmd.append(str(out))
    err = None
    for vf in vfs:
        cmd[cmd.index("-vf") + 1] = vf
        try:
            _run(cmd, timeout=1800)
            return out
        except RuntimeError as e:
            err = e
            continue
    raise err


def mux_xfade(
    clips: list[Path],
    audio: Path,
    subfilter: str,
    out: Path,
    clip_dur: float,
    max_sec: float | None = None,
    hook_text: str = "",
    fade: float = FADE,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    n = len(clips)
    inputs: list[str] = []
    for c in clips:
        inputs += ["-i", str(c)]
    inputs += ["-i", str(audio)]
    vfs = [
        f"{fx_mod.hook_vf(hook_text, fx_mod.FONT)},{fx_mod.watermark_vf()},{subfilter},format=yuv420p",
        f"{fx_mod.hook_vf(hook_text, fx_mod.FONT)},{fx_mod.watermark_fallback()},{subfilter},format=yuv420p",
        f"{fx_mod.hook_fallback(hook_text)},{fx_mod.watermark_vf()},{subfilter},format=yuv420p",
        f"{fx_mod.watermark_vf()},{subfilter},format=yuv420p",
        f"{fx_mod.watermark_fallback()},{subfilter},format=yuv420p",
        f"{subfilter},format=yuv420p",
    ]
    err = None
    for tail in vfs:
        parts = []
        prev = "0:v"
        for k in range(1, n):
            trans = (
                config.TRANSITIONS[(k - 1) % len(config.TRANSITIONS)]
                if config.MEDIA_POLISH
                else "fade"
            )
            off = k * clip_dur - k * fade
            parts.append(
                f"[{prev}][{k}:v]xfade=transition={trans}:duration={fade}"
                f":offset={off:.3f}[x{k}]"
            )
            prev = f"x{k}"
        parts.append(f"[{prev}]{tail}[vout]")
        cmd = (
            ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts)]
            + ["-map", "[vout]", "-map", f"{n}:a:0"]
            + _enc()
            + [
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-shortest",
                *FASTSTART,
            ]
        )
        if max_sec:
            cmd += ["-t", f"{max_sec:.3f}"]
        cmd.append(str(out))
        try:
            _run(cmd, timeout=2400)
            return out
        except RuntimeError as e:
            err = e
            continue
    raise err


def _thumb_variants(txt: Path, size: int, w: int, h: int, frac: str, border: int) -> list:
    anton = fx_mod._font_file("Anton-Regular.ttf")
    accent = (config.ACCENT or "0xFFD700").replace("#", "")
    bx, by = int(w * 0.055), int(h * 0.56)
    bw, bh = max(int(w * 0.013), 5), int(h * 0.30)
    bar = f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color={accent}@0.92:t=fill"

    def _main(farg: str) -> str:
        tf = txt.as_posix().replace(":", "\\:")
        return (
            f"drawtext=textfile='{tf}':fontsize={size}:{farg}:"
            f"fontcolor=white:borderw={border}:bordercolor=black@0.9:"
            f"shadowcolor=black@0.6:shadowx=0:shadowy={max(border, 6)}:"
            f"x=(w-text_w)/2:y={frac}:line_spacing={int(size * 0.16)}"
        )

    if anton:
        return [",".join([bar, _main(f"fontfile={anton}")]), None]
    return [",".join([bar, _main("font='DejaVu Sans'")]), None]


def build_thumb(video: Path, title: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    ss = max((info["duration"] or 10) * 0.3, 1.0)
    txt = out.parent / "thumb.txt"
    txt.write_bytes(wrap_title(title, width=16, lines=3).encode("utf-8"))
    pre = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "eq=saturation=1.08,"
        "drawbox=x=0:y=ih*0.5:w=iw:h=ih*0.5:color=black@0.6:t=fill,"
    )
    errs = []
    for i, dt in enumerate(_thumb_variants(txt, 86, 1280, 720, "h*0.5", 8)):
        vf = pre + dt if dt else pre.rstrip(",")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{ss:.1f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            vf,
            str(out),
        ]
        try:
            _run(cmd, timeout=120)
            return out
        except RuntimeError as e:
            errs.append(f"try{i}:{str(e)[-200:]}")
    raise RuntimeError("thumbnail all variants failed: " + " | ".join(errs))


def build_short_thumb(video: Path, title: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    info = probe(video)
    dur = info["duration"] or 10
    if dur > 4.2:
        ss = min(max(dur * 0.3, 3.35), max(3.35, dur - 0.8))
    else:
        ss = min(max(dur * 0.25, 0.5), 6.0)
    txt = out.parent / "sthumb.txt"
    txt.write_bytes(wrap_title(title, width=13, lines=4).encode("utf-8"))
    pre = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "eq=saturation=1.08,"
        "drawbox=x=0:y=ih*0.42:w=iw:h=ih*0.42:color=black@0.55:t=fill,"
    )
    errs = []
    for i, dt in enumerate(_thumb_variants(txt, 118, 1080, 1920, "h*0.47", 10)):
        vf = pre + dt if dt else pre.rstrip(",")
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{ss:.1f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            vf,
            str(out),
        ]
        try:
            _run(cmd, timeout=120)
            return out
        except RuntimeError as e:
            errs.append(f"try{i}:{str(e)[-200:]}")
    raise RuntimeError("short thumbnail all variants failed: " + " | ".join(errs))


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
    items: list[tuple[Path, bool, str, str]],
    audio: Path,
    sentences: list,
    scenes: list,
    voice_dur: float,
    title: str,
    workdir: Path,
    kind: str,
    beats: list | None = None,
) -> tuple[Path, Path]:
    if kind == "short":
        w, h, fps, cap, fade = (
            config.SHORT_W,
            config.SHORT_H,
            config.SHORT_FPS,
            float(config.SHORT_MAX_SEC),
            FADE,
        )
    else:
        w, h, fps, cap, fade = (
            config.LONG_W,
            config.LONG_H,
            config.LONG_FPS,
            None,
            FADE_LONG,
        )
    workdir.mkdir(parents=True, exist_ok=True)
    n = len(items)
    total = min(voice_dur, cap) if cap else voice_dur
    d = (total + (n - 1) * fade) / n if n > 1 else total
    durs = [d] * n
    patterns = list(KB_PATTERNS)
    random.Random(workdir.name).shuffle(patterns)
    clips = []
    for i, (path, is_video, _url, _credit) in enumerate(items):
        if config.kill_requested():
            raise RuntimeError("kill switch on")
        clip = workdir / f"clip_{i:02d}.mp4"
        extra = fx_mod.variant(f"{workdir.name}:{i}")
        if is_video:
            fit_clip(path, clip, d, w, h, fps, extra)
        else:
            ken_burns(path, clip, d, w, h, fps, extra, pattern=patterns[i % len(patterns)])
        clips.append(clip)
    if sentences:
        subs_path = build_karaoke(sentences, workdir / "subs.ass", kind, cap)
        cc = build_burst_srt(sentences, workdir / "cc.srt", cap)
        ass_esc = subs_path.as_posix().replace(":", "\\:").replace("'", "")
        subfilter = f"ass='{ass_esc}':fontsdir='assets/fonts'"
        if kind == "long" and config.MEDIA_POLISH and len(sentences) > 3:
            chap = build_chapter_ass(scenes, sentences, beats or [], workdir / "chapters.ass")
            chap_esc = chap.as_posix().replace(":", "\\:").replace("'", "")
            endp = build_end_ass(workdir / "end.ass", sentences, config.CHANNEL_NAME)
            end_esc = endp.as_posix().replace(":", "\\:").replace("'", "")
            subfilter += f",ass='{chap_esc}':fontsdir='assets/fonts',ass='{end_esc}'"
    else:
        cc = write_srt(scenes, durs, workdir / "cc.srt")
        srt_esc = cc.as_posix().replace(":", "\\:").replace("'", "")
        if kind == "short":
            margin, size = 430, 96
        else:
            margin, size = 150, 70
        style = (
            "FontName=DejaVu Sans,FontSize={sz},PrimaryColour=&HFFFFFF,"
            "OutlineColour=&H90000000,BorderStyle=1,Outline=4,Shadow=0,"
            "Alignment=2,MarginV={mg}".format(sz=size, mg=margin)
        )
        subfilter = f"subtitles='{srt_esc}':force_style='{style}'"
    hook_text = _hook_headline(title, scenes)
    final = workdir / "final.mp4"
    hard_cap = (cap + 3.0) if cap else None
    if n > 1:
        mux_xfade(
            clips, audio, subfilter, final, d, max_sec=hard_cap, hook_text=hook_text, fade=fade
        )
    else:
        mux_ass(clips[0], audio, subs_path if sentences else cc, final, max_sec=hard_cap, hook_text=hook_text)
    for c in clips:
        c.unlink(missing_ok=True)
    if kind == "short":
        verify_short(final)
    return final, cc


def build_chapters(scenes: list, sentences: list, beats: list | None = None) -> str:
    """Muc luc chapters cho video dai - tang CTR va retention.

    YouTube hien chapters tren thanh tien trinh khi mo ta co dong
    "MM:SS tieu de" bat dau tu 00:00, toi thieu 3 chapter, moi chapter >=10s.
    Lay moc tu gio bat dau cau noi cua moi scene (noi suy theo thu tu vi
    voiceover doc scene theo dung thu tu).
    """
    if not scenes or not sentences:
        return ""
    per = max(1, len(sentences) / max(1, len(scenes)))
    names = []
    if beats:
        names = [str(b)[:60] for b in beats if str(b).strip()]
    lines = []
    for i, s in enumerate(scenes):
        si = min(int(i * per), len(sentences) - 1)
        t = max(0.0, float(sentences[si].get("start", 0)))
        label = ""
        if names:
            label = names[min(i * len(names) // max(1, len(scenes)), len(names) - 1)]
        if not label:
            label = " ".join(str(s.get("caption") or "").split()[:7]) or f"Part {i + 1}"
        lines.append((t, label.strip()[:60]))
    # gop chapter <30s ke nhau, giu toi da 12 chapter
    merged = []
    for t, label in lines:
        if merged and t - merged[-1][0] < 30:
            continue
        if merged and label.lower() == merged[-1][1].lower():
            continue
        merged.append([t, label])
    while len(merged) > 12:
        step = len(merged) / 12
        merged = [merged[int(i * step)] for i in range(12)]
    if merged:
        merged[0][0] = 0.0
    out = []
    for t, label in merged:
        mm, ss = divmod(int(t), 60)
        hh, mm = divmod(mm, 60)
        ts = f"{hh}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
        out.append(f"{ts} {label}")
    return "\n".join(out)


def _hook_headline(title: str, scenes: list) -> str:
    """Tieu de 3 giay dau: lay phan 'dieu le do' cua tieu de video.

    Video nao cung bat dau bang mot cuc hinh anh trung tinh, nhin khong ra
    chuyen gi dang xay ra. Tieu de lon 3 giay dau la thu giu nguoi xem lai.
    """
    t = " ".join(str(title or "").split())
    t = t.split(" - ")[0].strip()
    if not t:
        return ""
    words = t.split()
    if len(words) > 9:
        t = " ".join(words[:9])
    return t.upper() if t.isascii() else t
