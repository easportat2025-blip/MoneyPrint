"""Grab a contact sheet of frames from a downloaded video (no ffmpeg needed)."""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent


def sheet(path: Path, cols=6, rows=2, w=260):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    if n <= 0:
        print(f"{path.name}: cannot read (codec?)")
        return None
    dur = n / fps
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = w / cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = max(1, int(h * scale))
    picks = np.linspace(0, n - 1, cols * rows).astype(int)
    tiles = []
    for i, idx in enumerate(picks):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, fr = cap.read()
        if not ok:
            tiles.append(np.full((h, w, 3), 40, np.uint8))
            continue
        fr = cv2.resize(fr, (w, h))
        t = idx / fps
        cv2.rectangle(fr, (0, 0), (w - 1, h - 1), (0, 200, 255), 1)
        cv2.putText(fr, f"{t:.1f}s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)
        tiles.append(fr)
    cap.release()
    grid = np.vstack([np.hstack(tiles[r * cols : (r + 1) * cols]) for r in range(rows)])
    out = path.with_suffix(".sheet.jpg")
    cv2.imwrite(str(out), grid, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{path.name}: {dur:.1f}s {n}f @{fps:.0f}fps -> {out.name}")
    return out


if __name__ == "__main__":
    for a in sys.argv[1:]:
        sheet(Path(a))