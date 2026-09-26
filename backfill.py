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
        "1": int(os.environ.get("TARGET_ACC1", "4")),
        "2": int(os.environ.get("TARGET_ACC2", "8")),
        "3": int(os.environ.get("TARGET_ACC3", "3")),
    }


def run_one(kind: str = "short") -> bool:
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), kind],
        cwd=str(ROOT),
        env=env,
        timeout=3000,
    )
    return proc.returncode == 0


def backfill(max_videos: int = 40) -> int:
    tg = targets()
    made = 0
    for _slot in ("2", "1", "3"):
        if made >= max_videos:
            break
        os.environ["CHANNEL"] = _slot
        for mod in [m for m in list(sys.modules) if m.startswith(("config", "state"))]:
            del sys.modules[mod]
        import config as cfg
        import state as st

        want = tg.get(_slot, 0)
        have = st.uploads_today_by_slot().get(_slot, 0)
        need = want - have
        print(
            f"[backfill] channel {_slot} ({cfg.CHANNEL_NAME}): {have}/{want} -> need {need}",
            flush=True,
        )
        for i in range(max(0, need)):
            if made >= max_videos:
                break
            print(f"[backfill] making video {i + 1}/{need} for slot {_slot}", flush=True)
            if run_one("short"):
                made += 1
            else:
                print(f"[backfill] slot {_slot} failed, moving on", flush=True)
                time.sleep(20)
    print(f"[backfill] DONE, created {made} videos", flush=True)
    return made


def burst(count: int, kind: str = "short") -> int:
    made = 0
    for i in range(count):
        print(f"[burst] {i + 1}/{count} {kind}", flush=True)
        if run_one(kind):
            made += 1
        else:
            time.sleep(20)
    print(f"[burst] created {made}/{count}", flush=True)
    return made
