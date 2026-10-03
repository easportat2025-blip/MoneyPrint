"""Fetch REAL YouTube stats + comments for tracked videos (local tool, needs .env).

Usage:
  python tools/yt_audit.py            # summary per account
  python tools/yt_audit.py --comments # dump every comment found
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.daily_ping import _slot_key, SLOT_LABEL  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"


def load_env() -> dict:
    out = {}
    p = ROOT / ".env"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def token(env: dict, key: str):
    cid, csec = env.get("YOUTUBE_CLIENT_ID", ""), env.get("YOUTUBE_CLIENT_SECRET", "")
    rt = env.get(key, "")
    if not (cid and rt):
        return None
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": cid,
            "client_secret": csec,
            "refresh_token": rt,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  !! token {key}: HTTP {r.status_code} {r.text[:120]}")
        return None
    return r.json().get("access_token")


def get(tok, path, **params):
    params["key"] = None
    params.pop("key")
    r = requests.get(f"{API}/{path}", params=params, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    if r.status_code != 200:
        print(f"  !! {path}: HTTP {r.status_code} {r.text[:150]}")
        return {}
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--comments", action="store_true")
    ap.add_argument("--slot", default="")
    args = ap.parse_args()

    env = load_env()
    for cand in ("state.json", "state_from_logs.json"):
        p = ROOT / cand
        if p.exists() and p.stat().st_size:
            recs = json.loads(p.read_text(encoding="utf-8"))
            break
    else:
        print("no state.json / state_from_logs.json - run: python main.py sync")
        return 1
    recs = [r for r in recs if r.get("youtube_id")]
    if args.slot:
        recs = [r for r in recs if _slot_key(r) == args.slot]
    print(f"tracked videos: {len(recs)}")

    for slot, key in [("2", "YOUTUBE_REFRESH_TOKEN_2"), ("3", "YOUTUBE_REFRESH_TOKEN_3")]:
        mine = [r for r in recs if _slot_key(r) == slot]
        if not mine:
            continue
        tok = token(env, key)
        if not tok:
            print(f"\n### {SLOT_LABEL.get(slot, slot)}: TOKEN DEAD, skip")
            continue
        me = get(tok, "channels", part="snippet,statistics", mineFields="x")
        mine_fields = "contentDetails,statistics,snippet"
        ids = [r["youtube_id"] for r in mine]
        print(f"\n### {SLOT_LABEL.get(slot, slot)} - {len(ids)} videos")
        rows = []
        allc = []
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            d = get(tok, "videos", part=mine_fields, id=",".join(chunk), mineFields="x")
            order = {v: k for k, v in enumerate(ids)}
            items = sorted(d.get("items", []), key=lambda it: order.get(it["id"], 999))
            for it in items:
                st = it.get("statistics", {})
                rows.append(
                    (
                        it["id"],
                        int(st.get("viewCount", 0)),
                        int(st.get("likeCount", 0)),
                        int(st.get("commentCount", 0)),
                        it.get("snippet", {}).get("title", "")[:58],
                        it.get("contentDetails", {}).get("duration", ""),
                    )
                )
            for it in items:
                if int(it.get("statistics", {}).get("commentCount", 0)) > 0:
                    allc += fetch_comments(tok, it["id"])
        rows.sort(key=lambda r: -r[1])
        print(f"{'views':>7} {'likes':>6} {'cmts':>5} {'dur':>7}  title")
        for vid, v, lk, c, t, dur in rows:
            print(f"{v:>7} {lk:>6} {c:>5} {dur:>7}  {t.encode('ascii','replace').decode()}  {vid}")

        if allc:
            dump_comments(slot, allc)
    return 0


def fetch_comments(tok, vid):
    out = []
    tokpage = None
    while True:
        r = requests.get(
            f"{API}/commentThreads",
            params={
                "part": "snippet",
                "videoId": vid,
                "maxResults": 100,
                "textFormat": "plainText",
                "pageToken": tokpage or "",
            },
            headers={"Authorization": f"Bearer {tok}"},
            timeout=30,
        )
        if r.status_code != 200:
            break
        j = r.json()
        for it in j.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            out.append({"video": vid, "author": sn.get("authorDisplayName", ""), "text": sn.get("textDisplay", "")})
        tokpage = j.get("nextPageToken")
        if not tokpage:
            break
    return out


def dump_comments(slot, cs):
    p = ROOT / f"cache_comments_{slot}.json"
    p.write_text(json.dumps(cs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> {len(cs)} comments saved to {p.name}")


if __name__ == "__main__":
    sys.exit(main())