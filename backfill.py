import os
import subprocess
import sys
import time
from pathlib import Path
import config
import state

ROOT = Path(__file__).resolve().parents[1]

def targets() -> dict:
    return {
        "1": int(os.environ.get("TARGET_ACC1", "1")),
        "2": int(os.environ.get("TARGET_ACC2", "8")),
        "3": int(os.environ.get("TARGET_ACC3", "5")),
    }


LONG_SLOTS = {
    "1": int(os.environ.get("TARGET_LONG_ACC1", "1")),
}

# visual identity per slot: (VISUAL_STYLE, MEDIA_MODE)
# acc1 = long stickman, acc2 = history archival stills, acc3 = animated stock
SLOT_STYLE = {
    "1": ("stickman", "mixed"),
    "2": ("stock", "stills"),
    "3": ("stock", "mixed"),
}


def run_one(kind: str = "short", slot: str = "") -> bool:
    env = dict(os.environ)
    if slot:
        env["CHANNEL"] = slot
        style, media = SLOT_STYLE.get(slot, ("stock", "mixed"))
        env["VISUAL_STYLE"] = style
        env["MEDIA_MODE"] = media
        if kind == "long":
            env["STICKMAN_SCENE_SEC"] = "14"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), kind],
        cwd=str(ROOT),
        env=env,
        timeout=5400,
    )
    return proc.returncode == 0


def backfill(max_videos: int = 40) -> int:
    tg = targets()
    made = 0
    plan = [("1", "long"), ("2", "short"), ("3", "short")]
    for _slot, kind in plan:
        if made >= max_videos:
            break
        os.environ["CHANNEL"] = _slot
        for mod in [m for m in list(sys.modules) if m.startswith(("config", "state"))]:
            del sys.modules[mod]
        import config as cfg
        import state as st

        want = LONG_SLOTS.get(_slot, 0) if kind == "long" else tg.get(_slot, 0)
        have = st.uploads_today_by_slot().get(_slot, 0)
        if kind == "short":
            have_short = sum(
                1
                for r in st.load()
                if (r.get("slot") or r.get("channel")) == _slot
                and r.get("kind") == "short"
                and r.get("youtube_id")
                and r.get("created_at", "").startswith(
                    st.datetime.now(st.timezone.utc).date().isoformat()
                )
            )
            have = have_short
        need = want - have
        print(
            f"[backfill] {kind} channel {_slot} ({cfg.CHANNEL_NAME}): {have}/{want} -> need {need}",
            flush=True,
        )
        for i in range(max(0, need)):
            if made >= max_videos:
                break
            print(
                f"[backfill] making {kind} {i + 1}/{need} for slot {_slot}", flush=True
            )
            if run_one(kind, slot=_slot):
                made += 1
            else:
                print(f"[backfill] slot {_slot} failed, moving on", flush=True)
                time.sleep(20)
    print(f"[backfill] DONE, created {made} videos", flush=True)
    return made


def burst(count: int, kind: str = "short", slot: str = "") -> int:
    made = 0
    for i in range(count):
        print(f"[burst] {i + 1}/{count} {kind}", flush=True)
        if run_one(kind, slot=slot):
            made += 1
        else:
            time.sleep(20)
    print(f"[burst] created {made}/{count}", flush=True)
    return made
