import subprocess
from pathlib import Path
import config


def _run(cmd: list[str], timeout: int = 1200) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {cmd[:4]}\n{proc.stderr[-800:]}")


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


def mux_audio(video: Path, audio: Path, out: Path, max_sec: float | None = None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
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
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
    ]
    if max_sec:
        cmd += ["-t", f"{max_sec:.3f}"]
    cmd.append(str(out))
    _run(cmd)
    return out


def assemble(
    images: list[Path],
    audio: Path,
    workdir: Path,
    kind: str,
) -> Path:
    if kind == "short":
        w, h, fps, scene_sec, max_sec = (
            config.SHORT_W,
            config.SHORT_H,
            config.SHORT_FPS,
            config.SHORT_SCENE_SEC,
            config.SHORT_MAX_SEC,
        )
    else:
        w, h, fps, scene_sec, max_sec = (
            config.LONG_W,
            config.LONG_H,
            config.LONG_FPS,
            config.LONG_SCENE_SEC,
            600,
        )
    workdir.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, img in enumerate(images):
        clip = workdir / f"clip_{i:02d}.mp4"
        ken_burns(img, clip, scene_sec, w, h, fps)
        clips.append(clip)
    silent = workdir / "silent.mp4"
    concat_clips(clips, silent)
    final = workdir / "final.mp4"
    mux_audio(silent, audio, final, max_sec=max_sec)
    for c in clips:
        c.unlink(missing_ok=True)
    silent.unlink(missing_ok=True)
    return final
